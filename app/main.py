from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from weasyprint import HTML

from app.services.pdf import extract_text_from_pdf
from app.services.pipeline import generate_resume


def _resource_dir() -> Path:
    # PyInstaller one-file apps unpack assets under _MEIPASS at runtime.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


BASE_DIR = _resource_dir()
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI()
app.mount("/static", StaticFiles(directory=os.fspath(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=os.fspath(TEMPLATES_DIR))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/generate")
async def generate_resume_pdf(
    request: Request,
    resume: UploadFile = File(...),
    job_text: str = Form(...),
    constraints: list[str] | None = Form(default=None),
):
    pdf_bytes = await resume.read()
    resume_text = extract_text_from_pdf(pdf_bytes)

    tailored_resume = generate_resume(resume_text, job_text, constraints or [])
    html = templates.get_template("resume.html").render({"resume": tailored_resume})

    pdf = HTML(string=html).write_pdf()
    filename = "tailored_resume.pdf"

    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
