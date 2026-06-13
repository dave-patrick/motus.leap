"""Generate test status report."""

import subprocess
import sys


def run_tests(category=None):
    """Run tests and return results."""
    if category:
        cmd = f"python -m pytest tests/{category}/ -v --tb=short"
    else:
        cmd = "python -m pytest tests/ -v --tb=short -m 'not slow'"

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd="tube-manager")

    return result.stdout, result.returncode


def main():
    """Generate test report."""
    print("\n" + "="*60)
    print("🧪 Tube Manager Test Status Report")
    print("="*60 + "\n")

    categories = {
        "unit": "Unit Tests",
        "integration": "Integration Tests",
        "security": "Security Tests",
        "load": "Load Tests (fast only)"
    }

    results = {}

    for cat, name in categories.items():
        print(f"\n{'='*60}")
        print(f"Testing: {name}")
        print('='*60)

        output, exit_code = run_tests(cat)

        # Parse results
        lines = output.split('\n')
        summary_line = [l for l in lines if 'passed' in l.lower() and ('error' in l.lower() or 'failed' in l.lower())]

        if summary_line:
            results[cat] = summary_line[-1]
        else:
            results[cat] = "No results"

        print(output[:500])  # First 500 chars
        if len(output) > 500:
            print(f"... ({len(output)} chars total)")

    print("\n" + "="*60)
    print("📊 Summary")
    print("="*60)

    for cat, result in results.items():
        print(f"{cat:15s}: {result}")

    print("\n" + "="*60)
    print("✨ Test Report Complete")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()