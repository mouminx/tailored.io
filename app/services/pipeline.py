from __future__ import annotations

import json
from app.models import Resume, TemplateSection
from app.services.ollama import chat_json

SYSTEM_PROMPT = """You are a resume assistant. You MUST only use facts that already exist in the resume text. Do not invent employers, titles, dates, degrees, or achievements. Make minimal edits needed to better match the job description, preserving the original tone and details. Output JSON only, conforming to the schema provided."""

SCHEMA = {
    "name": "string",
    "contact": ["string"],
    "summary": "string",
    "skills": ["string"],
    "experience": [
        {
            "role": "string",
            "company": "string",
            "location": "string",
            "dates": "string",
            "bullets": ["string"],
        }
    ],
    "education": [
        {
            "school": "string",
            "degree": "string",
            "dates": "string",
            "details": ["string"],
        }
    ],
    "projects": [
        {
            "name": "string",
            "details": ["string"],
        }
    ],
    "custom_sections": [
        {
            "key": "string",
            "title": "string",
            "items": ["string"],
        }
    ],
    "section_order": ["string"],
}

CONSTRAINT_RULES = {
    "one_page": "Keep overall length to about one page; prefer trimming or tightening over adding content.",
    "no_new_facts": "Do not add any facts that are not already in the resume text.",
    "preserve_format": "Preserve the existing section order and headings.",
    "tight_bullets": "Keep bullets short; avoid wrapping to more than ~2 lines.",
    "quantify_when_present": "Emphasize or surface metrics that already exist; do not invent numbers.",
    "ats_keywords": "Mirror relevant keywords from the job description only when supported by existing resume facts.",
    "reverse_chronological": "Keep experience and education entries in reverse-chronological order where dates permit.",
    "action_verbs": "Start bullets with strong action verbs and keep language concise.",
    "consistent_tense": "Use consistent tense by role recency (present for current roles, past for previous roles).",
    "no_first_person": "Avoid first-person pronouns such as I, me, and my.",
}

DEFAULT_TEMPLATE_SECTIONS = [
    TemplateSection(key="summary", title="Summary", kind="summary"),
    TemplateSection(key="skills", title="Skills", kind="skills"),
    TemplateSection(key="experience", title="Experience", kind="experience"),
    TemplateSection(key="projects", title="Projects", kind="projects"),
    TemplateSection(key="education", title="Education", kind="education"),
]


def _template_sections_text(template_sections: list[TemplateSection]) -> str:
    if not template_sections:
        return "- Default resume structure."
    lines = []
    for section in template_sections:
        lines.append(
            f"- key={section.key}, title={section.title}, kind={section.kind}"
        )
    return "\n".join(lines)


def build_prompt(
    resume_text: str,
    job_text: str,
    constraints: list[str],
    template_sections: list[TemplateSection],
) -> str:
    active_sections = template_sections or DEFAULT_TEMPLATE_SECTIONS
    constraints_text = ", ".join(constraints) if constraints else "none"
    constraints_rules = "\n".join(
        f"- {CONSTRAINT_RULES[key]}" for key in constraints if key in CONSTRAINT_RULES
    )
    if not constraints_rules:
        constraints_rules = "- None."
    return (
        "Resume text:\n"
        + resume_text
        + "\n\nJob description:\n"
        + job_text
        + "\n\nConstraints (keys):\n"
        + constraints_text
        + "\n\nConstraint rules:\n"
        + constraints_rules
        + "\n\nRequested resume template sections:\n"
        + _template_sections_text(active_sections)
        + "\n\nReturn JSON with this schema:\n"
        + json.dumps(SCHEMA, indent=2)
        + "\n\nRules:\n"
        + "- Preserve all facts; do not add new ones.\n"
        + "- Make minimal edits, only where relevant to the job.\n"
        + "- Keep bullets concise and measurable if already present.\n"
        + "- Fill section_order with the keys in requested template order.\n"
        + "- For unknown/custom template keys, populate custom_sections entries.\n"
        + "- Keep custom_sections keys/titles aligned with requested template sections.\n"
    )


def generate_resume(
    resume_text: str,
    job_text: str,
    constraints: list[str],
    template_sections: list[TemplateSection] | None = None,
) -> Resume:
    active_sections = template_sections or DEFAULT_TEMPLATE_SECTIONS
    prompt = build_prompt(resume_text, job_text, constraints, active_sections)
    data = chat_json(SYSTEM_PROMPT, prompt)
    resume = Resume.model_validate(data)
    if not resume.section_order:
        resume.section_order = [section.key for section in active_sections]
    return resume
