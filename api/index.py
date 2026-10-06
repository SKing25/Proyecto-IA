"""Punto de entrada para Vercel (serverless). Reexporta la app FastAPI."""
from app.main import app  # noqa: F401  (Vercel la sirve como `api/index.py:app`)
