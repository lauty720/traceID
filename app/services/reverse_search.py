"""
Reverse Image Search — SerpAPI Google Lens.
Falls back to demo when not configured.
"""

from typing import Dict, Any, List, Optional
import httpx
from urllib.parse import urlparse
from app.core.config import settings
from app.services.demo_data import generate_demo_analysis


DOMAIN_TYPES = {
    "pinterest.com": "Pinterest",
    "instagram.com": "Instagram",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "facebook.com": "Facebook",
    "fb.com": "Facebook",
    "twitter.com": "X",
    "x.com": "X",
    "tiktok.com": "TikTok",
    "linkedin.com": "LinkedIn",
    "github.com": "GitHub",
    "reddit.com": "Reddit",
    "flickr.com": "Flickr",
}


def _site_type(domain: str) -> str:
    d = (domain or "").lower()
    for key, label in DOMAIN_TYPES.items():
        if key in d:
            return label
    if any(x in d for x in ("news", "diario", "times", "bbc", "cnn")):
        return "Noticias"
    if any(x in d for x in ("blog", "medium", "substack")):
        return "Blog"
    return "Sitio web"


def _domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc or url
    except Exception:
        return url


async def reverse_image_search(image_path: str, image_bytes: Optional[bytes] = None) -> Dict[str, Any]:
    if settings.REVERSE_SEARCH_API_KEY and settings.REVERSE_SEARCH_API_URL:
        try:
            return await _call_serpapi_google_lens(image_path, image_bytes)
        except Exception as e:
            print(f"[Reverse Search] Real API failed: {e}. Using simulation.")

    demo = generate_demo_analysis(seed=image_path or "fallback")
    return demo["reverse_search"]


async def _upload_temp_image(image_path: str, image_bytes: Optional[bytes] = None) -> str:
    """Upload to 0x0.st so SerpAPI can fetch a public URL."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        if image_bytes:
            files = {"file": ("image.jpg", image_bytes, "image/jpeg")}
        else:
            with open(image_path, "rb") as f:
                content = f.read()
            files = {"file": ("image.jpg", content, "image/jpeg")}
        resp = await client.post("https://0x0.st", files=files)
        resp.raise_for_status()
        url = resp.text.strip()
        if not url.startswith("http"):
            raise RuntimeError(f"Temp upload failed: {url}")
        return url


async def _call_serpapi_google_lens(image_path: str, image_bytes: Optional[bytes] = None) -> Dict[str, Any]:
    api_key = settings.REVERSE_SEARCH_API_KEY.strip()
    base_url = (settings.REVERSE_SEARCH_API_URL or "https://serpapi.com/search").strip()

    params: Dict[str, Any] = {
        "engine": "google_lens",
        "api_key": api_key,
        "hl": "es",
    }

    if image_path and str(image_path).startswith(("http://", "https://")):
        params["url"] = image_path
    else:
        params["url"] = await _upload_temp_image(image_path, image_bytes)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()

    if data.get("error"):
        raise RuntimeError(data["error"])

    sources: List[Dict[str, Any]] = []

    for item in (data.get("visual_matches") or []):
        link = item.get("link") or item.get("source") or ""
        if not link:
            continue
        domain = _domain_from_url(link)
        sources.append({
            "domain": domain,
            "title": item.get("title") or domain,
            "url": link,
            "type": _site_type(domain),
            "match_type": "exact" if item.get("exact_match") else "partial",
            "date": None,
            "thumbnail": item.get("thumbnail"),
        })

    for item in (data.get("image_sources") or []):
        link = item.get("link") or item.get("source") or ""
        if not link:
            continue
        domain = _domain_from_url(link)
        sources.append({
            "domain": domain,
            "title": item.get("title") or domain,
            "url": link,
            "type": _site_type(domain),
            "match_type": "partial",
            "date": None,
            "thumbnail": item.get("thumbnail"),
        })

    seen = set()
    unique = []
    for s in sources:
        if s["url"] not in seen:
            seen.add(s["url"])
            unique.append(s)

    note = None
    if not unique:
        note = (
            "No se encontraron coincidencias indexadas. "
            "Esto no significa que la imagen sea original. "
            "Puede existir en sitios que el buscador no haya indexado."
        )

    return {
        "matches_found": len(unique),
        "sources": unique[:20],
        "note": note,
        "provider": "serpapi_google_lens",
    }
