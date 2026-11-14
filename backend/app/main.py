"""GlucoTrack API.

Run from backend/:
    uvicorn app.main:app --reload
Interactive docs: http://localhost:8000/docs
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.routers import patients

# Comma-separated list of frontend origins; default is the Vite dev server.
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

app = FastAPI(title="GlucoTrack API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

# One router per resource; add new ones here.
app.include_router(patients.router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}
