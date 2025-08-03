#!/bin/bash

# Copy migrations script for the assistant
# This script copies migration files from the source root back to the current project

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

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SOURCE_ROOT="$HOME/agents/template"

SOURCE_MIGRATIONS="$SOURCE_ROOT/internal/store/migrations/"
TARGET_MIGRATIONS="$PROJECT_ROOT/internal/store/migrations/"

print_status "📋 Copying migration files back to project..."

# Check if source directory exists
if [ ! -d "$SOURCE_MIGRATIONS" ]; then
    print_error "Source migrations directory not found at: $SOURCE_MIGRATIONS"
    exit 1
fi

# Create target directory if it doesn't exist
mkdir -p "$TARGET_MIGRATIONS"

# Copy migration files
if rsync -av "$SOURCE_MIGRATIONS" "$TARGET_MIGRATIONS"; then
    print_status "✅ Migration files copied successfully!"
    print_status "   From: $SOURCE_MIGRATIONS"
    print_status "   To: $TARGET_MIGRATIONS"

    # List the copied files
    if [ -d "$TARGET_MIGRATIONS/versions" ]; then
        print_status "📁 Migration files in versions directory:"
        ls -la "$TARGET_MIGRATIONS/versions/" | grep -v "^total" | tail -n +2
    fi
else
    print_error "❌ Failed to copy migration files"
    exit 1
fi
