#!/bin/bash
# Test runner script for Shipments Processing Platform
# This script provides different testing scenarios and configurations

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
VERBOSE=false
COVERAGE=false
PARALLEL=false
STOP_ON_FIRST_FAIL=false
MARKERS=""
TEST_PATH=""

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show help
show_help() {
    cat << EOF
🧪 Shipments Processing Platform - Test Runner

Usage: ./run-tests.sh [OPTIONS] [TEST_TYPE]

TEST_TYPES:
    unit           Run only unit tests
    integration    Run only integration tests
    e2e            Run only end-to-end tests
    smoke          Run smoke tests for quick validation
    all            Run all tests (default)

OPTIONS:
    -v, --verbose          Enable verbose output
    -c, --coverage         Generate coverage report
    -p, --parallel         Run tests in parallel
    -x, --stop-on-fail     Stop on first failure
    -m, --marker MARKER    Run tests with specific marker
    -t, --path PATH        Run tests from specific path
    -h, --help             Show this help message

EXAMPLES:
    ./run-tests.sh unit                    # Run unit tests only
    ./run-tests.sh e2e -v                  # Run E2E tests with verbose output
    ./run-tests.sh all -c -p               # Run all tests with coverage and parallel
    ./run-tests.sh -m "database"           # Run tests marked with 'database'
    ./run-tests.sh -t tests/unit/          # Run tests from specific directory
    ./run-tests.sh integration --coverage  # Run integration tests with coverage

MARKERS:
    unit, integration, e2e, slow, smoke, performance, database, storage, email

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -c|--coverage)
                COVERAGE=true
                shift
                ;;
            -p|--parallel)
                PARALLEL=true
                shift
                ;;
            -x|--stop-on-fail)
                STOP_ON_FIRST_FAIL=true
                shift
                ;;
            -m|--marker)
                MARKERS="$2"
                shift 2
                ;;
            -t|--path)
                TEST_PATH="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            unit|integration|e2e|smoke|all|performance)
                TEST_TYPE="$1"
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
}

# Check dependencies
check_dependencies() {
    print_status "Checking dependencies..."
    
    # Check if pytest is installed
    if ! command -v pytest &> /dev/null; then
        print_error "pytest is not installed. Please install it: pip install pytest"
        exit 1
    fi
    
    # Check if coverage is needed and available
    if [[ "$COVERAGE" == true ]] && ! python -c "import pytest_cov" &> /dev/null; then
        print_warning "pytest-cov is not installed. Installing..."
        pip install pytest-cov
    fi
    
    # Check if parallel execution is requested and pytest-xdist is available
    if [[ "$PARALLEL" == true ]] && ! python -c "import xdist" &> /dev/null; then
        print_warning "pytest-xdist is not installed. Installing..."
        pip install pytest-xdist
    fi
    
    print_success "Dependencies check completed"
}

# Setup test environment
setup_environment() {
    print_status "Setting up test environment..."
    
    # Set environment variables for testing
    export TESTING=true
    export GCP_PROJECT_ID="test-project"
    export GCS_BUCKET="test-bucket"
    export PYTHONPATH="${PYTHONPATH}:$(pwd)/services/shared_utils/src"
    
    # Create temporary directories if needed
    mkdir -p .pytest_cache
    mkdir -p htmlcov
    
    print_success "Test environment setup completed"
}

# Build pytest command
build_pytest_command() {
    local cmd="pytest"
    
    # Add test path
    if [[ -n "$TEST_PATH" ]]; then
        cmd="$cmd $TEST_PATH"
    elif [[ -n "$TEST_TYPE" && "$TEST_TYPE" != "all" ]]; then
        case $TEST_TYPE in
            unit)
                cmd="$cmd tests/unit/"
                ;;
            integration)
                cmd="$cmd tests/integration/"
                ;;
            e2e)
                cmd="$cmd tests/integration/test_end_to_end_flow.py"
                ;;
            smoke)
                cmd="$cmd -m smoke"
                ;;
            performance)
                cmd="$cmd -m performance"
                ;;
        esac
    else
        cmd="$cmd tests/"
    fi
    
    # Add markers
    if [[ -n "$MARKERS" ]]; then
        cmd="$cmd -m $MARKERS"
    fi
    
    # Add coverage
    if [[ "$COVERAGE" == true ]]; then
        cmd="$cmd --cov=services --cov-report=html --cov-report=term-missing --cov-fail-under=80"
    fi
    
    # Add parallel execution
    if [[ "$PARALLEL" == true ]]; then
        # Use number of CPU cores
        local cores=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
        cmd="$cmd -n $cores"
    fi
    
    # Add verbose output
    if [[ "$VERBOSE" == true ]]; then
        cmd="$cmd -v -s"
    fi
    
    # Add stop on first failure
    if [[ "$STOP_ON_FIRST_FAIL" == true ]]; then
        cmd="$cmd -x"
    fi
    
    # Add common options
    cmd="$cmd --tb=short --color=yes"
    
    echo "$cmd"
}

# Run tests
run_tests() {
    local cmd=$(build_pytest_command)
    
    print_status "Running tests with command: $cmd"
    echo
    
    # Execute the command
    if eval "$cmd"; then
        print_success "All tests passed!"
        
        # Show coverage report location if generated
        if [[ "$COVERAGE" == true ]]; then
            print_status "Coverage report generated in htmlcov/index.html"
        fi
        
        return 0
    else
        print_error "Some tests failed!"
        return 1
    fi
}

# Cleanup function
cleanup() {
    print_status "Cleaning up test environment..."
    # Remove any temporary test files if needed
    # This could include test databases, temporary files, etc.
}

# Main execution
main() {
    # Set default test type if not provided
    TEST_TYPE="${TEST_TYPE:-all}"
    
    echo "🧪 Shipments Processing Platform - Test Runner"
    echo "================================================"
    echo
    
    # Parse arguments
    parse_args "$@"
    
    # Check dependencies
    check_dependencies
    echo
    
    # Setup environment
    setup_environment
    echo
    
    # Run tests
    print_status "Test configuration:"
    print_status "  Type: $TEST_TYPE"
    print_status "  Verbose: $VERBOSE"
    print_status "  Coverage: $COVERAGE"
    print_status "  Parallel: $PARALLEL"
    print_status "  Markers: ${MARKERS:-none}"
    print_status "  Path: ${TEST_PATH:-default}"
    echo
    
    # Execute tests
    if run_tests; then
        exit_code=0
    else
        exit_code=1
    fi
    
    # Cleanup
    cleanup
    
    echo
    if [[ $exit_code -eq 0 ]]; then
        print_success "🎉 Test execution completed successfully!"
    else
        print_error "❌ Test execution completed with failures!"
    fi
    
    exit $exit_code
}

# Trap cleanup on exit
trap cleanup EXIT

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
