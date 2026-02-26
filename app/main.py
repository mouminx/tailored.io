from __future__ import annotations

import io
import os
import sys
import json
from pathlib import Path
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from weasyprint import HTML

from app.models import Resume, TemplateSection
from app.services.pdf import extract_text_from_pdf
from app.services.pipeline import compact_job_description, generate_resume


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

DEFAULT_VISUAL_OPTIONS = {
    "font": "serif",
    "density": "standard",
    "tone": "classic",
    "heading_style": "uppercase",
    "bullet_style": "dot",
    "skills_display": "chips",
    "section_divider": "none",
    "page_margin": "0_5",
}


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


def parse_visual_options(
    visual_font: str | None,
    visual_density: str | None,
    visual_tone: str | None,
    visual_heading_style: str | None,
    visual_bullet_style: str | None,
    visual_skills_display: str | None,
    visual_section_divider: str | None,
    visual_page_margin: str | None,
) -> dict[str, str]:
    font = (visual_font or DEFAULT_VISUAL_OPTIONS["font"]).strip().lower()
    density = (visual_density or DEFAULT_VISUAL_OPTIONS["density"]).strip().lower()
    tone = (visual_tone or DEFAULT_VISUAL_OPTIONS["tone"]).strip().lower()
    heading_style = (
        visual_heading_style or DEFAULT_VISUAL_OPTIONS["heading_style"]
    ).strip().lower()
    bullet_style = (
        visual_bullet_style or DEFAULT_VISUAL_OPTIONS["bullet_style"]
    ).strip().lower()
    skills_display = (
        visual_skills_display or DEFAULT_VISUAL_OPTIONS["skills_display"]
    ).strip().lower()
    section_divider = (
        visual_section_divider or DEFAULT_VISUAL_OPTIONS["section_divider"]
    ).strip().lower()
    page_margin = (
        visual_page_margin or DEFAULT_VISUAL_OPTIONS["page_margin"]
    ).strip().lower()

    if font not in {"serif", "sans_serif"}:
        font = DEFAULT_VISUAL_OPTIONS["font"]
    if density not in {"compact", "standard", "spacious"}:
        density = DEFAULT_VISUAL_OPTIONS["density"]
    if tone not in {"classic", "modern", "minimal"}:
        tone = DEFAULT_VISUAL_OPTIONS["tone"]
    if heading_style not in {"uppercase", "title_case"}:
        heading_style = DEFAULT_VISUAL_OPTIONS["heading_style"]
    if bullet_style not in {"dot", "dash", "none"}:
        bullet_style = DEFAULT_VISUAL_OPTIONS["bullet_style"]
    if skills_display not in {"chips", "inline"}:
        skills_display = DEFAULT_VISUAL_OPTIONS["skills_display"]
    if section_divider not in {"none", "subtle", "bold"}:
        section_divider = DEFAULT_VISUAL_OPTIONS["section_divider"]
    if page_margin not in {"0_25", "0_5", "0_75"}:
        page_margin = DEFAULT_VISUAL_OPTIONS["page_margin"]
    return {
        "font": font,
        "density": density,
        "tone": tone,
        "heading_style": heading_style,
        "bullet_style": bullet_style,
        "skills_display": skills_display,
        "section_divider": section_divider,
        "page_margin": page_margin,
    }


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


@app.post("/process-job")
async def process_job_description(job_text: str = Form(...)):
    result = compact_job_description(job_text)
    return JSONResponse(result)


@app.post("/generate")
async def generate_resume_pdf(
    request: Request,
    resume: UploadFile = File(...),
    job_text: str = Form(...),
    job_text_compacted: str | None = Form(default=None),
    constraints: list[str] | None = Form(default=None),
    section_template_json: str | None = Form(default=None),
    visual_font: str | None = Form(default=None),
    visual_density: str | None = Form(default=None),
    visual_tone: str | None = Form(default=None),
    visual_heading_style: str | None = Form(default=None),
    visual_bullet_style: str | None = Form(default=None),
    visual_skills_display: str | None = Form(default=None),
    visual_section_divider: str | None = Form(default=None),
    visual_page_margin: str | None = Form(default=None),
):
    pdf_bytes = await resume.read()
    resume_text = extract_text_from_pdf(pdf_bytes)
    template_sections = parse_template_sections(section_template_json)
    visual_options = parse_visual_options(
        visual_font,
        visual_density,
        visual_tone,
        visual_heading_style,
        visual_bullet_style,
        visual_skills_display,
        visual_section_divider,
        visual_page_margin,
    )

    tailored_resume = generate_resume(
        resume_text,
        job_text,
        constraints or [],
        template_sections,
        job_text_compacted,
    )
    render_sections = build_render_sections(tailored_resume, template_sections)
    html = templates.get_template("resume.html").render(
        {
            "resume": tailored_resume,
            "render_sections": render_sections,
            "visual": visual_options,
        }
    )

    pdf = HTML(string=html).write_pdf()
    filename = "tailored_resume.pdf"

    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
