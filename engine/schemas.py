from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, EmailStr

class Identity(BaseModel):
    name: str = Field(..., description="Full name of the candidate")
    email: EmailStr = Field(..., description="Email address")
    phone: str = Field(..., description="Phone number")
    linkedin: Optional[str] = None
    github: Optional[str] = None
    location: Optional[str] = None

class Experience(BaseModel):
    id: str = Field(..., description="Stable identifier for the experience")
    position: str = Field(..., description="Job title")
    company: str = Field(..., description="Company name")
    start_date: str = Field(..., description="Start date")
    end_date: str = Field(..., description="End date")
    location: Optional[str] = None
    achievements: List[str] = Field(default_factory=list, description="List of achievements/bullets")

class Project(BaseModel):
    id: str = Field(..., description="Stable identifier for the project")
    name: str = Field(..., description="Project name")
    description: Optional[str] = None
    keywords: Optional[str] = Field(None, description="Keywords separated by ·")

class Skill(BaseModel):
    name: str

class Education(BaseModel):
    degree: str
    school: str
    year: str
    specialization: Optional[str] = None
    details: Optional[str] = None
    modules: Optional[List[str]] = Field(default_factory=list)

class Language(BaseModel):
    name: str
    level: str

class CVData(BaseModel):
    """The final parsed and validated CV data structure."""
    identity: Identity
    headline: str
    summary: str
    experiences: List[Experience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    grouped_skills: Dict[str, List[Skill]] = Field(default_factory=dict)
    skills_inline: Optional[str] = None
    education: List[Education] = Field(default_factory=list)
    languages: List[Language] = Field(default_factory=list)
    hobbies: List[str] = Field(default_factory=list)
    
    # Internal fields for tracking errors or LLM metadata
    _last_error: Optional[str] = None

class JobOffer(BaseModel):
    id: Optional[str] = None
    title: str
    company: str
    location: Optional[str] = None
    description: str = ""
    url: Optional[str] = None
    matched_skills: List[str] = Field(default_factory=list)
    match_score: Optional[int] = None

class LLMExperience(BaseModel):
    id: str
    rewritten_title: str
    bullets: List[str]

class LLMProject(BaseModel):
    id: str
    rewritten_title: str
    one_line_description: str
    keywords_inline: str

class LLMCVData(BaseModel):
    headline: str
    summary: str
    experiences: List[LLMExperience] = Field(default_factory=list)
    projects: List[LLMProject] = Field(default_factory=list)
    skills_inline: Optional[str] = None

class LLMOutput(BaseModel):
    cv: LLMCVData

class LLMListOutput(BaseModel):
    items: List[str]

class CVGenState(BaseModel):
    cv_path: Optional[str] = None
    letter_path: Optional[str] = None
    letter_text: Optional[str] = None
    section_overrides: Dict[str, Any] = Field(default_factory=dict)
    section_proposal: Dict[str, Any] = Field(default_factory=dict)
    cv_data: Optional[Dict[str, Any]] = None
