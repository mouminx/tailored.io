from __future__ import annotations

import json
import re
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
    "quantify_when_present": "Rewrite bullets to foreground any existing metrics, percentages, counts, time savings, or scale already present; do not invent numbers.",
    "ats_keywords": "Mirror relevant keywords from the job description only when supported by existing resume facts.",
    "reverse_chronological": "Keep experience and education entries in reverse-chronological order where dates permit.",
    "action_verbs": "Start bullets with strong action verbs and keep language concise.",
    "consistent_tense": "Use consistent tense by role recency (present for current roles, past for previous roles).",
    "no_first_person": "Avoid first-person pronouns such as I, me, and my.",
    "stronger_impact_language": "Amplify phrasing for strongest achievements and expand high-value bullets by a short clause while staying factual and concise.",
}

DEFAULT_TEMPLATE_SECTIONS = [
    TemplateSection(key="summary", title="Summary", kind="summary"),
    TemplateSection(key="skills", title="Skills", kind="skills"),
    TemplateSection(key="experience", title="Experience", kind="experience"),
    TemplateSection(key="projects", title="Projects", kind="projects"),
    TemplateSection(key="education", title="Education", kind="education"),
]

JOB_COMPACTION_SYSTEM_PROMPT = (
    "You are a hiring brief summarizer. Summarize the job description for resume "
    "tailoring while preserving important keywords. Return JSON only."
)

JOB_COMPACTION_SCHEMA = {
    "compressed_job": "string",
    "must_have_keywords": ["string"],
    "priority_requirements": ["string"],
}

MAX_RESUME_CHARS = 14000
MAX_JOB_CHARS = 12000


def _clamp_text(text: str, max_chars: int) -> str:
    clean = text.strip()
    if len(clean) <= max_chars:
        return clean
    return clean[:max_chars]


def _normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip(" -\t")


def _extract_heading_blocks(job_text: str) -> dict[str, list[str]]:
    headings = {
        "principal accountabilities",
        "required skills and abilities",
        "required qualifications and education",
        "preferred qualifications and education",
        "about the role",
    }
    blocks: dict[str, list[str]] = {key: [] for key in headings}
    current: str | None = None
    for raw in job_text.splitlines():
        line = _normalize_line(raw)
        if not line:
            continue
        lowered = line.lower().rstrip(":")
        if lowered in headings:
            current = lowered
            continue
        if current:
            blocks[current].append(line)
    return blocks


def _extract_keywords(job_text: str) -> list[str]:
    candidates = re.findall(
        r"\b(Symitar(?:\s+Episys)?|SQL|PowerShell|UNIX|AIX|ITIL(?:\s*v?4)?|HTML|MS Office 365|disaster recovery|core banking)\b",
        job_text,
        flags=re.IGNORECASE,
    )
    seen: set[str] = set()
    result: list[str] = []
    for item in candidates:
        normalized = _normalize_line(item)
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result[:20]


def _heuristic_compact_job_description(job_text: str) -> dict[str, object]:
    clean = _clamp_text(job_text, MAX_JOB_CHARS)
    blocks = _extract_heading_blocks(clean)
    role_headline = ""
    for line in clean.splitlines():
        normalized = _normalize_line(line)
        if not normalized:
            continue
        if len(normalized) <= 90 and not normalized.lower().startswith("job category"):
            role_headline = normalized
            break
    if not role_headline:
        role_headline = "Role overview"

    responsibilities = blocks["principal accountabilities"][:6]
    required = (
        blocks["required qualifications and education"][:4]
        + blocks["required skills and abilities"][:4]
    )

    compact_parts = [role_headline]
    if responsibilities:
        compact_parts.append("Key responsibilities: " + "; ".join(responsibilities))
    if required:
        compact_parts.append("Core requirements: " + "; ".join(required))

    compressed_job = _clamp_text(" ".join(compact_parts), 1200)
    keywords = _extract_keywords(clean)
    priorities = (responsibilities + required)[:12]

    return {
        "compressed_job": compressed_job,
        "must_have_keywords": keywords,
        "priority_requirements": priorities,
    }


def _is_weak_compaction(compacted: dict[str, object], original_text: str) -> bool:
    compressed = str(compacted.get("compressed_job", "")).strip()
    keywords = compacted.get("must_have_keywords", [])
    priorities = compacted.get("priority_requirements", [])
    if not isinstance(keywords, list):
        keywords = []
    if not isinstance(priorities, list):
        priorities = []

    # Reject very short outputs that usually collapse to just title/company.
    if len(compressed) < 140:
        return True
    # Reject outputs with little extracted structure.
    if len(keywords) < 2 and len(priorities) < 4:
        return True
    # Reject obvious title-only compactions.
    first_line = _normalize_line(original_text.splitlines()[0] if original_text else "")
    if first_line and compressed.lower() in {first_line.lower(), f"{first_line.lower()} - kitsap credit union"}:
        return True
    return False


def compact_job_description(job_text: str) -> dict[str, object]:
    clamped_job = _clamp_text(job_text, MAX_JOB_CHARS)
    prompt = (
        "Job description:\n"
        + clamped_job
        + "\n\nSummarize and return JSON with this schema:\n"
        + json.dumps(JOB_COMPACTION_SCHEMA, indent=2)
        + "\n\nRules:\n"
        + "- compressed_job must be a concise summary (4-8 sentences, max 1200 chars).\n"
        + "- Preserve key hiring requirements, responsibilities, and technical scope.\n"
        + "- Keep important terms/technologies in must_have_keywords.\n"
        + "- priority_requirements should be actionable, resume-relevant bullets.\n"
    )
    try:
        data = chat_json(JOB_COMPACTION_SYSTEM_PROMPT, prompt)
        compressed_job = str(data.get("compressed_job", "")).strip() or clamped_job
        keywords = data.get("must_have_keywords", [])
        priorities = data.get("priority_requirements", [])
        if not isinstance(keywords, list):
            keywords = []
        if not isinstance(priorities, list):
            priorities = []
        keywords = [str(item).strip() for item in keywords if str(item).strip()]
        priorities = [str(item).strip() for item in priorities if str(item).strip()]
        llm_compacted = {
            "compressed_job": _clamp_text(compressed_job, 1200),
            "must_have_keywords": keywords[:20],
            "priority_requirements": priorities[:20],
        }
        if _is_weak_compaction(llm_compacted, clamped_job):
            return _heuristic_compact_job_description(clamped_job)
        return llm_compacted
    except Exception:
        return _heuristic_compact_job_description(clamped_job)


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
    job_focus: dict[str, object],
) -> str:
    active_sections = template_sections or DEFAULT_TEMPLATE_SECTIONS
    constraints_text = ", ".join(constraints) if constraints else "none"
    constraints_rules = "\n".join(
        f"- {CONSTRAINT_RULES[key]}" for key in constraints if key in CONSTRAINT_RULES
    )
    if not constraints_rules:
        constraints_rules = "- None."
    enforcement_checks: list[str] = []
    if "quantify_when_present" in constraints:
        enforcement_checks.append(
            "- Ensure each experience/project entry surfaces metrics if those metrics exist in source text."
        )
    if "stronger_impact_language" in constraints:
        enforcement_checks.append(
            "- Strengthen wording of top-impact bullets (scope, ownership, outcome) without adding new facts."
        )
    if not enforcement_checks:
        enforcement_checks.append("- No additional enforcement checks.")
    keywords = job_focus.get("must_have_keywords", [])
    priorities = job_focus.get("priority_requirements", [])
    if not isinstance(keywords, list):
        keywords = []
    if not isinstance(priorities, list):
        priorities = []
    keywords_text = "\n".join(f"- {item}" for item in keywords) or "- None extracted."
    priorities_text = "\n".join(f"- {item}" for item in priorities) or "- None extracted."
    return (
        "Resume text:\n"
        + resume_text
        + "\n\nPrimary job summary to target:\n"
        + str(job_focus.get("compressed_job", "")).strip()
        + "\n\nOriginal job description (reference only):\n"
        + job_text
        + "\n\nMust-have keywords:\n"
        + keywords_text
        + "\n\nPriority requirements:\n"
        + priorities_text
        + "\n\nConstraints (keys):\n"
        + constraints_text
        + "\n\nConstraint rules:\n"
        + constraints_rules
        + "\n\nConstraint enforcement checks:\n"
        + "\n".join(enforcement_checks)
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
        + "- Make wording decisions from compacted job priorities and keywords.\n"
        + "- Apply multiple targeted wording improvements when alignment opportunities exist.\n"
    )


def generate_resume(
    resume_text: str,
    job_text: str,
    constraints: list[str],
    template_sections: list[TemplateSection] | None = None,
    processed_job_text: str | None = None,
) -> Resume:
    active_sections = template_sections or DEFAULT_TEMPLATE_SECTIONS
    clamped_resume = _clamp_text(resume_text, MAX_RESUME_CHARS)
    if processed_job_text:
        job_focus = compact_job_description(processed_job_text)
        original_job_for_prompt = _clamp_text(processed_job_text, 1600)
    else:
        job_focus = compact_job_description(job_text)
        original_job_for_prompt = _clamp_text(job_text, 1600)
    prompt = build_prompt(
        clamped_resume, original_job_for_prompt, constraints, active_sections, job_focus
    )
    data = chat_json(SYSTEM_PROMPT, prompt)
    resume = Resume.model_validate(data)
    if not resume.section_order:
        resume.section_order = [section.key for section in active_sections]
    return resume
