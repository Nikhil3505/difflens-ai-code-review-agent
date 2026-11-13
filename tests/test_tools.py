"""Unit tests for Agent Tools."""

import os
import tempfile
import pytest
from diff_lens.tools import (
    FileContextInspector,
    TestCoverageInspector,
    StaticASTAnalyzer,
)


def test_file_context_inspector():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "example.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("line 1\nline 2\nline 3\nline 4\nline 5\n")

        inspector = FileContextInspector(repo_root=tmpdir)
        obs = inspector.run("example.py", start_line=2, end_line=4)
        assert "line 2" in obs
        assert "line 3" in obs
        assert "line 4" in obs
        assert "line 1" not in obs
        assert "line 5" not in obs


def test_test_coverage_inspector():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create app and test file
        tests_dir = os.path.join(tmpdir, "tests")
        os.makedirs(tests_dir)
        with open(os.path.join(tests_dir, "test_auth.py"), "w", encoding="utf-8") as f:
            f.write("def test_login(): pass\n")

        inspector = TestCoverageInspector(repo_root=tmpdir)
        obs = inspector.run("auth.py", function_name="login")
        assert "YES" in obs or "test_auth.py" in obs

        # Function not in tests
        obs_missing = inspector.run("auth.py", function_name="non_existent_fn")
        assert "WARNING: Function 'non_existent_fn' has NO existing test mentions" in obs_missing


def test_static_ast_analyzer_mutable_defaults():
    analyzer = StaticASTAnalyzer()
    bad_code = "def append_to(item, target=[]):\n    target.append(item)\n    return target\n"
    res = analyzer.run(bad_code)
    assert "Mutable default argument" in res


def test_static_ast_analyzer_bare_except():
    analyzer = StaticASTAnalyzer()
    bad_code = "try:\n    1 / 0\nexcept:\n    pass\n"
    res = analyzer.run(bad_code)
    assert "Bare 'except:' clause caught" in res


def test_static_ast_analyzer_sql_injection():
    analyzer = StaticASTAnalyzer()
    bad_code = 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")'
    res = analyzer.run(bad_code)
    assert "SQL Injection" in res


def test_static_ast_analyzer_insecure_md5():
    analyzer = StaticASTAnalyzer()
    bad_code = "h = hashlib.md5(b'secret').hexdigest()"
    res = analyzer.run(bad_code)
    assert "Insecure cryptographic hash 'hashlib.md5'" in res

