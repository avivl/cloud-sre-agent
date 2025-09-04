# gemini_sre_agent/agents/response_models.py

"""
Pydantic response models for structured agent outputs.

This module defines the response models that agents use to provide
structured, validated outputs from LLM interactions.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class TextResponse(BaseModel):
    """Basic text response model."""
    text: str = Field(..., description="The generated text")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score")


class AnalysisResponse(BaseModel):
    """Analysis response model."""
    summary: str = Field(..., description="Summary of the analysis")
    scores: Dict[str, float] = Field(..., description="Scores for each criterion")
    key_points: List[str] = Field(..., description="Key points from the analysis")
    recommendations: Optional[List[str]] = Field(None, description="Optional recommendations")


class CodeResponse(BaseModel):
    """Code generation response model."""
    code: str = Field(..., description="The generated code")
    language: str = Field(..., description="Programming language")
    explanation: str = Field(..., description="Explanation of the code")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score")
    dependencies: Optional[List[str]] = Field(None, description="Required dependencies")


class RemediationResponse(BaseModel):
    """Remediation plan response model."""
    root_cause_analysis: str = Field(..., description="Root cause analysis")
    proposed_fix: str = Field(..., description="Proposed fix description")
    code_patch: str = Field(..., description="Code patch or solution")
    priority: str = Field(..., description="Priority level (low, medium, high, critical)")
    estimated_effort: str = Field(..., description="Estimated effort required")


class TriageResponse(BaseModel):
    """Triage response model."""
    severity: str = Field(..., description="Severity level (low, medium, high, critical)")
    category: str = Field(..., description="Issue category")
    urgency: str = Field(..., description="Urgency level")
    description: str = Field(..., description="Issue description")
    suggested_actions: List[str] = Field(..., description="Suggested immediate actions")
