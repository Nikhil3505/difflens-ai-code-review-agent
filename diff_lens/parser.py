"""Unified Diff Parser for DiffLens."""

import re
from typing import List, Optional
from diff_lens.models import ParsedDiff, FileDiff, DiffHunk, DiffLine


class UnifiedDiffParser:
    """Robust parser for Unified Diff format output from Git or patch files."""

    DIFF_HEADER_RE = re.compile(r"^diff --git a/(?P<old_path>.+?) b/(?P<new_path>.+?)$")
    OLD_FILE_RE = re.compile(r"^--- (?:a/)?(?P<path>[^\t\n]+)")
    NEW_FILE_RE = re.compile(r"^\+\+\+ (?:b/)?(?P<path>[^\t\n]+)")
    HUNK_HEADER_RE = re.compile(
        r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@(?P<header>.*)$"
    )

    def parse(self, raw_diff: str) -> ParsedDiff:
        """Parse raw unified diff text into structured ParsedDiff object."""
        if not raw_diff or not raw_diff.strip():
            return ParsedDiff(files=[], raw_diff=raw_diff, total_added=0, total_deleted=0)

        lines = raw_diff.splitlines()
        files: List[FileDiff] = []
        current_file: Optional[FileDiff] = None
        current_hunk: Optional[DiffHunk] = None
        old_lineno = 0
        new_lineno = 0

        total_added = 0
        total_deleted = 0

        i = 0
        n = len(lines)

        while i < n:
            line = lines[i]

            # 1. Match 'diff --git a/... b/...'
            git_match = self.DIFF_HEADER_RE.match(line)
            if git_match:
                if current_hunk and current_file:
                    current_file.hunks.append(current_hunk)
                    current_hunk = None
                if current_file:
                    files.append(current_file)

                old_path = git_match.group("old_path")
                new_path = git_match.group("new_path")
                current_file = FileDiff(
                    old_path=old_path,
                    new_path=new_path,
                    change_type="modified",
                    hunks=[],
                )
                i += 1
                continue

            # 2. Match '--- a/...' or '--- /dev/null'
            old_match = self.OLD_FILE_RE.match(line)
            if old_match and not current_file:
                # Diff might not have 'diff --git' header (e.g. standard patch)
                path = old_match.group("path")
                change_type = "added" if path == "/dev/null" else "modified"
                current_file = FileDiff(
                    old_path=path,
                    new_path="",
                    change_type=change_type,
                    hunks=[],
                )
                i += 1
                continue
            elif old_match and current_file:
                path = old_match.group("path")
                if path == "/dev/null":
                    current_file.change_type = "added"
                current_file.old_path = path
                i += 1
                continue

            # 3. Match '+++ b/...' or '+++ /dev/null'
            new_match = self.NEW_FILE_RE.match(line)
            if new_match and current_file:
                path = new_match.group("path")
                if path == "/dev/null":
                    current_file.change_type = "deleted"
                current_file.new_path = path
                i += 1
                continue

            # 4. Match hunk header '@@ -o,c +n,c @@'
            hunk_match = self.HUNK_HEADER_RE.match(line)
            if hunk_match:
                if not current_file:
                    current_file = FileDiff(
                        old_path="unknown",
                        new_path="unknown",
                        change_type="modified",
                        hunks=[],
                    )

                if current_hunk:
                    current_file.hunks.append(current_hunk)

                old_start = int(hunk_match.group("old_start"))
                old_count = int(hunk_match.group("old_count")) if hunk_match.group("old_count") else 1
                new_start = int(hunk_match.group("new_start"))
                new_count = int(hunk_match.group("new_count")) if hunk_match.group("new_count") else 1
                header_text = hunk_match.group("header").strip()

                current_hunk = DiffHunk(
                    old_start=old_start,
                    old_lines=old_count,
                    new_start=new_start,
                    new_lines=new_count,
                    header=header_text,
                    lines=[],
                )
                old_lineno = old_start
                new_lineno = new_start
                i += 1
                continue

            # 5. Content inside hunk
            if current_hunk is not None:
                if line.startswith("+") and not line.startswith("+++"):
                    current_hunk.lines.append(
                        DiffLine(
                            type="+",
                            content=line[1:],
                            old_lineno=None,
                            new_lineno=new_lineno,
                        )
                    )
                    new_lineno += 1
                    total_added += 1
                    if current_file:
                        current_file.added_lines_count += 1
                elif line.startswith("-") and not line.startswith("---"):
                    current_hunk.lines.append(
                        DiffLine(
                            type="-",
                            content=line[1:],
                            old_lineno=old_lineno,
                            new_lineno=None,
                        )
                    )
                    old_lineno += 1
                    total_deleted += 1
                    if current_file:
                        current_file.deleted_lines_count += 1
                elif line.startswith(" ") or line == "":
                    # Context line
                    cnt = line[1:] if line.startswith(" ") else line
                    current_hunk.lines.append(
                        DiffLine(
                            type=" ",
                            content=cnt,
                            old_lineno=old_lineno,
                            new_lineno=new_lineno,
                        )
                    )
                    old_lineno += 1
                    new_lineno += 1
                elif line.startswith(r"\ No newline at end of file"):
                    # Ignore git warning marker
                    pass
                else:
                    # Trailing metadata or unexpected line
                    pass

            i += 1

        if current_hunk and current_file:
            current_file.hunks.append(current_hunk)
        if current_file:
            files.append(current_file)

        return ParsedDiff(
            files=files,
            raw_diff=raw_diff,
            total_added=total_added,
            total_deleted=total_deleted,
        )
