#!/bin/bash

# Database migration script for the assistant
# This script provides utilities for managing database migrations using Alembic

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

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ALEMBIC_DIR="$PROJECT_ROOT/internal/store"
VENV_DIR="$PROJECT_ROOT/venv"

# Function to check database connectivity
check_database_connectivity() {
    print_status "Checking database connectivity..."

    # Create a temporary Python script to test database connection
    local temp_script=$(mktemp)
    cat > "$temp_script" << 'EOF'
import sys
import os
# Add the current working directory (backend) to Python path
sys.path.insert(0, os.getcwd())

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine.url import URL, make_url
    from app.core.config.settings import get_database_settings

    # Get database URL (already includes SSL for Azure)
    settings = get_database_settings()
    url_obj = settings.database_url_obj

    # Create engine with additional connect args for Azure
    connect_args = {}
    if url_obj.host and ".postgres.database.azure.com" in url_obj.host:
        connect_args = {"sslmode": "require", "connect_timeout": 30}

    engine = create_engine(url_obj, connect_args=connect_args)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        if result.scalar() == 1:
            print("SUCCESS: Database connection established")
            sys.exit(0)
        else:
            print("ERROR: Database connection test failed")
            sys.exit(1)

except ImportError as e:
    print(f"ERROR: Missing dependencies - {e}")
    print("Please install required packages: pip install psycopg2-binary")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: Database connection failed - {e}")
    print("Common causes:")
    print("  - Database server not running")
    print("  - Wrong connection credentials")
    print("  - Database does not exist")
    print("  - Network connectivity issues")
    sys.exit(1)
EOF

    # Run the connectivity check
    if python "$temp_script"; then
        print_status "✅ Database is accessible"
        rm -f "$temp_script"
        return 0
    else
        print_error "❌ Database connectivity check failed"
        rm -f "$temp_script"
        return 1
    fi
}

# Function to check if alembic directory exists
check_alembic_setup() {
    if [ ! -d "$ALEMBIC_DIR" ]; then
        print_error "Alembic directory not found at: $ALEMBIC_DIR"
        print_error "Make sure the internal/store directory exists with alembic.ini"
        exit 1
    fi

    if [ ! -f "$ALEMBIC_DIR/alembic.ini" ]; then
        print_error "alembic.ini not found at: $ALEMBIC_DIR/alembic.ini"
        print_error "Make sure alembic is properly initialized"
        exit 1
    fi
}

# Function to setup Python environment
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
            print_warning "Make sure alembic is installed in your current environment"
        fi
    else
        print_status "Using existing virtual environment: $VIRTUAL_ENV"
    fi
}

# Function to run alembic commands
run_alembic() {
    check_alembic_setup
    setup_python_environment
    # Stay in project root but specify config file location
    # cd "$ALEMBIC_DIR"

    if ! command -v alembic &> /dev/null; then
        print_error "Alembic is not installed. Please install it with: pipenv install alembic"
        exit 1
    fi

    print_status "Checking database status..."
    echo
    echo "=== Database Connectivity ==="
    if ! check_database_connectivity; then
        print_error "Database connectivity failed. Please check your configuration."
        return 1
    fi

    print_status "Running: alembic -c $ALEMBIC_DIR/alembic.ini $* (from $(pwd))"
    alembic -c "$ALEMBIC_DIR/alembic.ini" "$@"
}

# Create a new migration
create_migration() {
    local message="$1"
    if [ -z "$message" ]; then
        print_error "Migration message is required"
        exit 1
    fi

    print_status "Creating migration: $message"
    run_alembic revision --autogenerate -m "$message"
}

# Upgrade database
upgrade_database() {
    local revision="${1:-head}"
    print_status "Upgrading database to: $revision"
    run_alembic upgrade "$revision"
}

# Downgrade database
downgrade_database() {
    local revision="$1"
    if [ -z "$revision" ]; then
        print_error "Target revision is required for downgrade"
        exit 1
    fi

    print_warning "Downgrading database to: $revision"
    read -p "Are you sure you want to downgrade the database? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        run_alembic downgrade "$revision"
    else
        print_status "Downgrade cancelled"
    fi
}

# Show current revision
show_current_revision() {
    print_status "Current database revision:"
    run_alembic current
}

# Show migration history
show_migration_history() {
    print_status "Migration history:"
    run_alembic history
}

# Show migration info
show_migration_info() {
    print_status "Migration information:"
    run_alembic show head
}

# Stamp database
stamp_database() {
    local revision="$1"
    if [ -z "$revision" ]; then
        print_error "Revision is required for stamp"
        exit 1
    fi

    print_warning "Stamping database with revision: $revision"
    read -p "Are you sure you want to stamp the database? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        run_alembic stamp "$revision"
    else
        print_status "Stamp cancelled"
    fi
}

# Reset database
reset_database() {
    print_warning "This will reset the database to initial state (all data will be lost)"
    read -p "Are you sure you want to reset the database? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Resetting database..."
        run_alembic downgrade base
        print_status "Database reset successfully"
    else
        print_status "Reset cancelled"
    fi
}

# Initialize database
init_database() {
    print_status "Initializing database with all migrations..."
    upgrade_database "head"
}

# Check database status
check_database() {

    echo
    echo "=== Current Revision ==="
    run_alembic current
    echo
    echo "=== Pending Migrations ==="
    if run_alembic heads > /dev/null 2>&1; then
        local current=$(run_alembic current --verbose 2>/dev/null | grep "Rev" | awk '{print $2}' || echo "")
        local head=$(run_alembic heads --verbose 2>/dev/null | grep "Rev" | awk '{print $2}' || echo "")

        if [ "$current" = "$head" ]; then
            print_status "Database is up to date"
        else
            print_warning "Database has pending migrations"
            echo "Current: $current"
            echo "Latest: $head"
        fi
    else
        print_warning "Could not determine migration status"
    fi
}

# Check only database connectivity
check_database_only() {
    setup_python_environment
    check_database_connectivity
}

# Show help
show_help() {
    cat << EOF
Database Migration Utility for the assistant

USAGE:
    $0 <command> [options]

COMMANDS:
    create <message>     Create a new migration with autogenerate
    upgrade [revision]   Upgrade database to revision (default: head)
    downgrade <revision> Downgrade database to revision
    current             Show current database revision
    history             Show migration history
    info                Show migration information
    stamp <revision>    Stamp database with revision (without running migrations)
    reset               Reset database to initial state (WARNING: destructive)
    init                Initialize database with all migrations
    check               Check database migration status and connectivity
    db-check            Check database connectivity only
    help                Show this help message

EXAMPLES:
    $0 create "Add user table"
    $0 upgrade
    $0 upgrade abc123
    $0 downgrade abc123
    $0 current
    $0 history
    $0 check
    $0 db-check

NOTE:
    This script looks for alembic configuration in: internal/store/
    Ensure your .env file is properly configured with database settings.
    Migration files are stored in: internal/store/migrations/versions/
    Virtual environment will be activated automatically if found at: .venv/
EOF
}

# Main function
main() {
    local command="$1"
    shift || true

    case "$command" in
        "create")
            create_migration "$1"
            ;;
        "upgrade")
            upgrade_database "$1"
            ;;
        "downgrade")
            downgrade_database "$1"
            ;;
        "current")
            show_current_revision
            ;;
        "history")
            show_migration_history
            ;;
        "info")
            show_migration_info
            ;;
        "stamp")
            stamp_database "$1"
            ;;
        "reset")
            reset_database
            ;;
        "init")
            init_database
            ;;
        "check")
            check_database
            ;;
        "db-check")
            check_database_only
            ;;
        "help"|"-h"|"--help"|"")
            show_help
            ;;
        *)
            print_error "Unknown command: $command"
            echo
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
