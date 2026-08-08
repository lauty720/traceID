import os
import uuid
import aiofiles
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.security import validate_image, sanitize_filename
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
    """Delete temporary file after analysis."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


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
):
    """
    Main analysis endpoint.
    Coordinates AI detection, reverse search, public footprint and report generation.
    When demo=true (or system is in demo mode) returns fictional data without requiring a valid image.
    """
    use_demo = bool(demo) or settings.is_demo_mode or settings.FORCE_DEMO_MODE

    _ensure_upload_dir()
    unique_name = f"{uuid.uuid4().hex}_image.jpg"
    file_path = None
    content = None

    if use_demo:
        # Demo: file is optional. If provided and valid we still accept it for seed variety.
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
                pass  # invalid file in demo is fine

        result = generate_demo_analysis(seed=unique_name)
        result["is_demo"] = True
        return JSONResponse(content=result)

    # --- Real pipeline: image is required ---
    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="Se requiere una imagen para el análisis.")

    await validate_image(file)
    original_name = sanitize_filename(file.filename or "image.jpg")
    unique_name = f"{uuid.uuid4().hex}_{original_name}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_name)
    content = await file.read()
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)
    background_tasks.add_task(_cleanup_file, file_path)

    try:
        image_analysis = await detect_ai_content(file_path, content)
        reverse_result = await reverse_image_search(file_path, content)
        footprint = await analyze_public_footprint(reverse_result, file_path)
        consistency = compute_consistency(reverse_result, footprint)
        evidence = compute_evidence_score(image_analysis, reverse_result, footprint, consistency)
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
    content = await file.read()
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)
    background_tasks.add_task(_cleanup_file, file_path)

    if settings.is_demo_mode:
        demo = generate_demo_analysis(seed=unique_name)
        return demo["image_analysis"]

    result = await detect_ai_content(file_path, content)
    return result


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
    content = await file.read()
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)
    background_tasks.add_task(_cleanup_file, file_path)

    if settings.is_demo_mode:
        demo = generate_demo_analysis(seed=unique_name)
        return demo["reverse_search"]

    result = await reverse_image_search(file_path, content)
    return result


@router.post("/analyze-public-footprint")
async def footprint_endpoint(payload: dict):
    reverse_result = payload.get("reverse_search", {})
    result = await analyze_public_footprint(reverse_result)
    return result


@router.post("/generate-report")
async def report_endpoint(payload: dict):
    report = await generate_analysis_report(
        payload.get("image_analysis", {}),
        payload.get("reverse_search", {}),
        payload.get("public_footprint", {}),
        payload.get("consistency", {}),
        payload.get("evidence_score", {}),
    )
    return report
