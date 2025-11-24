from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .llm_review import LLMReviewer
from .parser import load_analysis

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="DOCX Analyzer")

# Static mount placeholder (in case we add CSS/JS later).
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return TEMPLATES.TemplateResponse(
        "index.html",
        {
            "request": request,
            "result": None,
            "error": None,
            "default_model": "gemini-2.5-flash",
            "default_prompt": None,
        },
    )


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    file: UploadFile = File(...),
    model: str = Form("gemini-2.5-flash"),
    prompt: Optional[str] = Form(None),
):
    error = None
    result = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=True) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp.flush()
            analysis = load_analysis(tmp.name)
        reviewer = LLMReviewer(model=model)
        review_text = reviewer.review(analysis, prompt=prompt)
        result = {
            "analysis": analysis.to_dict(),
            "review": review_text,
            "model": model,
        }
    except Exception as exc:  # pragma: no cover - surface to UI
        error = str(exc)

    return TEMPLATES.TemplateResponse(
        "index.html",
        {
            "request": request,
            "result": result,
            "error": error,
            "default_model": model,
            "default_prompt": prompt,
        },
    )
