"""Command Line Interface for DiffLens."""

import argparse
import json
import os
import sys
from typing import Optional
from colorama import init, Fore, Style
from tabulate import tabulate

from diff_lens.agent import CodeReviewAgent
from diff_lens.models import ReviewReport, ReviewCategory, Severity, Verdict

init(autoreset=True)


def format_console_report(report: ReviewReport) -> str:
    """Format the review report with colors and structured tables for terminal output."""
    lines = []
    lines.append(f"{Style.BRIGHT}{Fore.CYAN}{'=' * 75}")
    lines.append(f"{Style.BRIGHT}{Fore.CYAN}       DiffLens Autonomous AI Code Review Agent - Report")
    lines.append(f"{Style.BRIGHT}{Fore.CYAN}{'=' * 75}{Style.RESET_ALL}\n")

    # Meta
    lines.append(f"{Style.BRIGHT}Target Source:{Style.RESET_ALL} {report.target_source}")
    lines.append(f"{Style.BRIGHT}Files Checked:{Style.RESET_ALL} {', '.join(report.files_reviewed) or 'None'}")
    lines.append(f"{Style.BRIGHT}Execution Mode:{Style.RESET_ALL} {report.mode}")
    lines.append(f"{Style.BRIGHT}Audit Time:{Style.RESET_ALL}     {report.execution_time_seconds}s\n")

    # Verdict Banner
    verdict = report.summary.verdict
    if verdict == Verdict.APPROVED:
        v_color = Fore.GREEN
    elif verdict == Verdict.NEEDS_DISCUSSION:
        v_color = Fore.YELLOW
    else:
        v_color = Fore.RED

    lines.append(f"{v_color}{Style.BRIGHT}VERDICT: [{verdict.value}] - {report.summary.executive_summary}{Style.RESET_ALL}\n")

    # Category Summary Table
    summary_data = [
        ["Possible Bugs", report.summary.bugs_count, Fore.RED + "[BUG]" + Style.RESET_ALL],
        ["Security / System Risks", report.summary.risks_count, Fore.LIGHTRED_EX + "[RISK]" + Style.RESET_ALL],
        ["Missing Tests", report.summary.missing_tests_count, Fore.YELLOW + "[TEST]" + Style.RESET_ALL],
        ["Style & Antipatterns", report.summary.style_count, Fore.MAGENTA + "[STYLE]" + Style.RESET_ALL],
    ]
    lines.append(tabulate(summary_data, headers=["Category", "Count", "Tag"], tablefmt="rounded"))
    lines.append("")

    # Tool Execution Audit Trail
    if report.tool_calls:
        lines.append(f"{Style.BRIGHT}{Fore.BLUE}--- Agent Tool Invocation Audit ({len(report.tool_calls)} calls) ---{Style.RESET_ALL}")
        tool_rows = []
        for tc in report.tool_calls:
            tool_rows.append([
                f"Step {tc.step}",
                tc.tool_name,
                (tc.reasoning or "")[:50],
                tc.observation[:60] + "..." if len(tc.observation) > 60 else tc.observation,
            ])
        lines.append(tabulate(tool_rows, headers=["Step", "Tool", "Agent Reasoning", "Observation Preview"], tablefmt="simple"))
        lines.append("")

    # Detailed Findings
    if not report.findings:
        lines.append(f"{Fore.GREEN}No issues identified! Code change passed all criteria.{Style.RESET_ALL}\n")
    else:
        lines.append(f"{Style.BRIGHT}{Fore.CYAN}--- Detailed Structured Findings ({len(report.findings)}) ---{Style.RESET_ALL}\n")
        for idx, f in enumerate(report.findings, 1):
            if f.category == ReviewCategory.BUG:
                cat_color = Fore.RED
            elif f.category == ReviewCategory.RISK:
                cat_color = Fore.LIGHTRED_EX
            elif f.category == ReviewCategory.TEST:
                cat_color = Fore.YELLOW
            else:
                cat_color = Fore.MAGENTA

            sev_color = Fore.RED if f.severity == Severity.CRITICAL else (Fore.YELLOW if f.severity == Severity.MAJOR else Fore.BLUE)

            lines.append(f"{Style.BRIGHT}#{idx}. [{f.id}] {cat_color}[{f.category.value}]{Style.RESET_ALL} {sev_color}[{f.severity.value}]{Style.RESET_ALL} {Style.BRIGHT}{f.title}{Style.RESET_ALL}")
            lines.append(f"    {Fore.WHITE}File:{Style.RESET_ALL} {f.file}:{f.line or 'N/A'}")
            lines.append(f"    {Fore.WHITE}Description:{Style.RESET_ALL} {f.description}")
            if f.impact:
                lines.append(f"    {Fore.LIGHTYELLOW_EX}Impact:{Style.RESET_ALL} {f.impact}")
            lines.append(f"    {Fore.GREEN}Suggestion:{Style.RESET_ALL} {f.suggestion}")
            if f.suggested_patch:
                lines.append(f"    {Fore.LIGHTCYAN_EX}Suggested Patch:{Style.RESET_ALL}")
                for pl in f.suggested_patch.splitlines():
                    lines.append(f"        {pl}")
            lines.append("")

    return "\n".join(lines)


def format_markdown_report(report: ReviewReport) -> str:
    """Format report as GitHub PR Comment compatible Markdown."""
    md = []
    md.append("# 🔍 DiffLens AI Code Review Report\n")
    md.append(f"**Target:** `{report.target_source}` | **Mode:** `{report.mode}` | **Audit Time:** {report.execution_time_seconds}s\n")

    # Verdict
    verdict_badge = {
        Verdict.APPROVED: "✅ **APPROVED**",
        Verdict.NEEDS_DISCUSSION: "⚠️ **NEEDS DISCUSSION**",
        Verdict.REQUEST_CHANGES: "❌ **REQUEST CHANGES**",
    }[report.summary.verdict]

    md.append(f"### Verdict: {verdict_badge}\n> {report.summary.executive_summary}\n")

    # Metrics table
    md.append("### 📊 Metrics Summary\n")
    md.append("| Category | Count | Status |")
    md.append("| :--- | :---: | :--- |")
    md.append(f"| 🐛 **Possible Bugs** | {report.summary.bugs_count} | {'⚠️ Review needed' if report.summary.bugs_count else '✅ Clean'} |")
    md.append(f"| 🛡️ **Risks & Security** | {report.summary.risks_count} | {'❌ Critical' if report.summary.risks_count else '✅ Clean'} |")
    md.append(f"| 🧪 **Missing Tests** | {report.summary.missing_tests_count} | {'⚠️ Add coverage' if report.summary.missing_tests_count else '✅ Covered'} |")
    md.append(f"| 🎨 **Style & Conventions** | {report.summary.style_count} | {'ℹ️ Suggestions' if report.summary.style_count else '✅ Clean'} |\n")

    # Tool calls fold
    if report.tool_calls:
        md.append("<details><summary><b>🛠️ Agent Tool Invocations</b></summary>\n")
        md.append("| Step | Tool | Goal | Result |")
        md.append("| :--- | :--- | :--- | :--- |")
        for tc in report.tool_calls:
            clean_obs = tc.observation.replace("\n", " ").replace("|", "\\|")[:80]
            md.append(f"| {tc.step} | `{tc.tool_name}` | {tc.reasoning or ''} | {clean_obs} |")
        md.append("\n</details>\n")

    # Findings
    md.append("### 📝 Findings & Feedback\n")
    for f in report.findings:
        icon = {"BUG": "🐛", "RISK": "🛡️", "TEST": "🧪", "STYLE": "🎨"}.get(f.category.value, "ℹ️")
        md.append(f"#### {icon} `[{f.category.value}]` {f.title}")
        md.append(f"- **Severity:** `{f.severity.value}` | **File:** `{f.file}:{f.line or 'N/A'}`")
        md.append(f"- **Description:** {f.description}")
        if f.impact:
            md.append(f"- **Impact:** {f.impact}")
        md.append(f"- **Suggestion:** {f.suggestion}")
        if f.suggested_patch:
            md.append(f"```python\n{f.suggested_patch}\n```")
        md.append("\n---\n")

    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(
        prog="diff_lens",
        description="DiffLens - Autonomous AI Code Review Agent for Git Diffs and Pull Requests.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Subcommand: review
    review_parser = subparsers.add_parser("review", help="Review a code change")
    group = review_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", "-f", type=str, help="Path to unified diff / patch file")
    group.add_argument("--staged", "-s", action="store_true", help="Review staged git changes")
    group.add_argument("--commit", "-c", type=str, help="Review changes from a commit (e.g. HEAD, HEAD~1)")
    group.add_argument("--working", "-w", action="store_true", help="Review unstaged working tree changes")

    review_parser.add_argument("--format", choices=["console", "json", "markdown"], default="console", help="Output format")
    review_parser.add_argument("--api-key", type=str, default=None, help="Gemini or OpenAI API Key")
    review_parser.add_argument("--provider", choices=["auto", "gemini", "openai"], default="auto", help="LLM Provider")
    review_parser.add_argument("--output", "-o", type=str, default=None, help="Save report to file")

    # Subcommand: demo
    demo_parser = subparsers.add_parser("demo", help="Run comprehensive demo across sample diffs")
    demo_parser.add_argument("--format", choices=["console", "json", "markdown"], default="console")

    # Subcommand: serve
    serve_parser = subparsers.add_parser("serve", help="Launch interactive web dashboard")
    serve_parser.add_argument("--host", type=str, default="127.0.0.1", help="Host binding")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to listen on")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "serve":
        from diff_lens.web.app import run_server
        run_server(host=args.host, port=args.port)
        return

    if args.command == "demo":
        from demo import run_demo
        run_demo(output_format=args.format)
        return

    if args.command == "review":
        agent = CodeReviewAgent(
            api_key=args.api_key,
            provider=args.provider,
        )

        try:
            if args.file:
                report = agent.review_file(args.file)
            elif args.staged:
                report = agent.review_staged()
            elif args.working:
                report = agent.review_working_tree()
            elif args.commit:
                report = agent.review_commit(args.commit)
            else:
                parser.print_help()
                sys.exit(1)
        except Exception as e:
            print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}", file=sys.stderr)
            sys.exit(1)

        # Output generation
        if args.format == "json":
            out_str = report.model_dump_json(indent=2)
        elif args.format == "markdown":
            out_str = format_markdown_report(report)
        else:
            out_str = format_console_report(report)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(out_str)
            print(f"Report saved to {args.output}")
        else:
            print(out_str)


if __name__ == "__main__":
    main()

