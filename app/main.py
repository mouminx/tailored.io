from __future__ import annotations

import io
import os
import sys
import json
from pathlib import Path
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from weasyprint import HTML

from app.models import Resume, TemplateSection
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


PRESET_SECTIONS = [
    TemplateSection(key="summary", title="Summary", kind="summary"),
    TemplateSection(key="skills", title="Skills", kind="skills"),
    TemplateSection(key="experience", title="Experience", kind="experience"),
    TemplateSection(key="projects", title="Projects", kind="projects"),
    TemplateSection(key="education", title="Education", kind="education"),
]


def parse_template_sections(section_template_json: str | None) -> list[TemplateSection]:
    if not section_template_json:
        return PRESET_SECTIONS
    try:
        raw = json.loads(section_template_json)
    except json.JSONDecodeError:
        return PRESET_SECTIONS
    if not isinstance(raw, list):
        return PRESET_SECTIONS

    sections: list[TemplateSection] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "")).strip().lower().replace(" ", "_")
        title = str(item.get("title", "")).strip()
        kind = str(item.get("kind", "custom")).strip().lower()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        sections.append(TemplateSection(key=key, title=title or key.title(), kind=kind))

    return sections or PRESET_SECTIONS


def build_render_sections(
    resume: Resume, template_sections: list[TemplateSection]
) -> list[dict]:
    by_custom_key = {section.key: section for section in resume.custom_sections}
    sections: list[dict] = []

    for section in template_sections:
        key = section.key
        if key == "summary" and resume.summary:
            sections.append({"kind": "summary", "title": section.title, "data": resume.summary})
        elif key == "skills" and resume.skills:
            sections.append({"kind": "skills", "title": section.title, "data": resume.skills})
        elif key == "experience" and resume.experience:
            sections.append({"kind": "experience", "title": section.title, "data": resume.experience})
        elif key == "projects" and resume.projects:
            sections.append({"kind": "projects", "title": section.title, "data": resume.projects})
        elif key == "education" and resume.education:
            sections.append({"kind": "education", "title": section.title, "data": resume.education})
        elif key in by_custom_key and by_custom_key[key].items:
            sections.append(
                {
                    "kind": "custom",
                    "title": section.title or by_custom_key[key].title,
                    "data": by_custom_key[key].items,
                }
            )
    return sections


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/generate")
async def generate_resume_pdf(
    request: Request,
    resume: UploadFile = File(...),
    job_text: str = Form(...),
    constraints: list[str] | None = Form(default=None),
    section_template_json: str | None = Form(default=None),
):
    pdf_bytes = await resume.read()
    resume_text = extract_text_from_pdf(pdf_bytes)
    template_sections = parse_template_sections(section_template_json)

    tailored_resume = generate_resume(
        resume_text, job_text, constraints or [], template_sections
    )
    render_sections = build_render_sections(tailored_resume, template_sections)
    html = templates.get_template("resume.html").render(
        {"resume": tailored_resume, "render_sections": render_sections}
    )

    pdf = HTML(string=html).write_pdf()
    filename = "tailored_resume.pdf"

    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
