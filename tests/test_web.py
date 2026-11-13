"""Unit tests for FastAPI Web Dashboard endpoints."""

import pytest
from diff_lens.web.app import health, get_samples, get_sample_content, run_review, ReviewRequest, index


def test_health_endpoint():
    resp = health()
    assert resp["status"] == "ok"
    assert "DiffLens" in resp["app"]


def test_samples_endpoint():
    samples = get_samples()
    assert len(samples) >= 4
    ids = [s["id"] for s in samples]
    assert "01_auth_sql_injection" in ids
    assert "02_payment_race_condition" in ids


def test_sample_content_endpoint():
    data = get_sample_content("01_auth_sql_injection")
    assert data["id"] == "01_auth_sql_injection"
    assert "diff --git" in data["content"]


def test_review_endpoint():
    sample_diff = """diff --git a/vuln.py b/vuln.py
--- a/vuln.py
+++ b/vuln.py
@@ -1,3 +1,6 @@
+def testFunc(user):
+    cursor.execute(f"SELECT * FROM users WHERE id = '{user}'")
+    return True
"""
    req = ReviewRequest(diff_text=sample_diff)
    report = run_review(req)
    assert report.summary is not None
    assert len(report.findings) > 0
    categories = [f.category.value for f in report.findings]
    assert "RISK" in categories


def test_ui_index_endpoint():
    html_resp = index()
    assert "DiffLens" in html_resp.body.decode("utf-8")
