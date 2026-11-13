"""Deterministic Rules and AST Analyzer Engine for DiffLens.

Provides deterministic, grounded code review analysis across all four categories:
- BUGS
- RISKS
- MISSING TESTS
- STYLE ISSUES

This ensures the agent can function reliably both offline (zero-API-key mode)
and as a grounding verification layer for the LLM agent.
"""

import ast
import re
from typing import List, Tuple, Optional
from diff_lens.models import (
    ParsedDiff,
    Finding,
    ReviewCategory,
    Severity,
    ReviewSummary,
    Verdict,
    FileDiff,
    DiffHunk,
)
from diff_lens.tools import FileContextInspector, TestCoverageInspector, StaticASTAnalyzer


class DeterministicRulesEngine:
    """Rule and AST-based review engine."""

    def __init__(self, repo_root: Optional[str] = None):
        self.repo_root = repo_root
        self.file_inspector = FileContextInspector(repo_root)
        self.test_inspector = TestCoverageInspector(repo_root)
        self.ast_analyzer = StaticASTAnalyzer()

    def analyze(self, parsed_diff: ParsedDiff) -> Tuple[List[Finding], ReviewSummary]:
        """Analyze a parsed diff and return structured findings and summary."""
        findings: List[Finding] = []
        finding_counter = 1

        # Check overall test presence in the diff
        test_files_in_diff = [
            f.new_path for f in parsed_diff.files
            if "test" in f.new_path.lower() or "spec" in f.new_path.lower()
        ]
        production_files_in_diff = [
            f.new_path for f in parsed_diff.files
            if f.new_path not in test_files_in_diff and f.change_type != "deleted"
        ]

        for file_diff in parsed_diff.files:
            file_path = file_diff.new_path or file_diff.old_path
            ext = file_path.split(".")[-1].lower() if "." in file_path else ""

            # Check for each hunk
            for hunk in file_diff.hunks:
                # 1. Analyze additions for bugs, risks, style
                added_lines = [l for l in hunk.lines if l.type == "+"]
                added_content = "\n".join(l.content for l in added_lines)

                # Check for AST issues if it's Python
                if ext == "py" and added_content.strip():
                    ast_findings = self._analyze_python_ast(file_path, hunk, finding_counter)
                    for f in ast_findings:
                        findings.append(f)
                        finding_counter += 1

                # Check for pattern-based issues across languages
                pattern_findings = self._analyze_patterns(file_path, hunk, finding_counter)
                for f in pattern_findings:
                    findings.append(f)
                    finding_counter += 1

                # Check for missing tests
                test_findings = self._analyze_missing_tests(
                    file_diff=file_diff,
                    hunk=hunk,
                    has_tests_in_diff=bool(test_files_in_diff),
                    finding_counter=finding_counter,
                )
                for f in test_findings:
                    findings.append(f)
                    finding_counter += 1

        # Global check: Production files modified but no tests included in diff
        if production_files_in_diff and not test_files_in_diff and parsed_diff.total_added > 5:
            # Check if we already logged a test finding for each file
            has_general_test_finding = any(f.category == ReviewCategory.TEST for f in findings)
            if not has_general_test_finding:
                findings.append(
                    Finding(
                        id=f"FINDING-{finding_counter:03d}",
                        category=ReviewCategory.TEST,
                        severity=Severity.MAJOR,
                        file=production_files_in_diff[0],
                        line=None,
                        title="Pull Request adds production code without test modifications",
                        description=(
                            f"The diff modifies {len(production_files_in_diff)} production file(s) "
                            f"({', '.join(production_files_in_diff[:3])}) with {parsed_diff.total_added} additions, "
                            f"but introduces zero test updates or new test cases."
                        ),
                        impact="Regression risk. New functionality is unverified in CI pipeline.",
                        suggestion="Add corresponding unit or integration test cases validating the new behavior and edge cases.",
                        confidence=0.95,
                    )
                )
                finding_counter += 1

        # Deduplicate findings by title and line
        unique_findings = []
        seen = set()
        for f in findings:
            key = (f.file, f.line, f.category, f.title)
            if key not in seen:
                seen.add(key)
                unique_findings.append(f)

        # Generate summary
        summary = self._generate_summary(unique_findings)
        return unique_findings, summary

    def _analyze_python_ast(self, file_path: str, hunk: DiffHunk, start_id: int) -> List[Finding]:
        findings = []
        added_lines = [l for l in hunk.lines if l.type == "+"]
        code = "\n".join(l.content for l in added_lines)

        try:
            tree = ast.parse(code)
        except SyntaxError:
            # Code snippet might be an incomplete block; wrap in a dummy function or analyze line by line
            try:
                tree = ast.parse(f"def _dummy_wrapper():\n" + "\n".join(f"    {l.content}" for l in added_lines))
            except Exception:
                return findings

        for node in ast.walk(tree):
            # 1. Mutable default arguments in function definitions
            if isinstance(node, ast.FunctionDef):
                for default in node.args.defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        line_no = self._map_ast_line_to_diff(node.lineno, hunk)
                        findings.append(
                            Finding(
                                id=f"FINDING-{start_id + len(findings):03d}",
                                category=ReviewCategory.BUG,
                                severity=Severity.MAJOR,
                                file=file_path,
                                line=line_no,
                                title=f"Mutable default argument in function '{node.name}'",
                                description=(
                                    f"Function '{node.name}' uses a mutable default value "
                                    f"({type(default).__name__.lower()}). In Python, default arguments are evaluated "
                                    f"once when the function is defined, causing all calls to mutate the shared object."
                                ),
                                impact="Subtle state leakage bugs across requests or callers.",
                                suggestion=f"Use 'def {node.name}(..., param=None):' and initialize inside the function body.",
                                suggested_patch=f"def {node.name}(..., param=None):\n    if param is None:\n        param = []",
                                confidence=0.95,
                            )
                        )

                # Style: Check naming (camelCase instead of snake_case)
                if re.match(r"^[a-z]+[A-Z]", node.name):
                    line_no = self._map_ast_line_to_diff(node.lineno, hunk)
                    snake_name = re.sub(r"(?<!^)(?=[A-Z])", "_", node.name).lower()
                    findings.append(
                        Finding(
                            id=f"FINDING-{start_id + len(findings):03d}",
                            category=ReviewCategory.STYLE,
                            severity=Severity.INFO,
                            file=file_path,
                            line=line_no,
                            title=f"Function '{node.name}' violates PEP 8 snake_case convention",
                            description=f"Function names in Python should follow snake_case naming style.",
                            impact="Inconsistent API style and reduced code readability.",
                            suggestion=f"Rename '{node.name}' to '{snake_name}'.",
                            suggested_patch=f"def {snake_name}(...):",
                            confidence=0.90,
                        )
                    )

            # 2. Bare except clauses
            elif isinstance(node, ast.Try):
                for handler in node.handlers:
                    if handler.type is None:
                        line_no = self._map_ast_line_to_diff(handler.lineno, hunk)
                        findings.append(
                            Finding(
                                id=f"FINDING-{start_id + len(findings):03d}",
                                category=ReviewCategory.RISK,
                                severity=Severity.MAJOR,
                                file=file_path,
                                line=line_no,
                                title="Bare 'except:' catches all exceptions including system interrupts",
                                description=(
                                    "Catching an unqualified 'except:' catches BaseException, which includes "
                                    "KeyboardInterrupt and SystemExit. This makes it impossible to terminate "
                                    "the process and hides syntax or memory errors."
                                ),
                                impact="Obscures fatal application crashes and complicates debugging.",
                                suggestion="Catch specific exceptions (e.g., 'except ValueError:' or 'except Exception:').",
                                suggested_patch="except Exception as e:\n    logger.error(f'Operation failed: {e}')",
                                confidence=0.95,
                            )
                        )

            # 3. Dynamic execution / eval / exec
            elif isinstance(node, ast.Call):
                func_repr = ast.unparse(node.func) if hasattr(ast, "unparse") else ""
                if func_repr in ("eval", "exec"):
                    line_no = self._map_ast_line_to_diff(node.lineno, hunk)
                    findings.append(
                        Finding(
                            id=f"FINDING-{start_id + len(findings):03d}",
                            category=ReviewCategory.RISK,
                            severity=Severity.CRITICAL,
                            file=file_path,
                            line=line_no,
                            title=f"Arbitrary code execution risk with '{func_repr}()'",
                            description=(
                                f"Direct invocation of '{func_repr}()' allows arbitrary code execution "
                                f"if any user-controlled input reaches this call."
                            ),
                            impact="Remote code execution (RCE) vulnerability.",
                            suggestion="Replace dynamic execution with safe parsers like ast.literal_eval or a structured dispatcher.",
                            confidence=0.98,
                        )
                    )

        return findings

    def _analyze_patterns(self, file_path: str, hunk: DiffHunk, start_id: int) -> List[Finding]:
        findings = []

        for line in hunk.lines:
            if line.type != "+":
                continue

            content = line.content
            line_no = line.new_lineno

            # 1. SQL Injection Risk
            if re.search(r'(execute|raw_query|cursor\.execute)\s*\(\s*(f["\']|["\'].*%|.*\.format)', content, re.IGNORECASE) or \
               re.search(r'f["\'].*(SELECT|INSERT|UPDATE|DELETE)\s+.*FROM', content, re.IGNORECASE) or \
               re.search(r'(SELECT|INSERT|UPDATE|DELETE)\s+.*FROM\s+.*WHERE\s+.*\{', content, re.IGNORECASE):
                findings.append(
                    Finding(
                        id=f"FINDING-{start_id + len(findings):03d}",
                        category=ReviewCategory.RISK,
                        severity=Severity.CRITICAL,
                        file=file_path,
                        line=line_no,
                        title="Critical SQL Injection vulnerability via string formatting",
                        description=(
                            "SQL query constructed using string interpolation (f-string or .format). "
                            "Untrusted user input can alter query syntax to bypass authentication or extract sensitive data."
                        ),
                        impact="Full database compromise, unauthorized data exfiltration, authentication bypass.",
                        suggestion="Use parameterized queries with placeholders: cursor.execute('SELECT ... WHERE col = %s', (val,))",
                        suggested_patch='cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, hashed_pwd))',
                        confidence=0.98,
                    )
                )

            # 2. Insecure Hashing (MD5 / SHA1 for passwords)
            if re.search(r'hashlib\.(md5|sha1)\s*\(', content, re.IGNORECASE) or \
               re.search(r'createHash\([\'"](md5|sha1)[\'"]\)', content, re.IGNORECASE):
                findings.append(
                    Finding(
                        id=f"FINDING-{start_id + len(findings):03d}",
                        category=ReviewCategory.RISK,
                        severity=Severity.MAJOR,
                        file=file_path,
                        line=line_no,
                        title="Insecure cryptographic algorithm (MD5/SHA-1) for sensitive data",
                        description=(
                            "MD5 and SHA-1 are cryptographically broken and vulnerable to collision attacks and rainbow tables. "
                            "They must never be used for password hashing or integrity tokens."
                        ),
                        impact="Credentials can be reversed using precomputed rainbow tables within seconds.",
                        suggestion="Use a salted, slow key derivation function such as bcrypt, Argon2, or PBKDF2.",
                        suggested_patch="import bcrypt\nhashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())",
                        confidence=0.96,
                    )
                )

            # 3. Race Condition / Concurrency Bug (Check-then-Act without lock)
            if re.search(r'if\s+.*balance\s*>=\s*.*amount', content, re.IGNORECASE) or \
               re.search(r'if\s+(.*stock.*>|.*count.*>).*:', content, re.IGNORECASE):
                # Check surrounding code lines (ignoring comments) in hunk for balance deduction without transaction/lock
                code_lines = [l.content.split("#")[0].strip() for l in hunk.lines if l.type == "+"]
                code_text = "\n".join(code_lines)
                has_debit = ("-=" in code_text or "balance - amount" in code_text or "deduct" in code_text or "update_balance" in code_text)
                has_concurrency_control = any(kw in code_text for kw in ["lock", "atomic", "transaction", "select_for_update", "with_for_update", "threading.Lock"])

                if ("balance" in code_text or "stock" in code_text) and has_debit and not has_concurrency_control:
                    findings.append(
                        Finding(
                            id=f"FINDING-{start_id + len(findings):03d}",
                            category=ReviewCategory.BUG,
                            severity=Severity.CRITICAL,
                            file=file_path,
                            line=line_no,
                            title="TOCTOU Concurrency Race Condition in financial transaction",
                            description=(
                                "Balance is verified and deducted in non-atomic steps without a database row lock or transaction lock. "
                                "Concurrent requests can pass the balance check simultaneously, resulting in double-spending or negative balances."
                            ),
                            impact="Double spending, negative wallet balance, financial loss.",
                            suggestion="Wrap the operation in a database transaction with 'SELECT ... FOR UPDATE' or an atomic distributed lock.",
                            suggested_patch="with db.transaction():\n    account = db.query(Account).filter_by(id=acc_id).with_for_update().one()\n    if account.balance >= amount:\n        account.balance -= amount",
                            confidence=0.92,
                        )
                    )

            # 4. Floating Point for Currency / Monetary amounts
            if re.search(r'amount\s*=\s*float\(', content) or re.search(r'price\s*:\s*float', content) or re.search(r'balance\s*\+=\s*float\(', content):
                findings.append(
                    Finding(
                        id=f"FINDING-{start_id + len(findings):03d}",
                        category=ReviewCategory.RISK,
                        severity=Severity.MAJOR,
                        file=file_path,
                        line=line_no,
                        title="Use of IEEE 754 floating point for currency calculations",
                        description=(
                            "Floating-point numbers cannot precisely represent base-10 decimals (e.g., 0.1 + 0.2 != 0.3). "
                            "Over time, financial calculations will accumulate rounding discrepancies and loss of precision."
                        ),
                        impact="Accounting inaccuracies, penny-shaving discrepancies in customer balances.",
                        suggestion="Use decimal.Decimal in Python or store amounts as integers in the lowest currency unit (cents).",
                        suggested_patch="from decimal import Decimal\namount = Decimal(str(raw_amount))",
                        confidence=0.93,
                    )
                )

            # 5. Off-by-one or boundary condition bugs
            if re.search(r'if\s+.*count\s*>\s*MAX_.*:|if\s+.*days\s*>\s*THRESHOLD|if\s+.*total\s*>\s*1000', content):
                findings.append(
                    Finding(
                        id=f"FINDING-{start_id + len(findings):03d}",
                        category=ReviewCategory.BUG,
                        severity=Severity.MINOR,
                        file=file_path,
                        line=line_no,
                        title="Potential off-by-one boundary check (strict inequality '>' used)",
                        description=(
                            f"Strict inequality check in '{content.strip()}'. Verify if boundary value should be inclusive (>=) "
                            f"to prevent boundary exclusion."
                        ),
                        impact="Edge-case tier or threshold misses exact boundary conditions.",
                        suggestion="Confirm business requirement whether threshold includes the boundary value ('>=' vs '>').",
                        confidence=0.75,
                    )
                )

            # 6. Resource Leak: open() without context manager
            if re.search(r'=\s*open\s*\(', content) and not re.search(r'with\s+open\s*\(', content):
                # Verify if 'with' appears on that line
                if not content.strip().startswith("with "):
                    findings.append(
                        Finding(
                            id=f"FINDING-{start_id + len(findings):03d}",
                            category=ReviewCategory.BUG,
                            severity=Severity.MAJOR,
                            file=file_path,
                            line=line_no,
                            title="Unmanaged file resource (open without 'with' statement)",
                            description=(
                                "File opened without a 'with' context manager. If an exception occurs before file.close(), "
                                "the file descriptor remains leaked open in memory."
                            ),
                            impact="Operating system file descriptor exhaustion under load or on repeated errors.",
                            suggestion="Use 'with open(...) as f:' to guarantee deterministic cleanup.",
                            suggested_patch="with open(filepath, 'r', encoding='utf-8') as f:\n    data = f.read()",
                            confidence=0.94,
                        )
                    )

            # 7. Unbounded memory read (f.read() on large file)
            if re.search(r'\.(read|readlines)\s*\(\s*\)', content) and ("data" in content or "file" in content):
                findings.append(
                    Finding(
                        id=f"FINDING-{start_id + len(findings):03d}",
                        category=ReviewCategory.RISK,
                        severity=Severity.MINOR,
                        file=file_path,
                        line=line_no,
                        title="Unbounded memory consumption via whole-file read",
                        description=(
                            "Reading the entire file into memory with .read() without chunking or size limits. "
                            "Processing large uploads or multi-gigabyte log files will cause an Out-Of-Memory (OOM) crash."
                        ),
                        impact="Worker process crash / Denial of Service due to high memory usage.",
                        suggestion="Stream the file in fixed-size chunks (e.g. while chunk := f.read(8192):) or iterate line by line.",
                        confidence=0.85,
                    )
                )

            # 8. Hardcoded secrets / API keys
            if re.search(r'(api_key|secret|password|auth_token)\s*=\s*["\'][a-zA-Z0-9_\-]{16,}["\']', content, re.IGNORECASE):
                findings.append(
                    Finding(
                        id=f"FINDING-{start_id + len(findings):03d}",
                        category=ReviewCategory.RISK,
                        severity=Severity.CRITICAL,
                        file=file_path,
                        line=line_no,
                        title="Hardcoded credentials / secret token in source code",
                        description=(
                            "Detected plaintext secret or credential assigned directly in code. "
                            "Hardcoded secrets in version control will be exposed to all repository readers and history."
                        ),
                        impact="Credential leak and unauthorized infrastructure access.",
                        suggestion="Load secrets from environment variables or a secret vault (e.g. os.getenv('API_KEY')).",
                        suggested_patch="import os\nAPI_KEY = os.environ.get('API_KEY')",
                        confidence=0.98,
                    )
                )

            # 9. Style: Long lines
            if len(content) > 120:
                findings.append(
                    Finding(
                        id=f"FINDING-{start_id + len(findings):03d}",
                        category=ReviewCategory.STYLE,
                        severity=Severity.INFO,
                        file=file_path,
                        line=line_no,
                        title=f"Line length exceeds 120 characters ({len(content)} chars)",
                        description="Code line exceeds recommended maximum line length, making side-by-side diff review difficult.",
                        impact="Reduced readability in terminal and code review tools.",
                        suggestion="Break line across multiple lines or extract temporary variables.",
                        confidence=0.90,
                    )
                )

        return findings

    def _analyze_missing_tests(
        self,
        file_diff: FileDiff,
        hunk: DiffHunk,
        has_tests_in_diff: bool,
        finding_counter: int,
    ) -> List[Finding]:
        findings = []
        file_path = file_diff.new_path or file_diff.old_path

        # If this is already a test file, do not flag missing tests
        if "test" in file_path.lower() or "spec" in file_path.lower():
            return findings

        # Look for new function definitions in hunk additions
        for line in hunk.lines:
            if line.type == "+" and (line.content.strip().startswith("def ") or line.content.strip().startswith("async def ")):
                fn_match = re.search(r"def\s+([a-zA-Z0-9_]+)\s*\(", line.content)
                if fn_match:
                    fn_name = fn_match.group(1)
                    if fn_name.startswith("__"):
                        continue  # Skip magic dunder methods

                    # Check coverage via test inspector tool
                    tool_obs = self.test_inspector.run(
                        target_file=file_path,
                        function_name=fn_name,
                        diff_content="",
                    )

                    if not has_tests_in_diff:
                        findings.append(
                            Finding(
                                id=f"FINDING-{finding_counter + len(findings):03d}",
                                category=ReviewCategory.TEST,
                                severity=Severity.MAJOR,
                                file=file_path,
                                line=line.new_lineno,
                                title=f"Missing unit test coverage for new function '{fn_name}'",
                                description=(
                                    f"New function '{fn_name}' was introduced in '{file_path}', but the code change "
                                    f"does not include any unit test additions. {tool_obs}"
                                ),
                                impact="Unverified logic may introduce regressions unnoticed by CI.",
                                suggestion=f"Add unit tests in a corresponding test file validating normal execution, boundary inputs, and error states for '{fn_name}'.",
                                suggested_patch=f"def test_{fn_name}_success():\n    # Test normal behavior\n    pass\n\ndef test_{fn_name}_error():\n    # Test error handling\n    pass",
                                confidence=0.92,
                            )
                        )
        return findings

    def _map_ast_line_to_diff(self, ast_lineno: int, hunk: DiffHunk) -> Optional[int]:
        """Map AST relative line to real file line in diff hunk."""
        added_lines = [l for l in hunk.lines if l.type == "+"]
        if 1 <= ast_lineno <= len(added_lines):
            return added_lines[ast_lineno - 1].new_lineno
        return hunk.new_start

    def _generate_summary(self, findings: List[Finding]) -> ReviewSummary:
        bugs = sum(1 for f in findings if f.category == ReviewCategory.BUG)
        risks = sum(1 for f in findings if f.category == ReviewCategory.RISK)
        tests = sum(1 for f in findings if f.category == ReviewCategory.TEST)
        styles = sum(1 for f in findings if f.category == ReviewCategory.STYLE)

        critical_count = sum(1 for f in findings if f.severity == Severity.CRITICAL)
        major_count = sum(1 for f in findings if f.severity == Severity.MAJOR)

        if critical_count > 0:
            verdict = Verdict.REQUEST_CHANGES
            exec_sum = (
                f"REQUEST CHANGES: Found {critical_count} critical and {major_count} major issue(s). "
                f"Severe vulnerabilities or bugs must be remediated prior to merge."
            )
        elif major_count > 0 or tests > 0:
            verdict = Verdict.NEEDS_DISCUSSION
            exec_sum = (
                f"NEEDS DISCUSSION: Found {len(findings)} finding(s) including {risks} risk(s) and {tests} missing test(s). "
                f"Test coverage and identified edge cases require attention."
            )
        else:
            verdict = Verdict.APPROVED
            exec_sum = (
                f"APPROVED: Code changes look clean. Found {len(findings)} minor/style item(s) that can be addressed optionally."
            )

        return ReviewSummary(
            total_findings=len(findings),
            bugs_count=bugs,
            risks_count=risks,
            missing_tests_count=tests,
            style_count=styles,
            verdict=verdict,
            executive_summary=exec_sum,
        )
