"""
AI Image Detector service.
Primary provider: Sightengine (genai model).
Falls back to demo/simulated results when not configured.
"""

from typing import Dict, Any, Optional
import httpx
from app.core.config import settings
from app.services.demo_data import generate_demo_analysis


async def detect_ai_content(image_path: str, image_bytes: Optional[bytes] = None) -> Dict[str, Any]:
    """Detect probability that an image was generated or manipulated by AI."""
    if settings.AI_DETECTOR_API_KEY and settings.AI_DETECTOR_API_URL:
        try:
            return await _call_sightengine(image_path, image_bytes)
        except Exception as e:
            print(f"[AI Detector] Real API failed: {e}. Using simulation.")

    demo = generate_demo_analysis(seed=image_path or "fallback")
    return demo["image_analysis"]


async def _call_sightengine(image_path: str, image_bytes: Optional[bytes] = None) -> Dict[str, Any]:
    """
    Sightengine AI-generated image detection.
    AI_DETECTOR_API_KEY format: api_user:api_secret
    """
    key = settings.AI_DETECTOR_API_KEY.strip()
    if ":" not in key:
        raise ValueError("Sightengine key must be api_user:api_secret")

    api_user, api_secret = key.split(":", 1)
    url = settings.AI_DETECTOR_API_URL.strip() or "https://api.sightengine.com/1.0/check.json"

    data = {
        "models": "genai",
        "api_user": api_user,
        "api_secret": api_secret,
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        if image_bytes:
            files = {"media": ("image.jpg", image_bytes, "image/jpeg")}
            response = await client.post(url, data=data, files=files)
        else:
            with open(image_path, "rb") as f:
                files = {"media": ("image.jpg", f, "image/jpeg")}
                response = await client.post(url, data=data, files=files)

        response.raise_for_status()
        payload = response.json()

    if payload.get("status") == "failure":
        raise RuntimeError(payload.get("error", {}).get("message", "Sightengine error"))

    ai_score = float(payload.get("type", {}).get("ai_generated", 0.0))
    ai_probability = round(ai_score * 100)

    if ai_probability < 30:
        confidence = "low"
        explanation = (
            "El análisis visual no detectó patrones fuertes asociados a generación sintética. "
            "Las texturas y el ruido de imagen son compatibles con una fotografía convencional. "
            "Este resultado no descarta manipulación posterior."
        )
    elif ai_probability < 70:
        confidence = "medium"
        explanation = (
            "Se observaron características visuales que pueden aparecer tanto en fotografías reales "
            "como en imágenes generadas o editadas. La confianza del detector es moderada. "
            "Se recomienda contrastar con otras fuentes."
        )
    else:
        confidence = "high"
        explanation = (
            "El sistema identificó señales compatibles con contenido generado o fuertemente "
            "manipulado mediante IA. Este resultado no constituye una prueba definitiva y puede "
            "contener falsos positivos."
        )

    return {
        "ai_probability": ai_probability,
        "confidence": confidence,
        "explanation": explanation,
        "warning": (
            "Este resultado puede contener falsos positivos y falsos negativos. "
            "No constituye una prueba definitiva de autenticidad o manipulación."
        ),
        "provider": "sightengine",
        "raw_score": ai_score,
    }
