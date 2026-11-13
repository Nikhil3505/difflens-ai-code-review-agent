"""Unit tests for CodeReviewAgent."""

import os
import pytest
from diff_lens.agent import CodeReviewAgent
from diff_lens.models import ReviewCategory, Verdict


def test_agent_review_auth_diff():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    diff_path = os.path.join(base_dir, "samples", "01_auth_sql_injection.diff")
    repo_dir = os.path.join(base_dir, "samples", "dummy_repo")

    agent = CodeReviewAgent(repo_root=repo_dir)
    report = agent.review_file(diff_path)

    assert report.target_source.startswith("file:")
    assert len(report.findings) > 0
    assert report.summary.verdict == Verdict.REQUEST_CHANGES

    categories = {f.category for f in report.findings}
    # Expect risks (SQLi / MD5) and style or missing tests
    assert ReviewCategory.RISK in categories

    # Verify tool calls were audited
    assert len(report.tool_calls) > 0
    tool_names = [tc.tool_name for tc in report.tool_calls]
    assert "inspect_file_context" in tool_names
    assert "inspect_test_coverage" in tool_names


def test_agent_review_payment_diff():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    diff_path = os.path.join(base_dir, "samples", "02_payment_race_condition.diff")

    agent = CodeReviewAgent()
    report = agent.review_file(diff_path)

    categories = {f.category for f in report.findings}
    assert ReviewCategory.BUG in categories
    assert ReviewCategory.RISK in categories


def test_agent_review_checkout_diff():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    diff_path = os.path.join(base_dir, "samples", "03_checkout_missing_tests.diff")

    agent = CodeReviewAgent()
    report = agent.review_file(diff_path)

    categories = {f.category for f in report.findings}
    assert ReviewCategory.BUG in categories
    assert ReviewCategory.TEST in categories

