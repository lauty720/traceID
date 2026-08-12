"""
Reverse Image Search — SerpAPI Google Lens / Google Reverse Image.
On failure returns empty results (never fake demo sources).
"""

from typing import Dict, Any, List, Optional
import httpx
from urllib.parse import urlparse
from app.core.config import settings


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


def _empty_result(note: str) -> Dict[str, Any]:
    return {
        "matches_found": 0,
        "sources": [],
        "note": note,
        "provider": "serpapi_google_lens",
    }


async def reverse_image_search(image_path: str, image_bytes: Optional[bytes] = None) -> Dict[str, Any]:
    if not (settings.REVERSE_SEARCH_API_KEY and settings.REVERSE_SEARCH_API_URL):
        return _empty_result(
            "Búsqueda inversa no configurada. No se consultó ningún motor de búsqueda."
        )

    try:
        return await _call_serpapi(image_path, image_bytes)
    except Exception as e:
        print(f"[Reverse Search] Real API failed: {e}")
        return _empty_result(
            "No se pudo completar la búsqueda inversa en este momento. "
            "Esto no implica que la imagen sea original ni que no exista en Internet."
        )


async def _upload_temp_image(image_bytes: bytes) -> str:
    """Publish image to a temporary public URL (SerpAPI needs a public URL)."""
    last_err = None

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        # 1) litterbox (catbox) — 1 hour
        try:
            r = await client.post(
                "https://litterbox.catbox.moe/resources/internals/api.php",
                data={"reqtype": "fileupload", "time": "1h"},
                files={"fileToUpload": ("image.jpg", image_bytes, "image/jpeg")},
            )
            if r.status_code < 400:
                url = r.text.strip()
                if url.startswith("http"):
                    return url
            last_err = f"litterbox: {r.status_code} {r.text[:200]}"
        except Exception as e:
            last_err = f"litterbox: {e}"

        # 2) catbox
        try:
            r = await client.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": ("image.jpg", image_bytes, "image/jpeg")},
            )
            if r.status_code < 400:
                url = r.text.strip()
                if url.startswith("http"):
                    return url
            last_err = f"catbox: {r.status_code} {r.text[:200]}"
        except Exception as e:
            last_err = f"catbox: {e}"

        # 3) 0x0.st
        try:
            r = await client.post(
                "https://0x0.st",
                files={"file": ("image.jpg", image_bytes, "image/jpeg")},
            )
            if r.status_code < 400:
                url = r.text.strip()
                if url.startswith("http"):
                    return url
            last_err = f"0x0: {r.status_code} {r.text[:200]}"
        except Exception as e:
            last_err = f"0x0: {e}"

        # 4) tmpfiles.org
        try:
            r = await client.post(
                "https://tmpfiles.org/api/v1/upload",
                files={"file": ("image.jpg", image_bytes, "image/jpeg")},
            )
            if r.status_code < 400:
                data = r.json()
                link = (data.get("data") or {}).get("url") or ""
                # tmpfiles returns page URL; convert to direct if possible
                if link.startswith("http"):
                    if "/tmpfiles.org/" in link and "/dl/" not in link:
                        link = link.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                    return link
            last_err = f"tmpfiles: {r.status_code} {r.text[:200]}"
        except Exception as e:
            last_err = f"tmpfiles: {e}"

    raise RuntimeError(f"No se pudo publicar imagen temporal: {last_err}")


async def _call_serpapi(image_path: str, image_bytes: Optional[bytes] = None) -> Dict[str, Any]:
    api_key = settings.REVERSE_SEARCH_API_KEY.strip()
    base_url = (settings.REVERSE_SEARCH_API_URL or "https://serpapi.com/search").strip()

    if image_bytes is None:
        with open(image_path, "rb") as f:
            image_bytes = f.read()

    if image_path and str(image_path).startswith(("http://", "https://")):
        public_url = image_path
    else:
        public_url = await _upload_temp_image(image_bytes)

    print(f"[Reverse Search] public_url={public_url}")

    data = None
    last_error = None

    async with httpx.AsyncClient(timeout=25.0) as client:
        # Engine 1: Google Lens
        try:
            r = await client.get(
                base_url,
                params={
                    "engine": "google_lens",
                    "url": public_url,
                    "api_key": api_key,
                    "hl": "es",
                },
            )
            r.raise_for_status()
            data = r.json()
            if data.get("error"):
                last_error = data["error"]
                print(f"[Reverse Search] google_lens error: {last_error}")
                data = None
            else:
                print("[Reverse Search] google_lens OK")
        except Exception as e:
            last_error = str(e)
            print(f"[Reverse Search] google_lens exception: {e}")
            data = None

        # Engine 2: Google Reverse Image
        if data is None:
            try:
                r = await client.get(
                    base_url,
                    params={
                        "engine": "google_reverse_image",
                        "image_url": public_url,
                        "api_key": api_key,
                        "hl": "es",
                    },
                )
                r.raise_for_status()
                data = r.json()
                if data.get("error"):
                    last_error = data["error"]
                    print(f"[Reverse Search] reverse_image error: {last_error}")
                    data = None
                else:
                    print("[Reverse Search] google_reverse_image OK")
            except Exception as e:
                last_error = str(e)
                print(f"[Reverse Search] reverse_image exception: {e}")
                data = None

    if not data:
        raise RuntimeError(last_error or "SerpAPI no devolvió resultados")

    sources: List[Dict[str, Any]] = []

    for key in ("visual_matches", "image_results", "image_sources", "organic_results", "inline_images"):
        for item in (data.get(key) or []):
            page = item.get("link") or item.get("source") or item.get("original") or ""
            if not page or not str(page).startswith("http"):
                continue
            domain = _domain_from_url(page)
            title = item.get("title") or item.get("source") or domain
            sources.append({
                "domain": domain,
                "title": str(title)[:200],
                "url": page,
                "type": _site_type(domain),
                "match_type": "exact" if item.get("exact_match") else "partial",
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
            "No se encontraron coincidencias indexadas en la búsqueda inversa. "
            "Esto no significa que la imagen sea original."
        )

    return {
        "matches_found": len(unique),
        "sources": unique[:20],
        "note": note,
        "provider": "serpapi_google_lens",
    }
