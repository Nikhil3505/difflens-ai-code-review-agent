"""Agent Tools for DiffLens.

These tools allow the review agent to gather surrounding context,
inspect test suites, run static AST analysis, and retrieve git diffs.
"""

import ast
import os
import re
import subprocess
from typing import Dict, Any, List, Optional
from diff_lens.models import ToolCallRecord


class FileContextInspector:
    """Tool to read source files around a changed hunk to provide broader context."""

    name = "inspect_file_context"
    description = (
        "Inspect the surrounding source code of a file in the repository "
        "to check imports, class definitions, function scope, or helper usages."
    )

    def __init__(self, repo_root: Optional[str] = None):
        self.repo_root = repo_root or os.getcwd()

    def run(self, file_path: str, start_line: Optional[int] = 1, end_line: Optional[int] = None) -> str:
        """Read lines from file_path between start_line and end_line (1-indexed)."""
        clean_path = file_path.lstrip("ab/\\")
        candidate_paths = [
            os.path.join(self.repo_root, clean_path),
            clean_path,
        ]
        target_path = None
        for cp in candidate_paths:
            if os.path.exists(cp) and os.path.isfile(cp):
                target_path = cp
                break

        if not target_path:
            return f"[Tool Observation] File '{file_path}' not found in working repository '{self.repo_root}'."

        try:
            with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            s_line = max(1, start_line or 1)
            e_line = min(total_lines, end_line or total_lines)

            selected = lines[s_line - 1 : e_line]
            formatted_lines = [
                f"{s_line + idx:4d} | {line.rstrip()}"
                for idx, line in enumerate(selected)
            ]
            header = f"=== File: {clean_path} (Lines {s_line}-{e_line} of {total_lines}) ===\n"
            return header + "\n".join(formatted_lines)
        except Exception as e:
            return f"[Tool Error] Failed to read '{file_path}': {str(e)}"


class TestCoverageInspector:
    """Tool to inspect test suites and check if modified functions have unit tests."""

    __test__ = False  # Prevent pytest from treating this domain class as a test suite
    name = "inspect_test_coverage"
    description = (
        "Scans test directories to determine if a modified module or function "
        "has corresponding unit/integration tests and whether tests were added in the diff."
    )

    def __init__(self, repo_root: Optional[str] = None):
        self.repo_root = repo_root or os.getcwd()

    def run(self, target_file: str, function_name: Optional[str] = None, diff_content: str = "") -> str:
        """Scan for test files associated with target_file and check for function_name."""
        clean_file = target_file.lstrip("ab/\\")
        base_name = os.path.splitext(os.path.basename(clean_file))[0]

        # 1. Check if the diff itself touches test files
        diff_touches_tests = False
        if diff_content:
            test_patterns = [r"test_.*\.py", r".*_test\.py", r"tests/.*", r"spec/.*"]
            for pat in test_patterns:
                if re.search(pat, diff_content, re.IGNORECASE):
                    diff_touches_tests = True
                    break

        # 2. Look for existing test files in the workspace
        potential_test_names = [
            f"test_{base_name}.py",
            f"{base_name}_test.py",
            f"test_{base_name}.js",
            f"test_{base_name}.ts",
        ]

        found_test_files = []
        for root, _, files in os.walk(self.repo_root):
            for file in files:
                if file in potential_test_names or ("test" in file and base_name in file):
                    found_test_files.append(os.path.relpath(os.path.join(root, file), self.repo_root))

        # 3. Check for specific function test assertions
        function_covered = False
        matching_tests = []
        if function_name and found_test_files:
            fn_clean = function_name.strip("(): ")
            for tf in found_test_files:
                tf_path = os.path.join(self.repo_root, tf)
                try:
                    with open(tf_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if fn_clean in content:
                            function_covered = True
                            matching_tests.append(tf)
                except Exception:
                    pass

        observations = []
        observations.append(f"Target Module: {clean_file}")
        observations.append(f"Diff updates/adds tests: {'YES' if diff_touches_tests else 'NO'}")

        if found_test_files:
            observations.append(f"Existing test files found in repository: {', '.join(found_test_files)}")
            if function_name:
                if function_covered:
                    observations.append(f"Function '{function_name}' appears in test suites: {', '.join(matching_tests)}")
                else:
                    observations.append(f"WARNING: Function '{function_name}' has NO existing test mentions in {found_test_files}.")
        else:
            observations.append(f"No existing test files found matching module '{base_name}'.")

        return "\n".join(observations)


class StaticASTAnalyzer:
    """Tool to perform Python Abstract Syntax Tree (AST) analysis on changed code."""

    name = "run_static_analysis"
    description = (
        "Parses code snippets or files to detect syntax errors, unsafe patterns "
        "(SQL injection, insecure hashing, bare exceptions, mutable defaults)."
    )

    def run(self, code_snippet: str, file_path: str = "snippet.py") -> str:
        """Run AST and pattern checks on the given snippet."""
        findings = []

        # 1. Syntax Check
        try:
            tree = ast.parse(code_snippet)
        except SyntaxError as e:
            return f"[Syntax Error] {e.msg} at line {e.lineno}, col {e.offset}: {e.text}"

        # 2. AST Visitor Checks
        class SecurityAndStyleVisitor(ast.NodeVisitor):
            def __init__(self):
                self.issues = []

            def visit_FunctionDef(self, node):
                # Check for mutable default arguments
                for default in node.args.defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        self.issues.append(
                            f"Line {node.lineno}: Mutable default argument '{ast.unparse(default)}' in function '{node.name}'. "
                            f"Can lead to shared state bugs across invocations."
                        )

                # Check naming convention (snake_case for functions)
                if re.match(r"^[a-z]+[A-Z]", node.name):
                    self.issues.append(
                        f"Line {node.lineno}: Function '{node.name}' uses camelCase naming instead of snake_case (PEP 8 violation)."
                    )

                self.generic_visit(node)

            def visit_Try(self, node):
                # Check for bare except:
                for handler in node.handlers:
                    if handler.type is None:
                        self.issues.append(
                            f"Line {handler.lineno}: Bare 'except:' clause caught. "
                            f"Catches SystemExit and KeyboardInterrupt, hiding unexpected errors."
                        )
                self.generic_visit(node)

            def visit_Call(self, node):
                # Check for md5 usage
                func_name = ast.unparse(node.func)
                if "hashlib.md5" in func_name:
                    self.issues.append(
                        f"Line {node.lineno}: Insecure cryptographic hash 'hashlib.md5' detected. "
                        f"Vulnerable to collision attacks; use bcrypt, argon2 or SHA-256."
                    )
                elif func_name in ("eval", "exec"):
                    self.issues.append(
                        f"Line {node.lineno}: Dangerous dynamic evaluation via '{func_name}' detected."
                    )

                # Check for SQL injection in execute() calls
                if "execute" in func_name and node.args:
                    first_arg = node.args[0]
                    # Check if argument is a JoinedStr (f-string)
                    if isinstance(first_arg, ast.JoinedStr):
                        self.issues.append(
                            f"Line {node.lineno}: Potential SQL Injection! Query constructed using f-string in '{func_name}'. "
                            f"Use parameterized queries with placeholders."
                        )
                    # Check for string % or .format()
                    elif isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, ast.Mod):
                        self.issues.append(
                            f"Line {node.lineno}: Potential SQL Injection! Query constructed using '%' string formatting in '{func_name}'."
                        )
                    elif isinstance(first_arg, ast.Call) and getattr(first_arg.func, "attr", "") == "format":
                        self.issues.append(
                            f"Line {node.lineno}: Potential SQL Injection! Query constructed using '.format()' in '{func_name}'."
                        )

                self.generic_visit(node)

        visitor = SecurityAndStyleVisitor()
        visitor.visit(tree)

        if not visitor.issues:
            return "Static AST analysis passed. No syntax errors or critical AST antipatterns detected."

        return "Static Analysis Findings:\n" + "\n".join(f"- {issue}" for issue in visitor.issues)


class GitDiffExtractor:
    """Tool to extract diffs from local git repository or patch files."""

    @staticmethod
    def get_staged_diff(repo_dir: str = ".") -> str:
        """Get diff of staged changes (git diff --cached)."""
        res = subprocess.run(
            ["git", "diff", "--cached"],
            cwd=repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        if res.returncode != 0:
            raise RuntimeError(f"Git error: {res.stderr}")
        return res.stdout

    @staticmethod
    def get_working_diff(repo_dir: str = ".") -> str:
        """Get diff of unstaged working tree changes (git diff)."""
        res = subprocess.run(
            ["git", "diff"],
            cwd=repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        if res.returncode != 0:
            raise RuntimeError(f"Git error: {res.stderr}")
        return res.stdout

    @staticmethod
    def get_commit_diff(commit_ref: str = "HEAD", repo_dir: str = ".") -> str:
        """Get diff introduced by a commit (git show <commit_ref>)."""
        res = subprocess.run(
            ["git", "show", commit_ref],
            cwd=repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        if res.returncode != 0:
            raise RuntimeError(f"Git error: {res.stderr}")
        return res.stdout

    @staticmethod
    def read_diff_file(file_path: str) -> str:
        """Read a unified diff file from disk."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Diff file '{file_path}' does not exist.")
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
