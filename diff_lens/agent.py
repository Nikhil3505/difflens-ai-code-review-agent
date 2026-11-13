"""Autonomous Code Review Agent Orchestrator for DiffLens."""

import time
from datetime import datetime
from typing import Optional, List
from diff_lens.models import (
    ReviewReport,
    ToolCallRecord,
    Finding,
    ReviewSummary,
    ReviewCategory,
)
from diff_lens.parser import UnifiedDiffParser
from diff_lens.tools import (
    FileContextInspector,
    TestCoverageInspector,
    StaticASTAnalyzer,
    GitDiffExtractor,
)
from diff_lens.rules_engine import DeterministicRulesEngine
from diff_lens.llm_client import LLMClient


class CodeReviewAgent:
    """The central Autonomous AI Agent for code reviews."""

    def __init__(
        self,
        repo_root: Optional[str] = None,
        api_key: Optional[str] = None,
        provider: str = "auto",
        model: Optional[str] = None,
    ):
        self.repo_root = repo_root
        self.parser = UnifiedDiffParser()
        self.file_inspector = FileContextInspector(repo_root)
        self.test_inspector = TestCoverageInspector(repo_root)
        self.ast_analyzer = StaticASTAnalyzer()
        self.rules_engine = DeterministicRulesEngine(repo_root)
        self.llm_client = LLMClient(api_key=api_key, provider=provider, model=model)

    def review(self, diff_text: str, source_label: str = "custom_diff") -> ReviewReport:
        """Execute the agentic review loop on the provided unified diff."""
        start_time = time.time()
        tool_records: List[ToolCallRecord] = []
        step_counter = 1

        # 1. Perception: Parse unified diff
        parsed_diff = self.parser.parse(diff_text)
        files_reviewed = [f.new_path or f.old_path for f in parsed_diff.files]

        # 2. Planning & Tool Execution Phase
        for file_diff in parsed_diff.files:
            file_path = file_diff.new_path or file_diff.old_path

            # Tool 1: File Context Inspector
            for hunk in file_diff.hunks[:2]:  # Inspect context for primary hunks
                obs = self.file_inspector.run(
                    file_path=file_path,
                    start_line=max(1, hunk.new_start - 10),
                    end_line=hunk.new_start + hunk.new_lines + 10,
                )
                tool_records.append(
                    ToolCallRecord(
                        step=step_counter,
                        tool_name=self.file_inspector.name,
                        arguments={
                            "file_path": file_path,
                            "start_line": max(1, hunk.new_start - 10),
                            "end_line": hunk.new_start + hunk.new_lines + 10,
                        },
                        observation=obs[:400] + ("..." if len(obs) > 400 else ""),
                        reasoning=f"Inspect surrounding lines in {file_path} to check caller and class scope context.",
                    )
                )
                step_counter += 1

            # Tool 2: Test Coverage Inspector
            test_obs = self.test_inspector.run(
                target_file=file_path,
                function_name=None,
                diff_content=diff_text,
            )
            tool_records.append(
                ToolCallRecord(
                    step=step_counter,
                    tool_name=self.test_inspector.name,
                    arguments={"target_file": file_path},
                    observation=test_obs,
                    reasoning=f"Verify if test suites exist for {file_path} and check if diff modified test files.",
                )
            )
            step_counter += 1

            # Tool 3: Static AST Analyzer (for Python files)
            if file_path.endswith(".py"):
                added_code = "\n".join(
                    l.content for h in file_diff.hunks for l in h.lines if l.type == "+"
                )
                if added_code.strip():
                    ast_obs = self.ast_analyzer.run(added_code, file_path=file_path)
                    tool_records.append(
                        ToolCallRecord(
                            step=step_counter,
                            tool_name=self.ast_analyzer.name,
                            arguments={"file_path": file_path, "code_snippet_len": len(added_code)},
                            observation=ast_obs,
                            reasoning=f"Run AST validation to detect syntax issues or hazardous operations in {file_path}.",
                        )
                    )
                    step_counter += 1

        # 3. Synthesis Phase: LLM vs Grounded Fallback
        findings: List[Finding] = []
        summary: Optional[ReviewSummary] = None
        execution_mode = "grounded-rules-agent"

        if self.llm_client.is_available():
            tool_obs_dicts = [r.model_dump() for r in tool_records]
            llm_result = self.llm_client.review_with_llm(diff_text, tool_obs_dicts)
            if llm_result:
                findings, summary = llm_result
                execution_mode = f"llm-agent ({self.llm_client.provider}:{self.llm_client.model})"

        # If LLM unavailable or returned empty, run grounded AST and rules engine
        if not findings or not summary:
            findings, summary = self.rules_engine.analyze(parsed_diff)
            execution_mode = "grounded-rules-agent (offline/zero-key fallback)"

        elapsed = round(time.time() - start_time, 3)

        return ReviewReport(
            timestamp=datetime.now().isoformat(),
            target_source=source_label,
            files_reviewed=files_reviewed,
            summary=summary,
            findings=findings,
            tool_calls=tool_records,
            execution_time_seconds=elapsed,
            mode=execution_mode,
        )

    def review_file(self, file_path: str) -> ReviewReport:
        """Review changes from a diff file on disk."""
        diff_text = GitDiffExtractor.read_diff_file(file_path)
        return self.review(diff_text, source_label=f"file:{file_path}")

    def review_staged(self) -> ReviewReport:
        """Review git staged changes (git diff --cached)."""
        diff_text = GitDiffExtractor.get_staged_diff(self.repo_root or ".")
        if not diff_text.strip():
            raise ValueError("No staged changes found in git repository. Run 'git add <files>' first.")
        return self.review(diff_text, source_label="git:staged")

    def review_working_tree(self) -> ReviewReport:
        """Review unstaged git working tree changes (git diff)."""
        diff_text = GitDiffExtractor.get_working_diff(self.repo_root or ".")
        if not diff_text.strip():
            raise ValueError("No uncommitted working tree changes found in git repository.")
        return self.review(diff_text, source_label="git:working_tree")

    def review_commit(self, commit_ref: str = "HEAD") -> ReviewReport:
        """Review changes introduced by a specific git commit (git show <commit>)."""
        diff_text = GitDiffExtractor.get_commit_diff(commit_ref, self.repo_root or ".")
        return self.review(diff_text, source_label=f"git:commit:{commit_ref}")

