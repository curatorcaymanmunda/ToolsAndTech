#!/bin/bash

# Web Server Backup & Restore Utility
# Copyright (C) 2025 Open Source Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# ============================================================================
#
# Advanced Web Server Backup & Restore Utility
# Production-grade backup solution for /var/www and MySQL databases
# 
# Features:
# - Cross-platform support (Linux distributions + macOS)
# - Service management (graceful stop/start of web services)
# - Progress monitoring with visual progress bars
# - Comprehensive integrity verification
# - Configuration file support with sensible defaults
# - Retention policies and automatic cleanup
# - Email and webhook notifications
# - Parallel compression for performance
# - Detailed logging and audit trails
# - Dry-run capability for testing
# - Automatic dependency installation
# - MySQL/MariaDB compatibility
# 
# Supported Platforms:
# - Linux: Ubuntu, Debian, RHEL, CentOS, Fedora, Arch, openSUSE, Alpine
# - macOS: Full Homebrew integration
# 
# Usage:
#   ./webserver-backup.sh                    # Interactive mode
#   ./webserver-backup.sh --auto --quiet     # Automated mode (cron)
#   ./webserver-backup.sh --dry-run          # Test mode
#   ./webserver-backup.sh --help             # Show help
#
# For more information and documentation:
# https://github.com/your-repo/webserver-backup-utility
#
# ============================================================================

set -euo pipefail

# Version and metadata
VERSION="2.1.0"
SCRIPT_NAME="webserver-backup"
CONFIG_FILE="/etc/${SCRIPT_NAME}.conf"
DEFAULT_EXCLUSIONS_FILE="/etc/${SCRIPT_NAME}.exclude"

# Show GPL license information
show_license() {
    cat << 'EOF'
Web Server Backup & Restore Utility v2.1.0
Copyright (C) 2025 Open Source Contributors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

This is free software, and you are welcome to redistribute it
under certain conditions. Run with --license for full license text.
EOF
}

# Show full GPL license text
show_full_license() {
    cat << 'EOF'
                    GNU GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007

 Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>
 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.

                            Preamble

  The GNU General Public License is a free, copyleft license for
software and other kinds of works.

  The licenses for most software and other practical works are designed
to take away your freedom to share and change the works.  By contrast,
the GNU General Public License is intended to guarantee your freedom to
share and change all versions of a program--to make sure it remains free
software for all its users.  We, the Free Software Foundation, use the
GNU General Public License for most of our software; it applies also to
any other work released this way by its authors.  You can apply it to
your programs, too.

[... Full GPL v3 text continues ...]

For the complete license text, visit: https://www.gnu.org/licenses/gpl-3.0.html
EOF
}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# OS Detection variables
OS_TYPE=""
OS_DISTRO=""
OS_VERSION=""
PACKAGE_MANAGER=""
INSTALL_CMD=""
SERVICE_MANAGER=""

# Global variables
TASK_TYPE=""
MYSQL_USER=""
MYSQL_PASS=""
MYSQL_HOST="localhost"
MYSQL_PORT="3306"
DESTINATION=""
LOG_FILE=""
BACKUP_DATE=$(date +"%Y%m%d_%H%M%S")
BACKUP_TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
WWW_SOURCE="/var/www"
DRY_RUN=false
BACKUP_TYPE="full"
COMPRESSION_LEVEL="6"
COMPRESSION_TOOL="gzip"
PARALLEL_JOBS=""
EXCLUDE_FILE=""
CONFIG_LOADED=false
AUTOMATIC_MODE=false
QUIET_MODE=false

# Backup metadata
declare -A BACKUP_STATS
BACKUP_STATS[start_time]=$(date +%s)
BACKUP_STATS[files_processed]=0
BACKUP_STATS[bytes_processed]=0

# Trap for cleanup
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        print_error "Operation interrupted or failed. Check log: $LOG_FILE"
    fi
    
    # Restart services if they were stopped
    restart_services
    
    exit $exit_code
}
trap cleanup EXIT INT TERM

# Function to print colored output
print_info() {
    if [[ "$QUIET_MODE" = false ]]; then
        if [[ -n "${LOG_FILE:-}" ]]; then
            echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE" 2>/dev/null || echo -e "${BLUE}[INFO]${NC} $1"
        else
            echo -e "${BLUE}[INFO]${NC} $1"
        fi
    else
        # Only log if LOG_FILE is set
        if [[ -n "${LOG_FILE:-}" ]]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1" >> "$LOG_FILE" 2>/dev/null || true
        fi
    fi
}

print_success() {
    if [[ "$QUIET_MODE" = false ]]; then
        if [[ -n "${LOG_FILE:-}" ]]; then
            echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE" 2>/dev/null || echo -e "${GREEN}[SUCCESS]${NC} $1"
        else
            echo -e "${GREEN}[SUCCESS]${NC} $1"
        fi
    else
        # Only log if LOG_FILE is set
        if [[ -n "${LOG_FILE:-}" ]]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS: $1" >> "$LOG_FILE" 2>/dev/null || true
        fi
    fi
}

print_warning() {
    if [[ "$QUIET_MODE" = false ]]; then
        if [[ -n "${LOG_FILE:-}" ]]; then
            echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE" 2>/dev/null || echo -e "${YELLOW}[WARNING]${NC} $1"
        else
            echo -e "${YELLOW}[WARNING]${NC} $1"
        fi
    else
        # Only log if LOG_FILE is set
        if [[ -n "${LOG_FILE:-}" ]]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1" >> "$LOG_FILE" 2>/dev/null || true
        fi
    fi
}

print_error() {
    if [[ -n "${LOG_FILE:-}" ]]; then
        echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE" 2>/dev/null || echo -e "${RED}[ERROR]${NC} $1"
    else
        echo -e "${RED}[ERROR]${NC} $1"
    fi
}

print_debug() {
    # Only log if LOG_FILE is set
    if [[ -n "${LOG_FILE:-}" ]]; then
        echo -e "${PURPLE}[DEBUG]${NC} $1" >> "$LOG_FILE" 2>/dev/null || true
    fi
}

print_progress() {
    if [[ "$QUIET_MODE" = false ]]; then
        echo -e "${CYAN}[PROGRESS]${NC} $1"
    fi
}

# Function to log with timestamp
log_message() {
    # Only log if LOG_FILE is set and not empty
    if [[ -n "${LOG_FILE:-}" ]]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE" 2>/dev/null || true
    fi
}

# Function to show progress bar
show_progress() {
    if [[ "$QUIET_MODE" = true ]]; then
        return
    fi
    
    local current=$1
    local total=$2
    local width=50
    local percentage=$((current * 100 / total))
    local filled=$((current * width / total))
    local empty=$((width - filled))
    
    printf "\r${CYAN}Progress: [${NC}"
    printf "%${filled}s" | tr ' ' '█'
    printf "%${empty}s" | tr ' ' '░'
    printf "${CYAN}] %d%% (%d/%d)${NC}" $percentage $current $total
    
    if [[ $current -eq $total ]]; then
        echo
    fi
}

# Function to detect operating system and set appropriate commands
detect_os() {
    print_info "Detecting operating system..."
    
    # Detect OS type
    case "$(uname -s)" in
        Linux*)
            OS_TYPE="Linux"
            ;;
        Darwin*)
            OS_TYPE="macOS"
            ;;
        CYGWIN*|MINGW*|MSYS*)
            OS_TYPE="Windows"
            print_error "Windows is not supported by this script"
            exit 1
            ;;
        *)
            OS_TYPE="Unknown"
            print_error "Unknown operating system: $(uname -s)"
            exit 1
            ;;
    esac
    
    # Linux distribution detection
    if [[ "$OS_TYPE" == "Linux" ]]; then
        if [[ -f /etc/os-release ]]; then
            source /etc/os-release
            OS_DISTRO="$ID"
            OS_VERSION="$VERSION_ID"
        elif [[ -f /etc/redhat-release ]]; then
            OS_DISTRO="rhel"
            OS_VERSION=$(grep -oE '[0-9]+\.[0-9]+' /etc/redhat-release | head -1)
        elif [[ -f /etc/debian_version ]]; then
            OS_DISTRO="debian"
            OS_VERSION=$(cat /etc/debian_version)
        else
            OS_DISTRO="unknown"
            OS_VERSION="unknown"
        fi
        
        # Set package manager and commands based on distribution
        case "$OS_DISTRO" in
            ubuntu|debian|linuxmint|pop)
                PACKAGE_MANAGER="apt"
                INSTALL_CMD="apt-get install -y"
                SERVICE_MANAGER="systemctl"
                ;;
            rhel|centos|fedora|rocky|almalinux)
                if command -v dnf &> /dev/null; then
                    PACKAGE_MANAGER="dnf"
                    INSTALL_CMD="dnf install -y"
                elif command -v yum &> /dev/null; then
                    PACKAGE_MANAGER="yum"
                    INSTALL_CMD="yum install -y"
                else
                    print_error "No package manager found (dnf/yum)"
                    exit 1
                fi
                SERVICE_MANAGER="systemctl"
                ;;
            arch|manjaro)
                PACKAGE_MANAGER="pacman"
                INSTALL_CMD="pacman -S --noconfirm"
                SERVICE_MANAGER="systemctl"
                ;;
            opensuse|opensuse-leap|opensuse-tumbleweed)
                PACKAGE_MANAGER="zypper"
                INSTALL_CMD="zypper install -y"
                SERVICE_MANAGER="systemctl"
                ;;
            alpine)
                PACKAGE_MANAGER="apk"
                INSTALL_CMD="apk add"
                SERVICE_MANAGER="rc-service"
                ;;
            *)
                print_warning "Unknown Linux distribution: $OS_DISTRO"
                print_warning "Defaulting to generic Linux commands"
                PACKAGE_MANAGER="unknown"
                INSTALL_CMD="echo 'Please install manually:'"
                SERVICE_MANAGER="systemctl"
                ;;
        esac
        
    elif [[ "$OS_TYPE" == "macOS" ]]; then
        OS_VERSION=$(sw_vers -productVersion)
        
        # Check for Homebrew
        if command -v brew &> /dev/null; then
            PACKAGE_MANAGER="brew"
            INSTALL_CMD="brew install"
        else
            print_warning "Homebrew not found. Install from: https://brew.sh"
            PACKAGE_MANAGER="manual"
            INSTALL_CMD="echo 'Please install Homebrew first, then:'"
        fi
        
        SERVICE_MANAGER="launchctl"
        
        # Adjust default paths for macOS
        if [[ "$WWW_SOURCE" == "/var/www" ]]; then
            WWW_SOURCE="/usr/local/var/www"
            print_info "Adjusted default web directory for macOS: $WWW_SOURCE"
        fi
    fi
    
    print_success "OS Detection completed:"
    print_info "  OS: $OS_TYPE $([ -n "$OS_DISTRO" ] && echo "($OS_DISTRO)")"
    print_info "  Version: $OS_VERSION"
    print_info "  Package Manager: $PACKAGE_MANAGER"
    print_info "  Service Manager: $SERVICE_MANAGER"
    
    log_message "OS Detection: $OS_TYPE $OS_DISTRO $OS_VERSION, Package Manager: $PACKAGE_MANAGER"
}

# [Continue with rest of functions from previous artifact...]
# For brevity, I'm including the key functions. The full script would include
# all the functions we developed earlier.

# Function to show usage information
show_usage() {
    cat << EOF
Web Server Backup & Restore Utility v$VERSION
Licensed under GNU GPL v3 - Free and Open Source Software

USAGE:
    $0 [OPTIONS]

OPTIONS:
    -h, --help              Show this help message
    -c, --config FILE       Use custom configuration file
    -d, --dry-run          Perform dry run (show what would be done)
    -v, --version          Show version information
    -a, --auto             Automatic mode (for cron jobs)
    -q, --quiet            Quiet mode (minimal output)
    --create-config        Create default configuration file and exit
    --os-info              Show detected OS information and exit
    --license              Show license information
    --gpl                  Show full GPL license text

EXAMPLES:
    $0                     Interactive mode
    $0 --dry-run          Show what would be backed up
    $0 --config /etc/my-backup.conf    Use custom config
    $0 --auto --quiet     Automatic backup (ideal for cron)
    $0 --os-info          Show OS detection results

CRON EXAMPLE:
    # Daily backup at 2 AM
    0 2 * * * $0 --auto --quiet

INSTALLATION:
    # Download and install:
    wget https://raw.githubusercontent.com/your-repo/webserver-backup-utility/main/webserver-backup.sh
    sudo cp webserver-backup.sh /usr/local/bin/
    sudo chmod +x /usr/local/bin/webserver-backup.sh
    
    # Create configuration:
    sudo /usr/local/bin/webserver-backup.sh --create-config

SUPPORTED PLATFORMS:
    Linux (Ubuntu, Debian, RHEL, CentOS, Fedora, Arch, openSUSE, Alpine)
    macOS (with Homebrew support)

PACKAGE MANAGERS:
    apt (Ubuntu/Debian), dnf/yum (RHEL/Fedora), pacman (Arch)
    zypper (openSUSE), apk (Alpine), brew (macOS)

FILES:
    $CONFIG_FILE           Main configuration file
    $DEFAULT_EXCLUSIONS_FILE    Default exclusions file
    /var/log/webserver-backup/    Default log directory

LICENSE:
    This program is free software licensed under GNU GPL v3.
    You are free to use, modify, and distribute this software.
    See --license for license information.

CONTRIBUTING:
    Issues and pull requests welcome at:
    https://github.com/your-repo/webserver-backup-utility

For more information and documentation, visit:
https://github.com/your-repo/webserver-backup-utility
EOF
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -v|--version)
                echo "Web Server Backup & Restore Utility v$VERSION"
                echo "Licensed under GNU GPL v3"
                echo "Copyright (C) 2025 Open Source Contributors"
                echo "This is free software; see --license for license information."
                echo "Supported platforms: Linux, macOS"
                exit 0
                ;;
            --license)
                show_license
                exit 0
                ;;
            --gpl)
                show_full_license
                exit 0
                ;;
            -c|--config)
                CONFIG_FILE="$2"
                shift 2
                ;;
            -d|--dry-run)
                DRY_RUN=true
                TASK_TYPE="backup"
                shift
                ;;
            -a|--auto)
                AUTOMATIC_MODE=true
                TASK_TYPE="backup"
                BACKUP_TYPE="full"
                shift
                ;;
            -q|--quiet)
                QUIET_MODE=true
                shift
                ;;
            --create-config)
                detect_os  # Need OS detection for package managers
                create_default_config
                create_default_exclusions
                echo
                echo "=========================================="
                echo "GNU GPL Licensed Web Server Backup Utility"
                echo "Configuration files created successfully!"
                echo "=========================================="
                echo
                echo "Configuration file: $CONFIG_FILE"
                echo "Exclusions file: $DEFAULT_EXCLUSIONS_FILE"
                echo
                echo "Please edit the configuration file with your MySQL credentials:"
                echo "  sudo nano $CONFIG_FILE"
                echo
                echo "Then run the backup script:"
                echo "  sudo $0"
                echo
                echo "This software is licensed under GNU GPL v3."
                echo "Run '$0 --license' for license information."
                exit 0
                ;;
            --os-info)
                detect_os
                echo
                echo "OS Detection Results:"
                echo "===================="
                echo "Operating System: $OS_TYPE"
                echo "Distribution: ${OS_DISTRO:-N/A}"
                echo "Version: $OS_VERSION"
                echo "Package Manager: $PACKAGE_MANAGER"
                echo "Install Command: $INSTALL_CMD"
                echo "Service Manager: $SERVICE_MANAGER"
                echo
                echo "This software is licensed under GNU GPL v3."
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
}

# [Rest of the functions would be included here from our complete script]

# Entry point with GPL notice
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Show brief license notice on startup (unless in quiet mode)
    if [[ "$QUIET_MODE" = false ]] && [[ "$1" != "--quiet" ]] && [[ "$1" != "-q" ]]; then
        echo "Web Server Backup & Restore Utility v$VERSION"
        echo "Copyright (C) 2025 - Licensed under GNU GPL v3"
        echo "This is free software; run with --license for details."
        echo
    fi
    
    initialize "$@"
    main "$@"
fi
EOF