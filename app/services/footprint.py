"""
Public footprint — extract profiles only from reverse-search public URLs.
No facial recognition. No private data.
"""

from typing import Dict, Any, List, Set
from urllib.parse import urlparse
from app.services.demo_data import generate_demo_analysis


SOCIAL_PATTERNS = {
    "instagram.com": "Instagram",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "tiktok.com": "TikTok",
    "facebook.com": "Facebook",
    "fb.com": "Facebook",
    "x.com": "X",
    "twitter.com": "X",
    "linkedin.com": "LinkedIn",
    "github.com": "GitHub",
}


def _extract_username(url: str, platform: str) -> str:
    try:
        path = urlparse(url).path.strip("/")
        parts = [p for p in path.split("/") if p]
        if not parts:
            return ""
        skip = {"watch", "reel", "p", "status", "posts", "photo", "videos", "channel", "c", "user"}
        for p in parts:
            if p.lower() in skip:
                continue
            if p.startswith("@"):
                return p
            if len(p) > 1:
                return f"@{p}" if platform in ("Instagram", "X", "TikTok") else p
        return parts[0] if parts else ""
    except Exception:
        return ""


async def analyze_public_footprint(reverse_search_result: Dict[str, Any], image_path: str = "") -> Dict[str, Any]:
    sources = reverse_search_result.get("sources") or []

    if not sources:
        if reverse_search_result.get("provider") is None and image_path:
            demo = generate_demo_analysis(seed=image_path)
            return demo["public_footprint"]
        return {
            "possible_profiles": [],
            "platforms": [],
            "note": "No se encontraron fuentes públicas a partir de las cuales extraer perfiles.",
        }

    profiles: List[Dict[str, Any]] = []
    platforms: Set[str] = set()
    seen_urls: Set[str] = set()

    for src in sources:
        url = src.get("url") or ""
        domain = (src.get("domain") or urlparse(url).netloc or "").lower()
        platform = None

        for key, name in SOCIAL_PATTERNS.items():
            if key in domain:
                platform = name
                break

        if not platform:
            t = (src.get("type") or "").strip()
            if t in ("Instagram", "YouTube", "TikTok", "Facebook", "X", "LinkedIn", "GitHub"):
                platform = t

        if not platform or url in seen_urls:
            continue
        seen_urls.add(url)
        platforms.add(platform)

        username = _extract_username(url, platform)
        public_name = src.get("title") or username or domain

        profiles.append({
            "platform": platform,
            "public_name": public_name[:120],
            "username": username or None,
            "url": url,
            "source": src.get("domain") or domain,
            "tag": "Posible coincidencia",
        })

    return {
        "possible_profiles": profiles[:15],
        "platforms": sorted(platforms),
        "note": (
            "Los perfiles mostrados son posibles coincidencias basadas en información pública. "
            "No se confirma que pertenezcan a la misma persona."
            if profiles else
            "No se extrajeron perfiles de redes sociales a partir de las fuentes encontradas."
        ),
    }


def compute_consistency(reverse_search: Dict, footprint: Dict) -> Dict[str, Any]:
    matches = reverse_search.get("matches_found", 0)
    profiles = footprint.get("possible_profiles", [])

    if matches == 0:
        return {
            "level": "low",
            "explanation": "No se encontraron fuentes públicas suficientes para evaluar consistencia entre apariciones de la imagen.",
        }
    if matches <= 2 and len(profiles) <= 1:
        return {
            "level": "medium",
            "explanation": "Se localizaron pocas apariciones públicas. Las fuentes disponibles muestran cierta relación temática, pero la información es limitada y no permite conclusiones firmes.",
        }
    return {
        "level": "high",
        "explanation": "Se encontraron múltiples apariciones públicas de imágenes similares o idénticas en diferentes dominios. Existe una consistencia aparente entre algunas de las fuentes, aunque no se puede confirmar que todas se refieran al mismo contexto o identidad.",
    }


def compute_evidence_score(image_analysis, reverse_search, footprint, consistency):
    score = 15
    matches = reverse_search.get("matches_found", 0)
    profiles = len(footprint.get("possible_profiles", []))
    ai_prob = image_analysis.get("ai_probability", 50)

    score += min(matches * 12, 40)
    score += min(profiles * 8, 24)
    if ai_prob < 30:
        score += 12
    elif ai_prob < 50:
        score += 6
    if consistency.get("level") == "high":
        score += 8
    elif consistency.get("level") == "medium":
        score += 4
    score = max(0, min(100, score))

    return {
        "score": score,
        "explanation": (
            "Este índice resume la cantidad y consistencia de señales técnicas y públicas "
            "encontradas durante el análisis. No determina la identidad ni la confiabilidad de una persona."
        ),
    }
