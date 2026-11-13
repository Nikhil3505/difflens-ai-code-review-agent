"""Unit tests for CLI formatters."""

from diff_lens.models import (
    ReviewReport,
    ReviewSummary,
    Finding,
    ReviewCategory,
    Severity,
    Verdict,
    ToolCallRecord,
)
from diff_lens.cli import format_console_report, format_markdown_report


def test_cli_formatters():
    report = ReviewReport(
        timestamp="2026-11-13T10:00:00",
        target_source="test.diff",
        files_reviewed=["auth.py"],
        summary=ReviewSummary(
            total_findings=2,
            bugs_count=1,
            risks_count=1,
            missing_tests_count=0,
            style_count=0,
            verdict=Verdict.REQUEST_CHANGES,
            executive_summary="Changes requested due to security bugs.",
        ),
        findings=[
            Finding(
                id="FINDING-001",
                category=ReviewCategory.RISK,
                severity=Severity.CRITICAL,
                file="auth.py",
                line=25,
                title="SQL Injection",
                description="Query contains f-string",
                suggestion="Use parameterized query",
            ),
            Finding(
                id="FINDING-002",
                category=ReviewCategory.BUG,
                severity=Severity.MAJOR,
                file="auth.py",
                line=30,
                title="Logic error",
                description="Incorrect condition",
                suggestion="Fix condition",
            ),
        ],
        tool_calls=[
            ToolCallRecord(
                step=1,
                tool_name="inspect_test_coverage",
                observation="No tests",
                reasoning="Check tests",
            )
        ],
        execution_time_seconds=0.05,
        mode="test-mode",
    )

    console_out = format_console_report(report)
    assert "DiffLens AI Code Review Agent" in console_out
    assert "Built by Nikhil Patil" in console_out
    assert "REQUEST_CHANGES" in console_out
    assert "SQL Injection" in console_out

    md_out = format_markdown_report(report)
    assert "# 🔍 DiffLens AI Code Review Report" in md_out
    assert "REQUEST CHANGES" in md_out
    assert "### 📝 Findings & Feedback" in md_out

