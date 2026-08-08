"""
Demo data generators for TraceID.
All data is clearly fictional and marked as demonstration.
No real persons or private information is used.
"""

from typing import Dict, Any
import random
from datetime import datetime, timedelta


def generate_demo_analysis(seed: str = "") -> Dict[str, Any]:
    """Generate realistic but clearly fictional demo analysis results."""
    random.seed(hash(seed) % (2**32) if seed else None)

    ai_prob = random.choice([12, 18, 27, 35, 48, 62, 71, 83, 91])
    confidence = "low" if ai_prob < 30 else ("medium" if ai_prob < 70 else "high")

    explanations = {
        "low": "El análisis visual no detectó patrones fuertes asociados a generación sintética. Las texturas y el ruido de imagen son compatibles con una fotografía convencional. Este resultado no descarta manipulación posterior.",
        "medium": "Se observaron algunas características visuales que pueden aparecer tanto en fotografías reales como en imágenes generadas o editadas. La confianza del detector es moderada. Se recomienda contrastar con otras fuentes.",
        "high": "El sistema identificó múltiples señales compatibles con contenido generado o fuertemente manipulado mediante IA (artefactos de textura, inconsistencias de iluminación, patrones repetitivos). Este resultado no constituye una prueba definitiva y puede contener falsos positivos.",
    }

    # Fake public sources (clearly fictional domains)
    possible_sources = [
        {
            "domain": "demo-gallery.example",
            "title": "Colección de imágenes de demostración - Galería pública",
            "url": "https://demo-gallery.example/item/traceid-demo-001",
            "type": "Sitio web",
            "match_type": "exact",
            "date": (datetime.now() - timedelta(days=random.randint(30, 800))).strftime("%Y-%m-%d"),
            "thumbnail": None,
        },
        {
            "domain": "pinterest.com",
            "title": "Tablero público de ejemplo - Imágenes de referencia",
            "url": "https://www.pinterest.com/demo_user/tablero-ejemplo/",
            "type": "Pinterest",
            "match_type": "partial",
            "date": (datetime.now() - timedelta(days=random.randint(10, 400))).strftime("%Y-%m-%d"),
            "thumbnail": None,
        },
        {
            "domain": "youtube.com",
            "title": "Video de demostración - Contenido educativo de ciberseguridad",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ_demo",
            "type": "YouTube",
            "match_type": "partial",
            "date": (datetime.now() - timedelta(days=random.randint(60, 600))).strftime("%Y-%m-%d"),
            "thumbnail": None,
        },
        {
            "domain": "blog.ejemplo-educativo.org",
            "title": "Artículo sobre huella digital pública - Caso de estudio",
            "url": "https://blog.ejemplo-educativo.org/huella-digital-caso",
            "type": "Blog",
            "match_type": "exact",
            "date": (datetime.now() - timedelta(days=random.randint(100, 900))).strftime("%Y-%m-%d"),
            "thumbnail": None,
        },
        {
            "domain": "news.demo-source.net",
            "title": "Reportaje de demostración sobre identidad digital",
            "url": "https://news.demo-source.net/articulo-demo-2024",
            "type": "Noticias",
            "match_type": "partial",
            "date": (datetime.now() - timedelta(days=random.randint(5, 200))).strftime("%Y-%m-%d"),
            "thumbnail": None,
        },
    ]

    num_matches = random.randint(0, 4)
    sources = random.sample(possible_sources, k=min(num_matches, len(possible_sources))) if num_matches > 0 else []

    # Fake public profiles (fictional)
    possible_profiles = [
        {
            "platform": "Instagram",
            "public_name": "Cuenta de demostración educativa",
            "username": "@demo_edu_account",
            "url": "https://www.instagram.com/demo_edu_account/",
            "source": "demo-gallery.example",
            "tag": "Posible coincidencia",
        },
        {
            "platform": "YouTube",
            "public_name": "Canal Educativo Demo",
            "username": "@CanalEduDemo",
            "url": "https://www.youtube.com/@CanalEduDemo",
            "source": "youtube.com",
            "tag": "Posible coincidencia",
        },
        {
            "platform": "X",
            "public_name": "Perfil público de ejemplo",
            "username": "@ejemplo_publico",
            "url": "https://x.com/ejemplo_publico",
            "source": "blog.ejemplo-educativo.org",
            "tag": "Posible coincidencia",
        },
        {
            "platform": "GitHub",
            "public_name": "Proyecto educativo open-source",
            "username": "demo-traceid-project",
            "url": "https://github.com/demo-traceid-project",
            "source": "blog.ejemplo-educativo.org",
            "tag": "Posible coincidencia",
        },
    ]

    profiles = []
    if sources:
        profiles = random.sample(possible_profiles, k=min(random.randint(0, 3), len(possible_profiles)))

    # Consistency
    if len(sources) == 0:
        consistency_level = "low"
        consistency_explanation = "No se encontraron fuentes públicas suficientes para evaluar consistencia entre apariciones de la imagen."
    elif len(sources) <= 2:
        consistency_level = "medium"
        consistency_explanation = "Se localizaron pocas apariciones públicas. Las fuentes disponibles muestran cierta relación temática, pero la información es limitada y no permite conclusiones firmes."
    else:
        consistency_level = "high"
        consistency_explanation = "Se encontraron múltiples apariciones públicas de imágenes similares o idénticas en diferentes dominios. Existe una consistencia aparente entre algunas de las fuentes, aunque no se puede confirmar que todas se refieran al mismo contexto o identidad."

    # Evidence score (0-100) based on signals found
    base_score = 20
    if sources:
        base_score += min(len(sources) * 12, 40)
    if profiles:
        base_score += min(len(profiles) * 8, 25)
    if ai_prob < 40:
        base_score += 10
    evidence_score = min(base_score + random.randint(-5, 10), 95)

    warnings = []
    if ai_prob >= 70:
        warnings.append({
            "level": "red",
            "message": "El detector encontró una alta probabilidad de generación o manipulación mediante IA.",
        })
    if ai_prob >= 40 and ai_prob < 70:
        warnings.append({
            "level": "yellow",
            "message": "Existen señales intermedias compatibles tanto con contenido real como con manipulación.",
        })
    if len(sources) >= 3:
        warnings.append({
            "level": "yellow",
            "message": "La imagen aparece en múltiples sitios sin una fuente original claramente identificable.",
        })
    if len(sources) >= 1 and any(s.get("match_type") == "partial" for s in sources):
        warnings.append({
            "level": "yellow",
            "message": "Existen diferencias visuales entre algunas de las coincidencias encontradas.",
        })
    if any((datetime.now() - datetime.strptime(s["date"], "%Y-%m-%d")).days > 365 for s in sources if s.get("date")):
        warnings.append({
            "level": "green",
            "message": "La imagen aparece en fuentes públicas desde hace varios años.",
        })
    if not sources:
        warnings.append({
            "level": "yellow",
            "message": "No se encontraron coincidencias indexadas. Esto no implica que la imagen sea original.",
        })

    summary = (
        "DATOS DE DEMOSTRACIÓN. "
        "El análisis de demostración encontró indicios compatibles con una fotografía "
        + ("posiblemente generada o manipulada. " if ai_prob >= 60 else "aparentemente convencional. ")
        + f"Se localizaron {len(sources)} aparición(es) pública(s) de la imagen o de variantes similares. "
        + (f"También se identificaron {len(profiles)} perfil(es) o canal(es) públicos que podrían estar relacionados según las fuentes. " if profiles else "")
        + "Sin embargo, la información disponible no permite confirmar que todos los perfiles o apariciones pertenezcan al mismo contexto o persona. "
        "Los resultados de esta demostración son ficticios y orientativos."
    )

    return {
        "is_demo": True,
        "image_analysis": {
            "ai_probability": ai_prob,
            "confidence": confidence,
            "explanation": explanations[confidence],
            "warning": "Este resultado puede contener falsos positivos y falsos negativos. No constituye una prueba definitiva de autenticidad o manipulación.",
        },
        "reverse_search": {
            "matches_found": len(sources),
            "sources": sources,
            "note": "Si no se encontraron coincidencias, esto no significa que la imagen sea original. Puede existir en sitios no indexados por el buscador." if not sources else None,
        },
        "public_footprint": {
            "possible_profiles": profiles,
            "platforms": list({p["platform"] for p in profiles}),
            "note": "Los perfiles mostrados son posibles coincidencias basadas en información pública. No se confirma que pertenezcan a la misma persona.",
        },
        "consistency": {
            "level": consistency_level,
            "explanation": consistency_explanation,
        },
        "evidence_score": {
            "score": evidence_score,
            "explanation": "Este índice resume la cantidad y consistencia de señales técnicas y públicas encontradas durante el análisis. No determina la identidad ni la confiabilidad de una persona.",
        },
        "summary": summary,
        "warnings": warnings,
    }