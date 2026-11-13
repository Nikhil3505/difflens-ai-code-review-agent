"""DiffLens AI Code Review Agent - Comprehensive Demo Script.

Demonstrates the agent reviewing 4 realistic pull request diffs:
1. Auth SQL Injection & Insecure Hashing
2. Payment Concurrency Race Condition
3. E-commerce Discount Boundary Bug & Missing Tests
4. Data Pipeline Resource & Memory Leak
"""

import os
import sys
from diff_lens.agent import CodeReviewAgent
from diff_lens.cli import format_console_report, format_markdown_report


def run_demo(output_format: str = "console"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    samples_dir = os.path.join(base_dir, "samples")
    dummy_repo = os.path.join(samples_dir, "dummy_repo")

    sample_files = [
        ("01_auth_sql_injection.diff", "Scenario 1: Authentication Security & Missing Tests"),
        ("02_payment_race_condition.diff", "Scenario 2: Financial Concurrency & Precision Risks"),
        ("03_checkout_missing_tests.diff", "Scenario 3: Business Logic Edge-cases & Missing Tests"),
        ("04_data_pipeline_leak.diff", "Scenario 4: System Resource Leak & Memory Limits"),
    ]

    print("\n" + "=" * 80)
    print("               🚀 DiffLens AI Code Review Agent - Live Demo")
    print("=" * 80)
    print("DiffLens parses unified git diffs, investigates with tools (context inspection,")
    print("workspace test scanning, AST analysis), and returns structured feedback across:")
    print("  1. 🐛 Possible Bugs")
    print("  2. 🛡️  Risks & Security Vulnerabilities")
    print("  3. 🧪 Missing Tests")
    print("  4. 🎨 Style Issues & Antipatterns")
    print("=" * 80 + "\n")

    # Initialize agent pointing to dummy_repo for file & test inspection
    agent = CodeReviewAgent(repo_root=dummy_repo)

    for filename, title in sample_files:
        diff_path = os.path.join(samples_dir, filename)
        if not os.path.exists(diff_path):
            print(f"Skipping {filename} (not found)")
            continue

        print(f"\n>>>> Executing Review for: {title} ({filename})")
        report = agent.review_file(diff_path)

        if output_format == "markdown":
            print(format_markdown_report(report))
        elif output_format == "json":
            print(report.model_dump_json(indent=2))
        else:
            print(format_console_report(report))

        print("-" * 80)

    print("\n🎉 Demo completed successfully for all 4 scenarios!")
    print("You can run interactive reviews on any git repo or diff via:")
    print("  python -m diff_lens review --file <patch.diff>")
    print("  python -m diff_lens review --staged")
    print("  python -m diff_lens serve --port 8000 (Interactive Web Dashboard)")


if __name__ == "__main__":
    fmt = sys.argv[1] if len(sys.argv) > 1 else "console"
    run_demo(output_format=fmt)

