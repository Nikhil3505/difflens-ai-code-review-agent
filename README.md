# ⚡ DiffLens: Autonomous AI Code Review Agent

> **Author:** Nikhil Patil (`patilnikhil3505@gmail.com`)  
> *Built by Nikhil Patil for AI Agent Technical Evaluation*

---

> An agentic code reviewer that inspects Git diffs and Pull Requests to deliver structured, actionable feedback across **Possible Bugs**, **Risks**, **Missing Tests**, and **Style Issues**.

---

## 1. What It Does

**DiffLens** is a local-first, autonomous AI agent designed to bridge the gap between static linters and human code review. Instead of treating code changes as isolated snippets, DiffLens investigates the wider repository context and provides grounded review reports.

- **4 Structured Feedback Categories**:
  - 🐛 **Possible Bugs**: TOCTOU concurrency race conditions, off-by-one boundary errors, unhandled null references, unclosed resource leaks.
  - 🛡️ **Risks & Security Vulnerabilities**: SQL injection via string interpolation, broken crypto (MD5/SHA-1), floating-point monetary math, unbounded memory consumption.
  - 🧪 **Missing Tests**: Flags production code changes introduced without accompanying test updates or unverified branches.
  - 🎨 **Style & Antipatterns**: PEP 8 violations (camelCase in Python), bare `except:` clauses, mutable default arguments (`def f(x=[])`).
- **Deterministic Verdicts**: Computes an executive decision (`APPROVED`, `NEEDS_DISCUSSION`, `REQUEST_CHANGES`) with impact assessment and copy-pasteable patch suggestions.
- **Multiple Operational Interfaces**:
  - **CLI**: Fast terminal reviews with formatted tables and color-coded severities.
  - **PR Comment Markdown**: Formatted GitHub PR review summary ready to pipe into CI bots.
  - **Interactive Web Dashboard**: Modern FastAPI-powered browser UI with sample diff presets and live tool audit trail.
  - **Zero-Key Resilience**: Full deterministic AST fallback engine ensuring anyone can clone, test, and evaluate without configuring an API key.

---

## 2. How I Built It

```
               ┌────────────────────────────────────────────────────────┐
               │                      Git Diff / PR                     │
               └───────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │           UnifiedDiffParser (Hunks, Lineno)            │
               └───────────────────────────┬────────────────────────────┘
                                           │
                      ┌────────────────────┴───────────────────┐
                      ▼                                        ▼
      ┌───────────────────────────────┐        ┌───────────────────────────────┐
      │     Agent Tool Execution      │        │      Workspace Knowledge      │
      │  - FileContextInspector       │◄───────┤  - Surrounding File Lines     │
      │  - TestCoverageInspector      │        │  - tests/ Directory Search    │
      │  - StaticASTAnalyzer          │        │  - AST Antipatterns / Syntax  │
      └───────────────┬───────────────┘        └───────────────────────────────┘
                      │
                      ▼
      ┌────────────────────────────────────────────────────────┐
      │             Synthesis & Schema Validation              │
      │  - Gemini / OpenAI REST Client (Online)                │
      │  - Deterministic AST Rules Engine (Offline Fallback)   │
      └───────────────────────────┬────────────────────────────┘
                                  │
                                  ▼
      ┌────────────────────────────────────────────────────────┐
      │               Structured ReviewReport                  │
      │  [Bugs | Risks | Missing Tests | Style | Verdict]      │
      └────────────────────────────────────────────────────────┘
```

- **Core Agent Loop (`diff_lens/agent.py`)**:
  1. **Perception**: I implemented `UnifiedDiffParser` to extract files, modified lines, additions, deletions, and accurately map hunk headers to real target line numbers.
  2. **Planning & Investigation**: For each changed file, the agent invokes its tools:
     - `inspect_file_context`: Retrieves surrounding file code to evaluate class scopes and global imports.
     - `inspect_test_coverage`: Inspects workspace test files to detect if modified functions have unit test assertions.
     - `run_static_analysis`: Executes Python AST visitors to detect unsafe nodes.
  3. **Synthesis**: Combines the diff and tool observations into the Pydantic `ReviewReport` schema.
- **Models & Providers (`diff_lens/llm_client.py`)**:
  - Supports **Google Gemini** (`gemini-1.5-flash`, `gemini-2.0-flash`) and **OpenAI** (`gpt-4o-mini`, custom Ollama endpoints).
  - Uses direct HTTP REST queries via `requests` without heavy proprietary SDK locks.
  - Built a **Deterministic Rules & AST Engine** (`diff_lens/rules_engine.py`) as a zero-key offline fallback.
- **Tech Stack**: Python 3.11, Pydantic v2 (strict schema validation), FastAPI & Uvicorn (dashboard), Colorama & Tabulate (CLI), Pytest (testing).

---

## 3. What Went Wrong and How I Handled It

1. **Truncated Diff Context & Line Drift**:
   - *Problem*: Git diff hunks typically show only 3 lines of surrounding code. LLMs reviewing raw diffs frequently hallucinated variable types or suggested imports that already existed earlier in the file.
   - *Resolution*: Implemented `FileContextInspector` tool. When reviewing a hunk, the agent queries lines `(start - 10)` to `(end + 10)` in the actual repository file, supplying grounded context to the reviewer.
2. **Comment Substring Collision in Static Analysis**:
   - *Problem*: In testing scenario 2 (concurrency race condition), an explanatory comment `# Potential race condition: non-atomic check and debit` caused the concurrency detector to falsely assume the word `"atomic"` meant a concurrency primitive was present!
   - *Resolution*: Stripped comments prior to evaluating concurrency safety keywords and validated AST call nodes directly.
3. **Test Hallucination vs Grounded Scanning**:
   - *Problem*: LLMs often claim "tests are missing" on PRs that actually include tests in other directories, or fail to notice when a new critical function is introduced without a test.
   - *Resolution*: Built `TestCoverageInspector` to recursively search the repo's test directories, inspect function symbol names in test suites, and explicitly report whether tests were touched in the diff.
4. **Evaluating Without Paid API Keys**:
   - *Problem*: Forcing an evaluator to provide a paid Gemini/OpenAI API key introduces friction or breaks in firewalled/offline environments.
   - *Resolution*: Built a dual-mode engine. If no API key is provided, DiffLens activates its grounded AST and pattern rules engine, producing identical Pydantic-validated JSON, Markdown, and CLI outputs with a full tool audit trail.

---

## 4. What I Would Do Next

- **GitHub App / GitLab Bot**: Automatically trigger DiffLens on `pull_request` webhooks and post inline comments directly on changed diff lines using GitHub's Review API.
- **Multi-Language AST Support**: Integrate `tree-sitter` to extend AST parsing beyond Python to TypeScript, Go, Rust, and Java.
- **Repository Vector Memory**: Index repo-specific PR history and architectural guidelines into a lightweight vector store (e.g., ChromaDB) to enforce team-specific design patterns.
- **One-Click Patch Application**: Allow developers to apply proposed `suggested_patch` snippets directly to their working tree via `diff_lens apply --finding <ID>`.

---

## 5. Quick Start & Demo

### Run the Live Demo (Zero API Key Needed):
```bash
# Run comprehensive demo across all 4 sample diff scenarios
python demo.py console

# Output as GitHub PR Comment Markdown
python demo.py markdown
```

### Review Local Code Changes:
```bash
# Review a specific diff file
python -m diff_lens review --file samples/01_auth_sql_injection.diff

# Review staged git changes in current repo
python -m diff_lens review --staged

# Review unstaged working tree changes
python -m diff_lens review --working

# Export output as JSON
python -m diff_lens review --file samples/02_payment_race_condition.diff --format json
```

### Launch Interactive Web Dashboard:
```bash
python -m diff_lens serve --port 8000
# Open http://127.0.0.1:8000 in your browser
```

### Run Unit Tests:
```bash
python -m pytest -v
```

