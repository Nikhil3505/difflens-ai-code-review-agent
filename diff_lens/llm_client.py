"""LLM Client for DiffLens supporting Gemini, OpenAI, and Local Models."""

import json
import os
from typing import List, Dict, Any, Optional, Tuple
import requests
from diff_lens.models import Finding, ReviewCategory, Severity, ReviewSummary, Verdict


class LLMClient:
    """Client for querying LLM APIs with tool-calling capabilities."""

    def __init__(self, api_key: Optional[str] = None, provider: str = "auto", model: Optional[str] = None):
        self.gemini_key = api_key or os.getenv("GEMINI_API_KEY")
        self.openai_key = api_key or os.getenv("OPENAI_API_KEY")
        self.provider = provider
        self.model = model

        if self.provider == "auto":
            if self.gemini_key:
                self.provider = "gemini"
                self.model = self.model or "gemini-1.5-flash"
            elif self.openai_key:
                self.provider = "openai"
                self.model = self.model or "gpt-4o-mini"
            else:
                self.provider = "fallback"

    def is_available(self) -> bool:
        """Check if an active LLM provider configuration exists."""
        return self.provider in ("gemini", "openai")

    def review_with_llm(
        self,
        diff_text: str,
        tool_observations: List[Dict[str, Any]],
    ) -> Optional[Tuple[List[Finding], ReviewSummary]]:
        """Call the LLM with diff and tool context, expecting structured findings."""
        if not self.is_available():
            return None

        prompt = self._build_prompt(diff_text, tool_observations)
        system_instruction = self._build_system_instruction()

        try:
            if self.provider == "gemini":
                return self._call_gemini(system_instruction, prompt)
            elif self.provider == "openai":
                return self._call_openai(system_instruction, prompt)
        except Exception as e:
            # Silently fall back to rules engine on any network/API exception
            print(f"[DiffLens Warning] LLM call failed ({str(e)}). Falling back to grounded AST engine.")
            return None

        return None

    def _build_system_instruction(self) -> str:
        return (
            "You are DiffLens, an autonomous AI Senior Staff Software Engineer and Security Code Reviewer. "
            "You review code changes (git diffs/pull requests) and return structured feedback.\n"
            "You must categorize every finding into one of EXACTLY four categories:\n"
            "1. BUG: Logic errors, off-by-one errors, null pointer dereferences, race conditions, unhandled exceptions.\n"
            "2. RISK: Security vulnerabilities (SQLi, XSS, RCE, insecure crypto), performance bottlenecks, breaking changes, data loss.\n"
            "3. TEST: Missing unit/integration tests for new functions, untested edge cases, lack of regression tests.\n"
            "4. STYLE: Naming conventions (PEP 8), mutable default arguments, bare exceptions, dead code, long lines, code smells.\n\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "findings": [\n'
            "    {\n"
            '      "id": "FINDING-001",\n'
            '      "category": "BUG" | "RISK" | "TEST" | "STYLE",\n'
            '      "severity": "CRITICAL" | "MAJOR" | "MINOR" | "INFO",\n'
            '      "file": "path/to/file.ext",\n'
            '      "line": 42,\n'
            '      "title": "Short title",\n'
            '      "description": "Detailed explanation of the issue and why it happens",\n'
            '      "impact": "Concrete consequence of this issue",\n'
            '      "suggestion": "Actionable advice on how to fix it",\n'
            '      "suggested_patch": "Optional code replacement snippet",\n'
            '      "confidence": 0.95\n'
            "    }\n"
            "  ],\n"
            '  "executive_summary": "High-level summary of review findings",\n'
            '  "verdict": "APPROVED" | "NEEDS_DISCUSSION" | "REQUEST_CHANGES"\n'
            "}"
        )

    def _build_prompt(self, diff_text: str, tool_observations: List[Dict[str, Any]]) -> str:
        obs_text = ""
        if tool_observations:
            obs_text = "\n### Agent Tool Observations (Surrounding context, AST, tests):\n"
            for obs in tool_observations:
                obs_text += f"- [{obs.get('tool_name')}]: {obs.get('observation')}\n"

        return (
            f"Please thoroughly review the following Git Diff / Code Change:\n\n"
            f"```diff\n{diff_text}\n```\n"
            f"{obs_text}\n"
            f"Analyze all added and changed lines carefully. Check for bugs, security risks, missing tests, and style issues. "
            f"Produce the JSON response as specified."
        )

    def _call_gemini(self, system_instruction: str, prompt: str) -> Optional[Tuple[List[Finding], ReviewSummary]]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.gemini_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_instruction}\n\n{prompt}"}],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
            },
        }

        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        return self._parse_json_response(raw_text)

    def _call_openai(self, system_instruction: str, prompt: str) -> Optional[Tuple[List[Finding], ReviewSummary]]:
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        raw_text = data["choices"][0]["message"]["content"]
        return self._parse_json_response(raw_text)

    def _parse_json_response(self, raw_text: str) -> Optional[Tuple[List[Finding], ReviewSummary]]:
        try:
            parsed = json.loads(raw_text)
            raw_findings = parsed.get("findings", [])
            findings: List[Finding] = []

            for rf in raw_findings:
                # Sanitize category
                cat_str = str(rf.get("category", "BUG")).upper()
                if cat_str not in ReviewCategory.__members__:
                    cat_str = "BUG"

                # Sanitize severity
                sev_str = str(rf.get("severity", "MINOR")).upper()
                if sev_str not in Severity.__members__:
                    sev_str = "MINOR"

                findings.append(
                    Finding(
                        id=rf.get("id", f"FINDING-{len(findings)+1:03d}"),
                        category=ReviewCategory[cat_str],
                        severity=Severity[sev_str],
                        file=rf.get("file", "unknown"),
                        line=rf.get("line"),
                        title=rf.get("title", "Review Finding"),
                        description=rf.get("description", ""),
                        impact=rf.get("impact"),
                        suggestion=rf.get("suggestion", ""),
                        suggested_patch=rf.get("suggested_patch"),
                        confidence=float(rf.get("confidence", 0.9)),
                    )
                )

            verdict_str = str(parsed.get("verdict", "NEEDS_DISCUSSION")).upper()
            if verdict_str not in Verdict.__members__:
                verdict_str = "NEEDS_DISCUSSION"

            bugs = sum(1 for f in findings if f.category == ReviewCategory.BUG)
            risks = sum(1 for f in findings if f.category == ReviewCategory.RISK)
            tests = sum(1 for f in findings if f.category == ReviewCategory.TEST)
            styles = sum(1 for f in findings if f.category == ReviewCategory.STYLE)

            summary = ReviewSummary(
                total_findings=len(findings),
                bugs_count=bugs,
                risks_count=risks,
                missing_tests_count=tests,
                style_count=styles,
                verdict=Verdict[verdict_str],
                executive_summary=parsed.get("executive_summary", "Review completed by AI Agent."),
            )

            return findings, summary
        except Exception as e:
            print(f"[DiffLens Warning] Failed to parse LLM JSON response: {e}")
            return None

