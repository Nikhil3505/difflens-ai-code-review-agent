"""FastAPI Web Application for DiffLens Interactive Dashboard."""

import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

from diff_lens.agent import CodeReviewAgent
from diff_lens.models import ReviewReport

app = FastAPI(title="DiffLens Web Dashboard", version="1.0.0")

# Sample directory resolution
SAMPLES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "samples"))

SAMPLE_METADATA = [
    {
        "id": "01_auth_sql_injection",
        "title": "Auth SQL Injection & Insecure Hashing",
        "category": "Security & Logic",
        "description": "Introduces f-string query construction, MD5 password hashing, and camelCase function name without tests.",
        "filename": "01_auth_sql_injection.diff",
    },
    {
        "id": "02_payment_race_condition",
        "title": "Payment Concurrency Race Condition",
        "category": "Concurrency & Finance",
        "description": "Debit check-then-act without atomic locks, floating-point currency representation, and bare except clause.",
        "filename": "02_payment_race_condition.diff",
    },
    {
        "id": "03_checkout_missing_tests",
        "title": "Checkout Tier Boundary Bug & Missing Tests",
        "category": "Business Logic & Testing",
        "description": "Strict boundary inequality (off-by-one), missing unit tests for new tier calculation, and unhandled empty cart.",
        "filename": "03_checkout_missing_tests.diff",
    },
    {
        "id": "04_data_pipeline_leak",
        "title": "Data Pipeline Resource & Memory Leak",
        "category": "Reliability & Performance",
        "description": "Unclosed file descriptor (open without with) and unbounded whole-file .read() buffer.",
        "filename": "04_data_pipeline_leak.diff",
    },
]


class ReviewRequest(BaseModel):
    diff_text: str
    api_key: Optional[str] = None
    provider: Optional[str] = "auto"
    model: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok", "app": "DiffLens Web Dashboard"}


@app.get("/api/samples")
def get_samples():
    return SAMPLE_METADATA


@app.get("/api/samples/{sample_id}")
def get_sample_content(sample_id: str):
    target = None
    for s in SAMPLE_METADATA:
        if s["id"] == sample_id:
            target = s
            break
    if not target:
        raise HTTPException(status_code=404, detail="Sample not found")

    file_path = os.path.join(SAMPLES_DIR, target["filename"])
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File {target['filename']} not found on disk")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    return {"id": target["id"], "title": target["title"], "content": content}


@app.post("/api/review", response_model=ReviewReport)
def run_review(req: ReviewRequest):
    if not req.diff_text.strip():
        raise HTTPException(status_code=400, detail="Diff text cannot be empty.")

    agent = CodeReviewAgent(
        api_key=req.api_key,
        provider=req.provider or "auto",
        model=req.model,
    )

    try:
        report = agent.review(req.diff_text, source_label="web_dashboard")
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(content=HTML_CONTENT)


def run_server(host: str = "127.0.0.1", port: int = 8000):
    print(f"Starting DiffLens Web Dashboard at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DiffLens - Autonomous AI Code Review Agent</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0d1117;
      --card-bg: #161b22;
      --border: #30363d;
      --text: #c9d1d9;
      --text-muted: #8b949e;
      --accent: #58a6ff;
      --accent-hover: #1f6feb;
      --green: #238636;
      --green-light: #2ea043;
      --red: #da3633;
      --red-bg: rgba(218, 54, 51, 0.15);
      --yellow: #d29922;
      --purple: #bc8cff;
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-sans);
      line-height: 1.5;
      padding-bottom: 60px;
    }
    header {
      background: var(--card-bg);
      border-bottom: 1px solid var(--border);
      padding: 16px 32px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-icon {
      font-size: 26px;
    }
    .brand-name {
      font-size: 20px;
      font-weight: 700;
      color: #fff;
      letter-spacing: -0.5px;
    }
    .badge-sub {
      background: rgba(88, 166, 255, 0.15);
      color: var(--accent);
      padding: 3px 8px;
      border-radius: 12px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .header-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .btn {
      background: var(--accent);
      color: #fff;
      border: none;
      padding: 8px 18px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: background 0.15s ease;
    }
    .btn:hover { background: var(--accent-hover); }
    .btn-secondary {
      background: #21262d;
      color: var(--text);
      border: 1px solid var(--border);
    }
    .btn-secondary:hover { background: #30363d; }
    .btn-green { background: var(--green); }
    .btn-green:hover { background: var(--green-light); }
    
    .container {
      max-width: 1400px;
      margin: 24px auto;
      padding: 0 24px;
    }
    
    /* Top samples bar */
    .samples-bar {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px 18px;
      margin-bottom: 20px;
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .samples-label {
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .sample-pill {
      background: #21262d;
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 5px 14px;
      font-size: 12px;
      cursor: pointer;
      color: var(--text);
      transition: all 0.15s ease;
    }
    .sample-pill:hover, .sample-pill.active {
      background: rgba(88, 166, 255, 0.15);
      border-color: var(--accent);
      color: #fff;
    }
    
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }
    @media (max-width: 1024px) {
      .grid { grid-template-columns: 1fr; }
    }
    
    .panel {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      min-height: 650px;
    }
    .panel-header {
      background: #1c2128;
      border-bottom: 1px solid var(--border);
      padding: 12px 18px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .panel-title {
      font-size: 14px;
      font-weight: 600;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .panel-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    
    textarea#diff-input {
      flex: 1;
      width: 100%;
      height: 100%;
      min-height: 520px;
      background: #0d1117;
      border: none;
      color: #e6edf3;
      font-family: var(--font-mono);
      font-size: 12.5px;
      line-height: 1.6;
      padding: 16px;
      resize: vertical;
      outline: none;
    }
    
    .options-bar {
      padding: 10px 16px;
      background: #161b22;
      border-top: 1px solid var(--border);
      display: flex;
      gap: 12px;
      align-items: center;
      font-size: 12px;
    }
    .options-bar input {
      background: #0d1117;
      border: 1px solid var(--border);
      color: #fff;
      padding: 5px 10px;
      border-radius: 4px;
      font-size: 12px;
      width: 200px;
    }

    /* Output Panel */
    .output-container {
      padding: 16px;
      overflow-y: auto;
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .placeholder-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 480px;
      color: var(--text-muted);
      text-align: center;
      gap: 12px;
    }
    .placeholder-state svg {
      width: 56px;
      height: 56px;
      opacity: 0.3;
    }
    
    /* Summary Card */
    .verdict-banner {
      border-radius: 8px;
      padding: 16px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-left: 5px solid;
    }
    .verdict-APPROVED {
      background: rgba(46, 160, 67, 0.12);
      border-color: var(--green);
    }
    .verdict-NEEDS_DISCUSSION {
      background: rgba(210, 153, 34, 0.12);
      border-color: var(--yellow);
    }
    .verdict-REQUEST_CHANGES {
      background: rgba(218, 54, 51, 0.12);
      border-color: var(--red);
    }
    
    .verdict-title {
      font-size: 15px;
      font-weight: 700;
      color: #fff;
    }
    .verdict-desc {
      font-size: 12.5px;
      color: var(--text);
      margin-top: 3px;
    }
    
    /* Stats counters */
    .stats-row {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
    }
    .stat-card {
      background: #1c2128;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px 14px;
      text-align: center;
      cursor: pointer;
      transition: border-color 0.15s;
    }
    .stat-card:hover { border-color: var(--accent); }
    .stat-num {
      font-size: 22px;
      font-weight: 700;
      line-height: 1.2;
    }
    .stat-label {
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
      font-weight: 600;
      margin-top: 2px;
    }
    
    .stat-bug { color: var(--red); }
    .stat-risk { color: #f0883e; }
    .stat-test { color: var(--yellow); }
    .stat-style { color: var(--purple); }

    /* Tool Call Audit accordion */
    .tools-accordion {
      background: #1c2128;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 10px 14px;
      font-size: 12px;
    }
    .tools-accordion summary {
      cursor: pointer;
      font-weight: 600;
      color: var(--accent);
      user-select: none;
    }
    .tool-list {
      margin-top: 10px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .tool-item {
      background: #0d1117;
      border-left: 3px solid var(--accent);
      padding: 8px 12px;
      border-radius: 0 4px 4px 0;
      font-family: var(--font-mono);
      font-size: 11.5px;
    }
    .tool-meta {
      color: var(--text-muted);
      font-size: 11px;
      margin-bottom: 2px;
    }

    /* Findings List */
    .findings-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .finding-card {
      background: #1c2128;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 14px 16px;
      transition: all 0.15s;
      position: relative;
    }
    .finding-card:hover { border-color: #58a6ff; }
    .finding-header {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 8px;
    }
    .cat-badge {
      font-size: 11px;
      font-weight: 700;
      padding: 2px 7px;
      border-radius: 4px;
      text-transform: uppercase;
    }
    .cat-BUG { background: var(--red-bg); color: #ff7b72; border: 1px solid rgba(218,54,51,0.4); }
    .cat-RISK { background: rgba(240,136,62,0.15); color: #ffa657; border: 1px solid rgba(240,136,62,0.4); }
    .cat-TEST { background: rgba(210,153,34,0.15); color: #e3b341; border: 1px solid rgba(210,153,34,0.4); }
    .cat-STYLE { background: rgba(188,140,255,0.15); color: #d2a8ff; border: 1px solid rgba(188,140,255,0.4); }

    .sev-badge {
      font-size: 10px;
      font-weight: 600;
      padding: 1px 6px;
      border-radius: 3px;
      background: #21262d;
      color: var(--text-muted);
    }
    .finding-title {
      font-size: 14px;
      font-weight: 600;
      color: #fff;
    }
    .finding-location {
      font-family: var(--font-mono);
      font-size: 11px;
      color: var(--text-muted);
      margin-bottom: 6px;
    }
    .finding-body {
      font-size: 12.5px;
      color: var(--text);
      margin-bottom: 8px;
    }
    .finding-impact {
      font-size: 12px;
      color: #f0883e;
      background: rgba(240,136,62,0.08);
      padding: 6px 10px;
      border-radius: 4px;
      margin-bottom: 8px;
    }
    .finding-suggestion {
      font-size: 12px;
      color: #7ee787;
      background: rgba(46,160,67,0.08);
      padding: 6px 10px;
      border-radius: 4px;
      margin-bottom: 8px;
    }
    pre.code-patch {
      background: #0d1117;
      padding: 10px;
      border-radius: 4px;
      font-family: var(--font-mono);
      font-size: 11px;
      color: #79c0ff;
      overflow-x: auto;
      border: 1px solid #30363d;
      margin-top: 6px;
    }
    
    .spinner {
      border: 2px solid rgba(255,255,255,0.2);
      border-top: 2px solid #fff;
      border-radius: 50%;
      width: 14px;
      height: 14px;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <span class="brand-icon">⚡</span>
      <span class="brand-name">DiffLens</span>
      <span class="badge-sub">Autonomous AI Review Agent</span>
    </div>
    <div class="header-actions">
      <button class="btn btn-secondary" onclick="exportMarkdown()">📋 Copy PR Markdown</button>
      <button class="btn btn-secondary" onclick="exportJSON()">💾 Export JSON</button>
      <button class="btn btn-green" id="run-btn" onclick="executeReview()">
        <span>🚀 Run AI Agent Review</span>
      </button>
    </div>
  </header>

  <div class="container">
    <!-- Samples Selection Toolbar -->
    <div class="samples-bar">
      <span class="samples-label">Load Sample Diff:</span>
      <div id="samples-pills" style="display: flex; gap: 8px; flex-wrap: wrap;"></div>
    </div>

    <!-- Main 2-Column Interface -->
    <div class="grid">
      <!-- Left Panel: Diff Input -->
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">
            <span>📄</span> Git Diff / Pull Request Code Change
          </div>
          <div class="panel-actions">
            <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 11px;" onclick="clearDiff()">Clear</button>
          </div>
        </div>
        <textarea id="diff-input" placeholder="Paste your git diff, pull request patch, or select a sample above..."></textarea>
        <div class="options-bar">
          <label style="color: var(--text-muted);">Optional API Key (Gemini/OpenAI):</label>
          <input type="password" id="api-key-input" placeholder="Leaves empty to use Grounded AST Fallback" />
          <span style="color: var(--text-muted); font-size: 11px;">Zero-key offline mode active by default</span>
        </div>
      </div>

      <!-- Right Panel: Structured Review Results -->
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">
            <span>🎯</span> Structured Agent Feedback
          </div>
          <div id="filter-pills" style="display: flex; gap: 6px;"></div>
        </div>
        <div class="output-container" id="output-box">
          <div class="placeholder-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p><strong>No review executed yet.</strong></p>
            <p style="font-size: 12px; max-width: 320px;">Select a sample diff above or paste your code change, then click <strong>"Run AI Agent Review"</strong>.</p>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    let currentReport = null;
    let activeFilter = 'ALL';

    // Fetch available sample diffs
    async function initSamples() {
      try {
        const res = await fetch('/api/samples');
        const samples = await res.json();
        const container = document.getElementById('samples-pills');
        container.innerHTML = '';

        samples.forEach((s, idx) => {
          const btn = document.createElement('button');
          btn.className = 'sample-pill' + (idx === 0 ? ' active' : '');
          btn.textContent = s.title;
          btn.onclick = () => loadSample(s.id, btn);
          container.appendChild(btn);
        });

        if (samples.length > 0) {
          loadSample(samples[0].id, container.children[0]);
        }
      } catch (e) {
        console.error('Failed to load samples', e);
      }
    }

    async function loadSample(sampleId, pillElem) {
      document.querySelectorAll('.sample-pill').forEach(p => p.classList.remove('active'));
      if (pillElem) pillElem.classList.add('active');

      try {
        const res = await fetch(`/api/samples/${sampleId}`);
        const data = await res.json();
        document.getElementById('diff-input').value = data.content;
      } catch (e) {
        console.error('Failed to fetch sample diff', e);
      }
    }

    function clearDiff() {
      document.getElementById('diff-input').value = '';
      document.querySelectorAll('.sample-pill').forEach(p => p.classList.remove('active'));
    }

    async function executeReview() {
      const diffText = document.getElementById('diff-input').value;
      if (!diffText.trim()) {
        alert('Please paste or select a diff first.');
        return;
      }

      const apiKey = document.getElementById('api-key-input').value.trim();
      const runBtn = document.getElementById('run-btn');
      runBtn.disabled = true;
      runBtn.innerHTML = '<div class="spinner"></div><span>Reviewing Code...</span>';

      const outputBox = document.getElementById('output-box');
      outputBox.innerHTML = `
        <div class="placeholder-state">
          <div class="spinner" style="width: 36px; height: 36px; border-width: 3px;"></div>
          <p style="margin-top: 14px;"><strong>DiffLens Agent is analyzing diff...</strong></p>
          <p style="font-size: 12px; color: var(--text-muted);">Executing tool calls (AST analysis, test coverage mapping, file context inspection)...</p>
        </div>
      `;

      try {
        const res = await fetch('/api/review', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            diff_text: diffText,
            api_key: apiKey || null,
            provider: apiKey ? 'auto' : 'fallback'
          })
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Review failed');
        }

        currentReport = await res.json();
        renderReport(currentReport);
      } catch (err) {
        outputBox.innerHTML = `<div style="color: var(--red); padding: 20px;">Review Error: ${err.message}</div>`;
      } finally {
        runBtn.disabled = false;
        runBtn.innerHTML = '<span>🚀 Run AI Agent Review</span>';
      }
    }

    function renderReport(report) {
      const box = document.getElementById('output-box');
      box.innerHTML = '';

      // 1. Verdict Banner
      const vBanner = document.createElement('div');
      vBanner.className = `verdict-banner verdict-${report.summary.verdict}`;
      vBanner.innerHTML = `
        <div>
          <div class="verdict-title">${report.summary.verdict}: ${report.summary.verdict === 'APPROVED' ? 'Code is Ready' : 'Action Required'}</div>
          <div class="verdict-desc">${report.summary.executive_summary}</div>
        </div>
        <div style="font-size: 11px; text-align: right; color: var(--text-muted); font-family: var(--font-mono);">
          <div>Time: ${report.execution_time_seconds}s</div>
          <div>Mode: ${report.mode}</div>
        </div>
      `;
      box.appendChild(vBanner);

      // 2. Metrics 4-Grid
      const stats = document.createElement('div');
      stats.className = 'stats-row';
      stats.innerHTML = `
        <div class="stat-card" onclick="filterCategory('BUG')">
          <div class="stat-num stat-bug">${report.summary.bugs_count}</div>
          <div class="stat-label">Possible Bugs</div>
        </div>
        <div class="stat-card" onclick="filterCategory('RISK')">
          <div class="stat-num stat-risk">${report.summary.risks_count}</div>
          <div class="stat-label">Risks & Security</div>
        </div>
        <div class="stat-card" onclick="filterCategory('TEST')">
          <div class="stat-num stat-test">${report.summary.missing_tests_count}</div>
          <div class="stat-label">Missing Tests</div>
        </div>
        <div class="stat-card" onclick="filterCategory('STYLE')">
          <div class="stat-num stat-style">${report.summary.style_count}</div>
          <div class="stat-label">Style Issues</div>
        </div>
      `;
      box.appendChild(stats);

      // 3. Tool Calls Accordion
      if (report.tool_calls && report.tool_calls.length > 0) {
        const details = document.createElement('details');
        details.className = 'tools-accordion';
        details.innerHTML = `
          <summary>🛠️ Agent Tool Audit Trail (${report.tool_calls.length} tools executed)</summary>
          <div class="tool-list">
            ${report.tool_calls.map(tc => `
              <div class="tool-item">
                <div class="tool-meta">Step ${tc.step} | <strong>${tc.tool_name}</strong> &rarr; ${tc.reasoning || ''}</div>
                <div style="color: var(--text-muted); white-space: pre-wrap;">${tc.observation}</div>
              </div>
            `).join('')}
          </div>
        `;
        box.appendChild(details);
      }

      // 4. Findings List
      const findingsContainer = document.createElement('div');
      findingsContainer.className = 'findings-list';
      findingsContainer.id = 'findings-container';
      box.appendChild(findingsContainer);

      renderFindingsList();
    }

    function filterCategory(cat) {
      activeFilter = (activeFilter === cat) ? 'ALL' : cat;
      renderFindingsList();
    }

    function renderFindingsList() {
      const container = document.getElementById('findings-container');
      if (!container || !currentReport) return;
      container.innerHTML = '';

      const filtered = activeFilter === 'ALL'
        ? currentReport.findings
        : currentReport.findings.filter(f => f.category === activeFilter);

      if (filtered.length === 0) {
        container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 20px;">No findings for category "${activeFilter}".</div>`;
        return;
      }

      filtered.forEach((f, idx) => {
        const card = document.createElement('div');
        card.className = 'finding-card';
        card.innerHTML = `
          <div class="finding-header">
            <span class="cat-badge cat-${f.category}">${f.category}</span>
            <span class="sev-badge">${f.severity}</span>
            <span class="finding-title">#${idx+1}. ${f.title}</span>
          </div>
          <div class="finding-location">📁 ${f.file}${f.line ? ` : line ${f.line}` : ''}</div>
          <div class="finding-body">${f.description}</div>
          ${f.impact ? `<div class="finding-impact">⚠️ <strong>Impact:</strong> ${f.impact}</div>` : ''}
          <div class="finding-suggestion">💡 <strong>Suggestion:</strong> ${f.suggestion}</div>
          ${f.suggested_patch ? `<pre class="code-patch"><code>${f.suggested_patch}</code></pre>` : ''}
        `;
        container.appendChild(card);
      });
    }

    function exportMarkdown() {
      if (!currentReport) { alert('Run a review first.'); return; }
      let md = `# 🔍 DiffLens AI Code Review Report\\n\\n`;
      md += `**Verdict:** ${currentReport.summary.verdict}\\n`;
      md += `> ${currentReport.summary.executive_summary}\\n\\n`;
      md += `### Metrics Summary\\n`;
      md += `- 🐛 **Possible Bugs:** ${currentReport.summary.bugs_count}\\n`;
      md += `- 🛡️ **Risks:** ${currentReport.summary.risks_count}\\n`;
      md += `- 🧪 **Missing Tests:** ${currentReport.summary.missing_tests_count}\\n`;
      md += `- 🎨 **Style Issues:** ${currentReport.summary.style_count}\\n\\n`;
      md += `### Findings\\n`;
      currentReport.findings.forEach(f => {
        md += `#### [${f.category}] ${f.title} (${f.severity})\\n`;
        md += `- **Location:** \`${f.file}:${f.line || 'N/A'}\`\\n`;
        md += `- **Description:** ${f.description}\\n`;
        if (f.impact) md += `- **Impact:** ${f.impact}\\n`;
        md += `- **Suggestion:** ${f.suggestion}\\n\\n`;
      });
      navigator.clipboard.writeText(md);
      alert('Markdown report copied to clipboard!');
    }

    function exportJSON() {
      if (!currentReport) { alert('Run a review first.'); return; }
      const blob = new Blob([JSON.stringify(currentReport, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `difflens-report-${Date.now()}.json`;
      a.click();
    }

    window.onload = initSamples;
  </script>
</body>
</html>
"""
