"""Data models and schemas for DiffLens AI Code Review Agent."""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ReviewCategory(str, Enum):
    """The four required core feedback categories."""
    BUG = "BUG"
    RISK = "RISK"
    TEST = "TEST"
    STYLE = "STYLE"


class Severity(str, Enum):
    """Severity ratings for code review findings."""
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    INFO = "INFO"


class Verdict(str, Enum):
    """Overall review decision."""
    APPROVED = "APPROVED"
    NEEDS_DISCUSSION = "NEEDS_DISCUSSION"
    REQUEST_CHANGES = "REQUEST_CHANGES"


class DiffLine(BaseModel):
    """Represents an individual line in a unified diff hunk."""
    type: str  # '+', '-', ' '
    content: str
    old_lineno: Optional[int] = None
    new_lineno: Optional[int] = None


class DiffHunk(BaseModel):
    """A hunk representing a contiguous set of changed and context lines."""
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    header: str
    lines: List[DiffLine] = Field(default_factory=list)


class FileDiff(BaseModel):
    """Represents all changes to a single file in a diff."""
    old_path: str
    new_path: str
    change_type: str = "modified"  # modified, added, deleted, renamed
    hunks: List[DiffHunk] = Field(default_factory=list)
    added_lines_count: int = 0
    deleted_lines_count: int = 0


class ParsedDiff(BaseModel):
    """Complete parsed diff containing multiple files."""
    files: List[FileDiff] = Field(default_factory=list)
    raw_diff: str = ""
    total_added: int = 0
    total_deleted: int = 0


class ToolCallRecord(BaseModel):
    """Audit log of a tool invocation made by the agent during review."""
    step: int
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    observation: str
    reasoning: Optional[str] = None


class Finding(BaseModel):
    """Structured code review finding."""
    id: str
    category: ReviewCategory
    severity: Severity
    file: str
    line: Optional[int] = None
    title: str
    description: str
    impact: Optional[str] = None
    suggestion: str
    suggested_patch: Optional[str] = None
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)


class ReviewSummary(BaseModel):
    """High-level summary of review results."""
    total_findings: int = 0
    bugs_count: int = 0
    risks_count: int = 0
    missing_tests_count: int = 0
    style_count: int = 0
    verdict: Verdict = Verdict.APPROVED
    executive_summary: str = ""


class ReviewReport(BaseModel):
    """The complete structured review output returned by the agent."""
    timestamp: str
    target_source: str
    files_reviewed: List[str] = Field(default_factory=list)
    summary: ReviewSummary
    findings: List[Finding] = Field(default_factory=list)
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    execution_time_seconds: float = 0.0
    mode: str = "agent-autonomous"

