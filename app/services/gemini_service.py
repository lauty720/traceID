"""
Google Gemini integration for report generation and result interpretation.
Falls back to template-based summary when no API key is present.
"""

from typing import Dict, Any, Optional
import json
from app.core.config import settings


async def generate_analysis_report(
    image_analysis: Dict[str, Any],
    reverse_search: Dict[str, Any],
    public_footprint: Dict[str, Any],
    consistency: Dict[str, Any],
    evidence_score: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Use Gemini to produce a neutral summary and refined warnings.
    If no key is available, returns a deterministic template summary.
    """
    if not settings.GEMINI_API_KEY:
        return _template_summary(
            image_analysis, reverse_search, public_footprint, consistency, evidence_score
        )

    try:
        return await _call_gemini(
            image_analysis, reverse_search, public_footprint, consistency, evidence_score
        )
    except Exception as e:
        print(f"[Gemini] API call failed: {e}. Using template summary.")
        return _template_summary(
            image_analysis, reverse_search, public_footprint, consistency, evidence_score
        )


def _template_summary(
    image_analysis: Dict,
    reverse_search: Dict,
    public_footprint: Dict,
    consistency: Dict,
    evidence_score: Dict,
) -> Dict[str, Any]:
    ai_prob = image_analysis.get("ai_probability", 0)
    matches = reverse_search.get("matches_found", 0)
    profiles = public_footprint.get("possible_profiles", [])

    summary_parts = []
    if ai_prob >= 70:
        summary_parts.append(
            "El detector de autenticidad encontró indicios compatibles con contenido generado o fuertemente manipulado mediante IA."
        )
    elif ai_prob >= 40:
        summary_parts.append(
            "El análisis de autenticidad mostró señales intermedias; la imagen podría ser real o haber sido editada."
        )
    else:
        summary_parts.append(
            "El análisis visual no detectó patrones fuertes asociados a generación sintética."
        )

    if matches == 0:
        summary_parts.append(
            "No se localizaron coincidencias públicas indexadas de esta imagen. Esto no implica que la imagen sea original."
        )
    else:
        summary_parts.append(
            f"Se localizaron {matches} aparición(es) pública(s) de la imagen o de variantes similares en Internet."
        )

    if profiles:
        summary_parts.append(
            f"A partir de las fuentes públicas se identificaron {len(profiles)} perfil(es) o canal(es) que podrían estar relacionados. "
            "No se puede confirmar que pertenezcan a la misma persona o contexto."
        )
    else:
        summary_parts.append(
            "No se extrajeron perfiles públicos adicionales a partir de las fuentes encontradas."
        )

    summary_parts.append(
        "Toda la información presentada es orientativa y se basa únicamente en datos públicamente accesibles. "
        "Los resultados no constituyen una identificación definitiva."
    )

    return {
        "summary": " ".join(summary_parts),
        "warnings": [],  # warnings are already generated upstream
    }


async def _call_gemini(
    image_analysis: Dict,
    reverse_search: Dict,
    public_footprint: Dict,
    consistency: Dict,
    evidence_score: Dict,
) -> Dict[str, Any]:
    """
    Call Google Gemini to interpret the structured results and produce a neutral summary.
    """
    import google.generativeai as genai

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""
Eres un analista de ciberseguridad educativo. Debes generar un resumen NEUTRAL y PROBABILÍSTICO
a partir de los siguientes resultados de análisis de una imagen. 

REGLAS OBLIGATORIAS:
- Usa siempre lenguaje probabilístico: "posible", "aparentemente", "indicios compatibles", "no se puede confirmar".
- NUNCA afirmes con certeza que dos perfiles pertenecen a la misma persona.
- NUNCA uses reconocimiento facial ni intentes identificar personas.
- Solo te basas en información pública ya obtenida.
- El resumen debe ser claro, profesional y educativo.
- Responde SOLO con un JSON válido que tenga las claves: "summary" (string) y "warnings" (array de objetos con "level" y "message").

Datos de entrada:
{json.dumps({
    "image_analysis": image_analysis,
    "reverse_search": reverse_search,
    "public_footprint": public_footprint,
    "consistency": consistency,
    "evidence_score": evidence_score,
}, ensure_ascii=False, indent=2)}
"""

    response = model.generate_content(prompt)
    text = response.text.strip()

    # Extract JSON from possible markdown fences
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    data = json.loads(text)
    return {
        "summary": data.get("summary", ""),
        "warnings": data.get("warnings", []),
    }