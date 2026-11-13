"""Unit tests for UnifiedDiffParser."""

import pytest
from diff_lens.parser import UnifiedDiffParser


SAMPLE_DIFF = """diff --git a/app.py b/app.py
index 1234567..89abcdef 100644
--- a/app.py
+++ b/app.py
@@ -10,4 +10,6 @@ def main():
     print("Hello")
-    return 0
+    print("World")
+    return 1
"""


def test_parser_basic():
    parser = UnifiedDiffParser()
    result = parser.parse(SAMPLE_DIFF)

    assert len(result.files) == 1
    file_diff = result.files[0]
    assert file_diff.old_path == "app.py"
    assert file_diff.new_path == "app.py"
    assert file_diff.added_lines_count == 2
    assert file_diff.deleted_lines_count == 1
    assert len(file_diff.hunks) == 1

    hunk = file_diff.hunks[0]
    assert hunk.old_start == 10
    assert hunk.new_start == 10

    # Verify line numbers
    added_lines = [l for l in hunk.lines if l.type == "+"]
    assert len(added_lines) == 2
    assert added_lines[0].content == '    print("World")'
    assert added_lines[0].new_lineno == 11
    assert added_lines[1].content == '    return 1'
    assert added_lines[1].new_lineno == 12


def test_parser_empty():
    parser = UnifiedDiffParser()
    result = parser.parse("")
    assert len(result.files) == 0
    assert result.total_added == 0
    assert result.total_deleted == 0


def test_parser_added_file():
    diff = """--- /dev/null
+++ b/new_module.py
@@ -0,0 +1,3 @@
+def new_func():
+    pass
"""
    parser = UnifiedDiffParser()
    result = parser.parse(diff)
    assert len(result.files) == 1
    assert result.files[0].change_type == "added"
    assert result.files[0].new_path == "new_module.py"

