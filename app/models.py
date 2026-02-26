from __future__ import annotations

from pydantic import BaseModel, Field


class TemplateSection(BaseModel):
    key: str = ""
    title: str = ""
    kind: str = "custom"


class Experience(BaseModel):
    role: str = ""
    company: str = ""
    location: str = ""
    dates: str = ""
    bullets: list[str] = Field(default_factory=list)


class Education(BaseModel):
    school: str = ""
    degree: str = ""
    dates: str = ""
    details: list[str] = Field(default_factory=list)


class Project(BaseModel):
    name: str = ""
    details: list[str] = Field(default_factory=list)


class CustomSection(BaseModel):
    key: str = ""
    title: str = ""
    items: list[str] = Field(default_factory=list)


class Resume(BaseModel):
    name: str = ""
    contact: list[str] = Field(default_factory=list)
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    custom_sections: list[CustomSection] = Field(default_factory=list)
    section_order: list[str] = Field(default_factory=list)
