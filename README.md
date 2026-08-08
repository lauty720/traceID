# TraceID Backend

FastAPI service for image authenticity analysis and public footprint detection.

## Quick start

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
mkdir -p uploads
python run.py
```

API: http://localhost:8000  
Docs: http://localhost:8000/docs

Without API keys the service runs in **demo mode**.

## Environment

See `.env.example` for all variables.

## Adding real APIs

1. **AI Detector** → implement `_call_real_detector()` in `app/services/ai_detector.py`
2. **Reverse Search** → implement `_call_real_reverse_search()` in `app/services/reverse_search.py`
3. **Gemini** → set `GEMINI_API_KEY` (already implemented)

The rest of the pipeline stays the same.
