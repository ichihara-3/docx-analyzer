import json
import tempfile
import time
import markdown
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .llm_review import DEFAULT_USER_INSTRUCTION, LLMReviewer, get_prompt_template
from .parser import load_analysis

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# File size limit: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024

app = FastAPI(title="DOCX Analyzer")

# Mount static files
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
            "error_type": None,
            "default_model": "gemini-2.5-flash",
            "default_prompt": DEFAULT_USER_INSTRUCTION,
            "default_template": "default",
        },
    )


@app.post("/api/analyze")
async def api_analyze(
    file: UploadFile = File(...),
    model: str = Form("gemini-2.5-flash"),
    prompt: Optional[str] = Form(None),
    template: str = Form("default"),
):
    """JSON API endpoint for analysis."""
    start_time = time.time()
    
    try:
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Validate file size
        if file_size > MAX_FILE_SIZE:
            return JSONResponse(
                status_code=400,
                content={
                    "error": f"ファイルサイズが大きすぎます（{file_size / 1024 / 1024:.1f}MB）。"
                            f"上限は{MAX_FILE_SIZE / 1024 / 1024:.0f}MBです。",
                    "error_type": "file_too_large"
                }
            )
        
        # Validate file type
        if not file.filename or not file.filename.lower().endswith(".docx"):
            return JSONResponse(
                status_code=400,
                content={
                    "error": "DOCXファイルのみ対応しています。",
                    "error_type": "invalid_file_type"
                }
            )
        
        # Parse DOCX
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=True) as tmp:
            tmp.write(content)
            tmp.flush()
            try:
                analysis = load_analysis(tmp.name)
            except Exception as parse_error:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "ファイルの解析に失敗しました。ファイルが破損しているか、"
                                "正しいDOCX形式ではない可能性があります。",
                        "error_type": "parse_error"
                    }
                )
        
        # Get prompt from template if custom prompt not provided
        if not prompt or prompt.strip() == "":
            prompt = get_prompt_template(template)
        
        # LLM Review
        try:
            reviewer = LLMReviewer(model=model)
            review_text = reviewer.review(analysis, user_instruction=prompt)
        except Exception as llm_error:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "LLMレビューの実行に失敗しました。APIキーが正しく設定されているか確認してください。",
                    "error_type": "llm_error"
                }
            )
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        return JSONResponse(
            content={
                "success": True,
                "analysis": analysis.to_dict(),
                "analysis_json": json.dumps(analysis.to_dict(), ensure_ascii=False, indent=2),
                "review": review_text,
                "review_html": markdown.markdown(review_text),
                "model": model,
                "processing_time": f"{processing_time:.1f}",
                "file_size": f"{file_size / 1024:.1f}",
                "filename": file.filename,
            }
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "error": f"予期しないエラーが発生しました: {str(exc)}",
                "error_type": "unknown_error"
            }
        )


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    file: UploadFile = File(...),
    model: str = Form("gemini-2.5-flash"),
    prompt: Optional[str] = Form(None),
    template: str = Form("default"),
):
    error = None
    error_type = None
    result = None
    start_time = time.time()
    
    try:
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Validate file size
        if file_size > MAX_FILE_SIZE:
            error_type = "file_too_large"
            raise ValueError(
                f"ファイルサイズが大きすぎます（{file_size / 1024 / 1024:.1f}MB）。"
                f"上限は{MAX_FILE_SIZE / 1024 / 1024:.0f}MBです。"
            )
        
        # Validate file type
        if not file.filename or not file.filename.lower().endswith(".docx"):
            error_type = "invalid_file_type"
            raise ValueError("DOCXファイルのみ対応しています。")
        
        # Parse DOCX
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=True) as tmp:
            tmp.write(content)
            tmp.flush()
            try:
                analysis = load_analysis(tmp.name)
            except Exception as parse_error:
                error_type = "parse_error"
                raise ValueError(
                    f"ファイルの解析に失敗しました。ファイルが破損しているか、"
                    f"正しいDOCX形式ではない可能性があります。"
                ) from parse_error
        
        # Get prompt from template if custom prompt not provided
        if not prompt or prompt.strip() == "":
            prompt = get_prompt_template(template)
        
        # LLM Review
        try:
            reviewer = LLMReviewer(model=model)
            review_text = reviewer.review(analysis, user_instruction=prompt)
        except Exception as llm_error:
            error_type = "llm_error"
            raise ValueError(
                f"LLMレビューの実行に失敗しました。APIキーが正しく設定されているか確認してください。"
            ) from llm_error
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        result = {
            "analysis": analysis.to_dict(),
            "analysis_json": json.dumps(analysis.to_dict(), ensure_ascii=False, indent=2),
            "review": review_text,
            "review_html": markdown.markdown(review_text),
            "model": model,
            "processing_time": f"{processing_time:.1f}",
            "file_size": f"{file_size / 1024:.1f}",
            "filename": file.filename,
        }
    except ValueError as ve:
        error = str(ve)
    except Exception as exc:  # pragma: no cover - surface to UI
        error_type = "unknown_error"
        error = f"予期しないエラーが発生しました: {str(exc)}"

    return TEMPLATES.TemplateResponse(
        "index.html",
        {
            "request": request,
            "result": result,
            "error": error,
            "error_type": error_type,
            "default_model": model,
            "default_prompt": prompt,
            "default_template": template,
        },
    )
