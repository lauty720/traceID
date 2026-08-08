from fastapi import HTTPException, UploadFile
from app.core.config import settings

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Magic number signatures for basic validation without python-magic
MAGIC_SIGNATURES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "image/webp",  # WEBP starts with RIFF....WEBP
}


async def validate_image(file: UploadFile) -> None:
    """Validate uploaded file type and size."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo no válido.")

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Formato no permitido. Usa: JPG, JPEG, PNG o WEBP.",
        )

    content = await file.read()
    await file.seek(0)

    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo supera el límite de {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )

    if len(content) < 100:
        raise HTTPException(status_code=400, detail="El archivo parece vacío o corrupto.")

    # Magic byte validation (no external dependency required)
    is_valid = False
    if content[:3] == b"\xff\xd8\xff":
        is_valid = True
    elif content[:8] == b"\x89PNG\r\n\x1a\n":
        is_valid = True
    elif content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        is_valid = True

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="El contenido del archivo no coincide con una imagen válida.",
        )


def sanitize_filename(filename: str) -> str:
    """Basic filename sanitization."""
    import re
    name = re.sub(r"[^\w\-_.]", "_", filename)
    return name[:100]
