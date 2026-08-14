import os
import uuid
import asyncio
import aiofiles
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Request, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.security import validate_image, sanitize_filename
from sqlalchemy.orm import Session
from app.core.auth import get_current_user, check_daily_limit, increment_usage
from app.db.database import get_db
from app.db.models import User
from app.services import (
    detect_ai_content,
    reverse_image_search,
    analyze_public_footprint,
    compute_consistency,
    compute_evidence_score,
    generate_analysis_report,
    generate_demo_analysis,
)

router = APIRouter(prefix="/api")
limiter = Limiter(key_func=get_remote_address)


def _ensure_upload_dir():
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


async def _cleanup_file(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _compress_image(content: bytes, max_side: int = 1280, quality: int = 82) -> bytes:
    """Shrink image to speed up external API uploads."""
    try:
        from io import BytesIO
        from PIL import Image
        img = Image.open(BytesIO(content))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_side:
            img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue()
    except Exception:
        return content


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "TraceID",
        "demo_mode": settings.is_demo_mode,
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "ai_detector_configured": bool(settings.AI_DETECTOR_API_KEY),
        "reverse_search_configured": bool(settings.REVERSE_SEARCH_API_KEY),
    }


@router.post("/analyze")
@limiter.limit(settings.RATE_LIMIT)
async def analyze_image(
    request: Request,
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    demo: Optional[bool] = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    use_demo = bool(demo) or settings.is_demo_mode or settings.FORCE_DEMO_MODE

    _ensure_upload_dir()
    unique_name = f"{uuid.uuid4().hex}_image.jpg"
    file_path = None
    content = None

    if use_demo:
        if file and file.filename:
            try:
                await validate_image(file)
                original_name = sanitize_filename(file.filename)
                unique_name = f"{uuid.uuid4().hex}_{original_name}"
                file_path = os.path.join(settings.UPLOAD_DIR, unique_name)
                content = await file.read()
                async with aiofiles.open(file_path, "wb") as f:
                    await f.write(content)
                background_tasks.add_task(_cleanup_file, file_path)
            except Exception:
                pass
        result = generate_demo_analysis(seed=unique_name)
        result["is_demo"] = True
        return JSONResponse(content=result)

    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="Se requiere una imagen para el análisis.")

    check_daily_limit(db, user)

    await validate_image(file)
    original_name = sanitize_filename(file.filename or "image.jpg")
    unique_name = f"{uuid.uuid4().hex}_{original_name}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_name)
    raw = await file.read()
    content = _compress_image(raw)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)
    background_tasks.add_task(_cleanup_file, file_path)

    try:
        # Parallel: AI detector + reverse search (biggest time save)
        image_analysis, reverse_result = await asyncio.gather(
            detect_ai_content(file_path, content),
            reverse_image_search(file_path, content),
            return_exceptions=True,
        )

        if isinstance(image_analysis, Exception):
            print(f"[Analyze] AI detector error: {image_analysis}")
            image_analysis = {
                "ai_probability": 0,
                "confidence": "low",
                "explanation": "No se pudo completar la detección de IA a tiempo. Reintentá más tarde.",
                "warning": "Resultado parcial por timeout o error del proveedor.",
            }
        if isinstance(reverse_result, Exception):
            print(f"[Analyze] Reverse search error: {reverse_result}")
            reverse_result = {
                "matches_found": 0,
                "sources": [],
                "note": "La búsqueda inversa no respondió a tiempo. Esto no implica que la imagen sea original.",
            }

        footprint = await analyze_public_footprint(reverse_result, file_path)
        consistency = compute_consistency(reverse_result, footprint)
        evidence = compute_evidence_score(image_analysis, reverse_result, footprint, consistency)

        # Fast template report (skip Gemini wait — keeps us under Render free timeout)
        report = await generate_analysis_report(
            image_analysis, reverse_result, footprint, consistency, evidence
        )

        warnings = report.get("warnings") or []
        if not warnings:
            ai_prob = image_analysis.get("ai_probability", 0)
            if ai_prob >= 70:
                warnings.append({
                    "level": "red",
                    "message": "El detector encontró una alta probabilidad de generación o manipulación mediante IA.",
                })
            elif ai_prob >= 40:
                warnings.append({
                    "level": "yellow",
                    "message": "Existen señales intermedias compatibles tanto con contenido real como con manipulación.",
                })
            if reverse_result.get("matches_found", 0) >= 3:
                warnings.append({
                    "level": "yellow",
                    "message": "La imagen aparece en múltiples sitios sin una fuente original claramente identificable.",
                })
            if reverse_result.get("matches_found", 0) == 0:
                warnings.append({
                    "level": "yellow",
                    "message": "No se encontraron coincidencias indexadas. Esto no implica que la imagen sea original.",
                })

        increment_usage(db, user.id)

        result = {
            "is_demo": False,
            "image_analysis": image_analysis,
            "reverse_search": reverse_result,
            "public_footprint": footprint,
            "consistency": consistency,
            "evidence_score": evidence,
            "summary": report.get("summary", ""),
            "warnings": warnings,
        }
        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Analyze] Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Ocurrió un error durante el análisis. Por favor intentá nuevamente.",
        )


@router.post("/detect-ai")
@limiter.limit(settings.RATE_LIMIT)
async def detect_ai_only(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    await validate_image(file)
    _ensure_upload_dir()
    unique_name = f"{uuid.uuid4().hex}_{sanitize_filename(file.filename or 'img.jpg')}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_name)
    content = _compress_image(await file.read())
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)
    background_tasks.add_task(_cleanup_file, file_path)

    if settings.is_demo_mode:
        return generate_demo_analysis(seed=unique_name)["image_analysis"]
    return await detect_ai_content(file_path, content)


@router.post("/reverse-search")
@limiter.limit(settings.RATE_LIMIT)
async def reverse_search_only(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    await validate_image(file)
    _ensure_upload_dir()
    unique_name = f"{uuid.uuid4().hex}_{sanitize_filename(file.filename or 'img.jpg')}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_name)
    content = _compress_image(await file.read())
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)
    background_tasks.add_task(_cleanup_file, file_path)

    if settings.is_demo_mode:
        return generate_demo_analysis(seed=unique_name)["reverse_search"]
    return await reverse_image_search(file_path, content)


@router.post("/analyze-public-footprint")
async def footprint_endpoint(payload: dict):
    return await analyze_public_footprint(payload.get("reverse_search", {}))


@router.post("/generate-report")
async def report_endpoint(payload: dict):
    return await generate_analysis_report(
        payload.get("image_analysis", {}),
        payload.get("reverse_search", {}),
        payload.get("public_footprint", {}),
        payload.get("consistency", {}),
        payload.get("evidence_score", {}),
    )
