from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl

class Materials(BaseModel):
    """Materials needed for a DIY project"""
    name: str
    quantity: Optional[str] = None
    optional: bool = False
    alternatives: List[str] = Field(default_factory=list)
    estimated_cost: Optional[float] = None

class ProjectStep(BaseModel):
    """Individual step in a DIY project"""
    step_number: int
    description: str
    time_estimate: Optional[str] = None
    tools_needed: List[str] = Field(default_factory=list)
    tips: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

class DIYProject(BaseModel):
    """Complete DIY project information"""
    url: HttpUrl
    title: str
    summary: str = Field(..., max_length=500)
    difficulty_level: str = Field(..., description="beginner/intermediate/advanced")
    materials: List[Materials]
    steps: List[ProjectStep]
    category: str
    tags: List[str] = Field(default_factory=list)
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    source_domain: str
