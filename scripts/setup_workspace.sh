#!/bin/bash

# Workspace setup script for Car Assistant
# This script handles common setup tasks like syncing code and setting up the environment

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
BUILD_FLAG=true
while [[ $# -gt 0 ]]; do
    case $1 in
        --build)
            BUILD_FLAG=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

FILES_ROOT="$(pwd)"
ENV_FILE="$FILES_ROOT/.env"
PROJECT_ROOT="$HOME/agents/template"

print_status "🔧 Setting up workspace..."

if [ ! -d "$PROJECT_ROOT" ]; then
    mkdir -p "$PROJECT_ROOT"
fi

# Copy current directory to high_agent with conditional --delete
if [ "$BUILD_FLAG" = true ]; then
    print_status "Building with clean sync (--delete)..."
    rsync -av --delete --exclude-from='.deployignore' $FILES_ROOT/ $PROJECT_ROOT
else
    print_status "Syncing changes without deletion..."
    rsync -av --exclude-from='.deployignore' $FILES_ROOT/ $PROJECT_ROOT
fi

# Copy .env file from root if it exists
if [ -f "$ENV_FILE" ]; then
    print_status "Copying .env file from root directory..."
    rsync -av $ENV_FILE $PROJECT_ROOT/.env
fi

# Change directory to high_agent
print_status "Changing to workspace directory..."
cd $PROJECT_ROOT

# Check if .env file exists
if [ ! -f .env ]; then
    print_error ".env file not found. Please create it and try again."
    cd $FILES_ROOT
    exit 1
fi

# Create necessary directories
mkdir -p logs

# Install dependencies if needed
if [ ! -d ".venv" ]; then
    print_status "Creating virtual environment and installing dependencies..."
    if ! (export PIPENV_VENV_IN_PROJECT=1 && pipenv --python 3.12 && pipenv install); then
        print_error "Failed to create virtual environment ensure that python3-pipenv is installed"
        cd $FILES_ROOT
        exit 1
    fi
fi

print_status "Virtual environment is ready for use with 'pipenv run'"

print_status "✅ Workspace setup complete!"
print_status "Current directory: $FILES_ROOT"
