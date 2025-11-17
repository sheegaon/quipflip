#!/usr/bin/env python3
"""
Quipflip Localhost Integration Test Runner

Python-based test runner for integration tests.
Alternative to the bash script, works cross-platform.

Usage:
    python run_localhost_tests.py [test_type] [pytest_args]

Examples:
    python run_localhost_tests.py all
    python run_localhost_tests.py integration -v
    python run_localhost_tests.py quick -s
"""
import sys
import subprocess
import httpx
import json
from pathlib import Path

BASE_URL = "http://localhost:8000/qf"
TESTS_DIR = Path("tests")


class Colors:
    """ANSI color codes for terminal output."""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color


def print_header(text: str):
    """Print formatted header."""
    print(f"\n{Colors.BLUE}{'=' * 60}{Colors.NC}")
    print(f"{Colors.BLUE}{text}{Colors.NC}")
    print(f"{Colors.BLUE}{'=' * 60}{Colors.NC}\n")


def print_section(text: str):
    """Print formatted section."""
    print(f"\n{Colors.BLUE}{'━' * 60}{Colors.NC}")
    print(f"{Colors.BLUE}{text}{Colors.NC}")
    print(f"{Colors.BLUE}{'━' * 60}{Colors.NC}")


def check_server() -> bool:
    """Check if backend server is running."""
    print(f"{Colors.YELLOW}Checking if backend server is running...{Colors.NC}")

    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=5.0)
        if response.status_code == 200:
            print(f"{Colors.GREEN}Server is running at {BASE_URL}{Colors.NC}")
            return True
        else:
            print(f"{Colors.RED}Server returned status {response.status_code}{Colors.NC}")
            return False
    except httpx.ConnectError:
        print(f"{Colors.RED}Cannot connect to server at {BASE_URL}{Colors.NC}")
        print(f"{Colors.RED}Please start the server with:{Colors.NC}")
        print(f"{Colors.YELLOW}  uvicorn backend.main:app --reload{Colors.NC}")
        return False
    except Exception as e:
        print(f"{Colors.RED}Unexpected error: {e}{Colors.NC}")
        return False


def show_server_info():
    """Display server information."""
    print(f"\n{Colors.YELLOW}Server Information:{Colors.NC}")

    try:
        response = httpx.get(f"{BASE_URL}/", timeout=5.0)
        if response.status_code == 200:
            info = response.json()
            for key, value in info.items():
                print(f"  {key}: {value}")
        else:
            print("  Could not fetch server info")
    except Exception as e:
        print(f"  Error: {e}")

    print()


def run_test_file(test_file: str, test_name: str, extra_args: list) -> bool:
    """
    Run a test file with pytest.

    Args:
        test_file: Path to test file
        test_name: Display name for tests
        extra_args: Additional pytest arguments

    Returns:
        True if tests passed, False otherwise
    """
    print_section(f"Running: {test_name}")

    cmd = ["pytest", test_file, "-v"] + extra_args

    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode == 0:
            print(f"\n{Colors.GREEN}{test_name} completed successfully{Colors.NC}")
            return True
        else:
            print(f"\n{Colors.RED}{test_name} failed{Colors.NC}")
            return False
    except FileNotFoundError:
        print(f"{Colors.RED}pytest not found. Install with: pip install pytest{Colors.NC}")
        return False
    except Exception as e:
        print(f"{Colors.RED}Error running tests: {e}{Colors.NC}")
        return False


def run_tests(test_type: str, extra_args: list):
    """
    Run tests based on test type.

    Args:
        test_type: Type of tests to run
        extra_args: Additional pytest arguments
    """
    test_files = {
        "integration": ("tests/test_integration_localhost.py", "Integration Tests"),
        "scenarios": ("tests/test_game_scenarios_localhost.py", "Game Scenario Tests"),
        "stress": ("tests/test_stress_localhost.py", "Stress Tests"),
    }

    results = []

    if test_type == "all":
        print(f"{Colors.YELLOW}Running ALL localhost tests...{Colors.NC}")
        for test_file, test_name in test_files.values():
            results.append(run_test_file(test_file, test_name, extra_args))

    elif test_type == "quick":
        print(f"{Colors.YELLOW}Running quick test suite (integration + scenarios)...{Colors.NC}")
        for key in ["integration", "scenarios"]:
            test_file, test_name = test_files[key]
            results.append(run_test_file(test_file, test_name, extra_args))

    elif test_type in ["integration", "int"]:
        test_file, test_name = test_files["integration"]
        results.append(run_test_file(test_file, test_name, extra_args))

    elif test_type in ["scenarios", "game"]:
        test_file, test_name = test_files["scenarios"]
        results.append(run_test_file(test_file, test_name, extra_args))

    elif test_type in ["stress", "load"]:
        test_file, test_name = test_files["stress"]
        results.append(run_test_file(test_file, test_name, extra_args))

    elif test_type == "health":
        print(f"{Colors.YELLOW}Running health check only...{Colors.NC}")
        cmd = ["pytest", "tests/test_integration_localhost.py::TestHealthEndpoints", "-v"] + extra_args
        subprocess.run(cmd)

    else:
        print(f"{Colors.RED}Unknown test type: {test_type}{Colors.NC}")
        print_help()
        sys.exit(1)

    # Print summary
    print_header("Test Run Complete!")

    if results:
        passed = sum(results)
        total = len(results)
        if passed == total:
            print(f"{Colors.GREEN}All {total} test suites passed!{Colors.NC}")
        else:
            print(f"{Colors.YELLOW}{passed}/{total} test suites passed{Colors.NC}")
            if passed < total:
                print(f"{Colors.RED}{total - passed} test suite(s) failed{Colors.NC}")

    print(f"\n{Colors.YELLOW}Tip: Check server logs for detailed request information{Colors.NC}\n")


def print_help():
    """Print help message."""
    help_text = """
Usage: python run_localhost_tests.py [TEST_TYPE] [PYTEST_ARGS]

TEST_TYPE options:
  all          - Run all test suites (default)
  integration  - Run integration tests only
  scenarios    - Run game scenario tests only
  stress       - Run stress/load tests only
  quick        - Run integration + scenarios (skip stress)
  health       - Run health check only
  help         - Show this help message

PYTEST_ARGS: Any additional pytest arguments
  Examples:
    -s                Show print output
    -k test_name      Run tests matching pattern
    --maxfail=1       Stop after first failure
    -vv               Very verbose output

Examples:
  python run_localhost_tests.py                     # Run all tests
  python run_localhost_tests.py integration         # Integration only
  python run_localhost_tests.py quick -s            # Quick tests with output
  python run_localhost_tests.py all -k player       # All player-related tests
  python run_localhost_tests.py stress -vv          # Stress tests, very verbose
"""
    print(help_text)


def main():
    """Main entry point."""
    print_header("Quipflip Localhost Integration Tests")

    # Parse arguments
    if len(sys.argv) > 1 and sys.argv[1] in ["help", "-h", "--help"]:
        print_help()
        sys.exit(0)

    test_type = sys.argv[1] if len(sys.argv) > 1 else "all"
    extra_args = sys.argv[2:] if len(sys.argv) > 2 else []

    # Check server
    if not check_server():
        sys.exit(1)

    # Show server info
    show_server_info()

    # Run tests
    try:
        run_tests(test_type, extra_args)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Tests interrupted by user{Colors.NC}")
        sys.exit(1)


if __name__ == "__main__":
    main()
