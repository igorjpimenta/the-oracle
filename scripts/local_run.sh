#!/bin/bash

# Local development script for the assistant
# This script builds and starts the application, Redis, and Postgres containers

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse command line arguments
BUILD_FLAG=false
BUILD_API=true
BUILD_PG=true
BUILD_REDIS=true
while [[ $# -gt 0 ]]; do
    case $1 in
        --build)
            BUILD_FLAG=true
            shift
            ;;
        --no-api)
            BUILD_API=false
            shift
            ;;
        --no-postgres)
            BUILD_PG=false
            shift
            ;;
        --no-redis)
            BUILD_REDIS=false
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--build] [--no-postgres] [--no-redis]"
            echo "  --build     Build Docker images before running"
            echo "  --no-api    Don't build the application container (assumes the application is already built)"
            echo "  --no-postgres    Don't start Postgres container (assumes Postgres is already running somewhere)"
            echo "  --no-redis  Don't start Redis container (assumes Redis is already running somewhere)"
            exit 1
            ;;
    esac
done

echo "🚀 Starting the assistant API locally..."

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_ROOT/.venv"
# Database setup and migrations
print_status "Setting up database..."

setup_python_environment() {
    # Add project root to Python path so imports work from any directory
    export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
    print_status "Added $PROJECT_ROOT to PYTHONPATH"

    # Check if we're already in a virtual environment
    if [ -z "$VIRTUAL_ENV" ]; then
        # Try to activate virtual environment if it exists
        if [ -d "$VENV_DIR" ]; then
            print_status "Activating virtual environment at $VENV_DIR"
            # Check OS and activate accordingly
            if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
                # Windows (Git Bash/MSYS)
                source "$VENV_DIR/Scripts/activate" 2>/dev/null || {
                    print_warning "Could not activate Windows virtual environment"
                }
            else
                # Linux/Mac
                source "$VENV_DIR/bin/activate" 2>/dev/null || {
                    print_warning "Could not activate virtual environment"
                }
            fi
        else
            print_warning "Virtual environment not found at $VENV_DIR"
        fi
    else
        print_status "Using existing virtual environment: $VIRTUAL_ENV"
    fi
}


start_app() {
    setup_python_environment

    print_status "Starting FastAPI application..."
    print_status ""
    print_status "API will be available at: http://localhost:4000"
    print_status "API documentation: http://localhost:4000/docs"
    print_status "To stop it, run: Ctrl+C"
    print_status ""

    python -m app.main
}

# Function to start Redis container
start_redis_container() {
    print_status "Starting Redis container..."
    cd "$PROJECT_ROOT"

    if [ "$BUILD_FLAG" = true ]; then
        docker compose up -d --build redis
    else
        docker compose up -d redis
    fi

    # Wait for Redis to be healthy
    print_status "Waiting for Redis to be ready..."
    timeout=30
    counter=0
    while [ $counter -lt $timeout ]; do
        if docker compose exec -T redis redis-cli ping >/dev/null 2>&1; then
            print_status "Redis is ready!"
            break
        fi
        sleep 1
        counter=$((counter + 1))
    done

    if [ $counter -eq $timeout ]; then
        print_error "Redis failed to start within $timeout seconds"
        exit 1
    fi

    print_status "Redis container started successfully"
    print_status ""
    print_status "Redis will be available at: http://localhost:6379"
    print_status "To stop it, run: docker compose down redis"

}

# Function to start a Postgres container
start_postgres_container() {
    print_status "Starting Postgres container..."
    cd "$PROJECT_ROOT"

    if [ "$BUILD_FLAG" = true ]; then
        docker compose up -d --build postgres
    else
        docker compose up -d postgres
    fi

    print_status "Postgres container started successfully"
    print_status ""
    print_status "Postgres will be available at: http://localhost:5432"
    print_status "To stop it, run: docker compose down postgres"
}

# Main execution logic
if [ "$USE_DOCKER" = true ]; then
    # Run everything in Docker
    start_full_docker
else
    # Start Redis container if requested
    if [ "$BUILD_REDIS" = true ]; then
        start_redis_container
    fi

    if [ "$BUILD_PG" = true ]; then
        start_postgres_container
    fi

    if [ "$BUILD_API" = true ]; then
        start_app
    fi

    print_status ""
    print_status "All services started successfully"
    print_status ""
fi
