#!/bin/bash

# Quipflip Localhost Integration Test Runner
# This script helps run integration tests against a running localhost backend

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Base URL for backend
BASE_URL="http://localhost:8000/qf"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Quipflip Localhost Integration Tests${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to check if server is running
check_server() {
    echo -e "${YELLOW}Checking if backend server is running...${NC}"

    if curl -s "${BASE_URL}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Server is running at ${BASE_URL}${NC}"
        return 0
    else
        echo -e "${RED}✗ Cannot connect to server at ${BASE_URL}${NC}"
        echo -e "${RED}Please start the server with:${NC}"
        echo -e "${YELLOW}  uvicorn backend.main:app --reload${NC}"
        return 1
    fi
}

# Function to show server info
show_server_info() {
    echo ""
    echo -e "${YELLOW}Server Information:${NC}"
    curl -s "${BASE_URL}/" | python3 -m json.tool 2>/dev/null || echo "Could not fetch server info"
    echo ""
}

# Function to run tests
run_tests() {
    local test_file=$1
    local test_name=$2
    shift 2  # Remove first two arguments
    local extra_args=("$@")  # Remaining arguments

    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Running: ${test_name}${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    if pytest "${test_file}" -v "${extra_args[@]}"; then
        echo -e "${GREEN}✓ ${test_name} completed successfully${NC}"
        return 0
    else
        echo -e "${RED}✗ ${test_name} failed${NC}"
        return 1
    fi
}

# Function to cleanup test data
cleanup_test_data() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Cleaning up test player data...${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    if python3 cleanup_test_players.py --yes --verbose; then
        echo -e "${GREEN}✓ Test data cleanup completed${NC}"
        return 0
    else
        echo -e "${RED}✗ Test data cleanup failed${NC}"
        return 1
    fi
}

# Parse command line arguments
TEST_TYPE="${1:-all}"
shift  # Remove first argument
EXTRA_ARGS=("$@")  # Remaining arguments as array

# Check if server is running
if ! check_server; then
    exit 1
fi

# Show server info
show_server_info

# Run appropriate tests based on argument
case "$TEST_TYPE" in
    "all")
        echo -e "${YELLOW}Running ALL localhost tests...${NC}"
        run_tests "tests/test_integration_localhost.py" "Integration Tests" "${EXTRA_ARGS[@]}"
        run_tests "tests/test_game_scenarios_localhost.py" "Game Scenario Tests" "${EXTRA_ARGS[@]}"
        run_tests "tests/test_stress_localhost.py" "Stress Tests" "${EXTRA_ARGS[@]}"
        ;;

    "integration"|"int")
        run_tests "tests/test_integration_localhost.py" "Integration Tests" "${EXTRA_ARGS[@]}"
        ;;

    "scenarios"|"game")
        run_tests "tests/test_game_scenarios_localhost.py" "Game Scenario Tests" "${EXTRA_ARGS[@]}"
        ;;

    "stress"|"load")
        run_tests "tests/test_stress_localhost.py" "Stress Tests" "${EXTRA_ARGS[@]}"
        ;;

    "quick")
        echo -e "${YELLOW}Running quick test suite (integration + scenarios)...${NC}"
        run_tests "tests/test_integration_localhost.py" "Integration Tests" "${EXTRA_ARGS[@]}"
        run_tests "tests/test_game_scenarios_localhost.py" "Game Scenario Tests" "${EXTRA_ARGS[@]}"
        ;;

    "health")
        echo -e "${YELLOW}Running health check only...${NC}"
        pytest tests/test_integration_localhost.py::TestHealthEndpoints -v "${EXTRA_ARGS[@]}"
        ;;

    "cleanup")
        cleanup_test_data
        exit 0
        ;;

    "help"|"-h"|"--help")
        echo "Usage: ./run_localhost_tests.sh [TEST_TYPE] [PYTEST_ARGS]"
        echo ""
        echo "TEST_TYPE options:"
        echo "  all          - Run all test suites (default)"
        echo "  integration  - Run integration tests only"
        echo "  scenarios    - Run game scenario tests only"
        echo "  stress       - Run stress/load tests only"
        echo "  quick        - Run integration + scenarios (skip stress)"
        echo "  health       - Run health check only"
        echo "  cleanup      - Remove all test player data from database"
        echo "  help         - Show this help message"
        echo ""
        echo "PYTEST_ARGS: Any additional pytest arguments"
        echo "  Examples:"
        echo "    -s                Show print output"
        echo "    -k test_name      Run tests matching pattern"
        echo "    --maxfail=1       Stop after first failure"
        echo ""
        echo "Examples:"
        echo "  ./run_localhost_tests.sh                     # Run all tests"
        echo "  ./run_localhost_tests.sh integration         # Integration only"
        echo "  ./run_localhost_tests.sh quick -s            # Quick tests with output"
        echo "  ./run_localhost_tests.sh all -k player       # All player-related tests"
        echo "  ./run_localhost_tests.sh cleanup             # Clean up test data"
        exit 0
        ;;

    *)
        echo -e "${RED}Unknown test type: ${TEST_TYPE}${NC}"
        echo "Run './run_localhost_tests.sh help' for usage information"
        exit 1
        ;;
esac

# Summary
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Test run complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Optional cleanup prompt
echo -e "${YELLOW}Clean up test player data from database?${NC}"
echo -e "${YELLOW}This will remove all test players and their associated data.${NC}"
read -p "Run cleanup? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    cleanup_test_data
else
    echo -e "${YELLOW}Skipping cleanup. You can run it later with:${NC}"
    echo -e "${YELLOW}  ./run_localhost_tests.sh cleanup${NC}"
    echo -e "${YELLOW}  or: python3 cleanup_test_players.py${NC}"
fi

echo ""
echo -e "${YELLOW}Tip: Check server logs for detailed request information${NC}"
echo ""
