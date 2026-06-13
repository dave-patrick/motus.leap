"""Run all tests and generate coverage report."""

import subprocess
import sys
import os

def run_command(cmd, description):
    """Run a command and report results."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print('='*60)

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)

    if result.stderr:
        print("STDERR:", result.stderr)

    if result.returncode != 0:
        print(f"❌ {description} FAILED")
        return False
    else:
        print(f"✅ {description} PASSED")
        return True

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("🧪 Tube Manager Test Suite")
    print("="*60)

    os.chdir("tube-manager")

    results = []

    # 1. Unit tests
    results.append(run_command(
        "python -m pytest tests/unit/ -v --tb=short",
        "Unit Tests"
    ))

    # 2. Integration tests
    results.append(run_command(
        "python -m pytest tests/integration/ -v --tb=short",
        "Integration Tests"
    ))

    # 3. Security tests
    results.append(run_command(
        "python -m pytest tests/security/ -v --tb=short",
        "Security Tests"
    ))

    # 4. Load tests (skip on CI)
    if os.getenv("CI") != "true":
        results.append(run_command(
            "python -m pytest tests/load/ -v --tb=short -m 'not slow'",
            "Load Tests (fast)"
        ))

    # 5. All tests with coverage
    results.append(run_command(
        "python -m pytest tests/ -v --cov=. --cov-report=html --cov-report=term-missing",
        "All Tests with Coverage"
    ))

    # Summary
    print("\n" + "="*60)
    print("📊 Test Summary")
    print("="*60)

    passed = sum(results)
    total = len(results)

    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("✅ All tests passed!")
        print("\nCoverage report generated in: htmlcov/index.html")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())