from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.api.routes import router, limiter

app = FastAPI(
    title="TraceID API",
    description="Herramienta educativa de ciberseguridad para verificar autenticidad de imágenes y analizar su huella pública.",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS abierto para Netlify + cualquier origen (proyecto educativo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"[Global] Unhandled: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor. Intentá nuevamente más tarde."},
    )


app.include_router(router)


@app.get("/")
async def root():
    return {
        "name": "TraceID",
        "tagline": "Verificá. Analizá. Conocé tu huella digital.",
        "status": "running",
        "demo_mode": settings.is_demo_mode,
    }
