#!/bin/bash

# Database Backup Cron Setup Script
# This script sets up automated database backups using cron

set -e  # Exit on any error

PROJECT_ROOT="/home/mithun/PROJECT/student-attendance-django"
SCRIPT_DIR="$PROJECT_ROOT"
BACKUP_MANAGER="$SCRIPT_DIR/backup_manager.py"
LOG_DIR="$PROJECT_ROOT/logs"
BACKUP_CONFIG="$PROJECT_ROOT/backup_config.env"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Setting up MySQL Database Backup System${NC}"
echo "=================================================="

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"
echo -e "${GREEN}✅ Created logs directory: $LOG_DIR${NC}"

# Make backup manager executable
chmod +x "$BACKUP_MANAGER"
echo -e "${GREEN}✅ Made backup manager executable${NC}"

# Load backup configuration
if [ -f "$BACKUP_CONFIG" ]; then
    source "$BACKUP_CONFIG"
    echo -e "${GREEN}✅ Loaded backup configuration${NC}"
else
    echo -e "${YELLOW}⚠️  Backup config file not found, using defaults${NC}"
    BACKUP_SCHEDULE="0 2 * * *"  # Default: 2 AM daily
fi

# Get current user
CURRENT_USER=$(whoami)
echo -e "${BLUE}👤 Setting up cron job for user: $CURRENT_USER${NC}"

# Create cron job entry
CRON_JOB="$BACKUP_SCHEDULE cd $PROJECT_ROOT && /usr/bin/python3 $BACKUP_MANAGER run >> $LOG_DIR/backup_cron.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "backup_manager.py"; then
    echo -e "${YELLOW}⚠️  Backup cron job already exists. Removing old entry...${NC}"
    # Remove existing backup cron jobs
    (crontab -l 2>/dev/null | grep -v "backup_manager.py") | crontab -
fi

# Add new cron job
echo -e "${BLUE}📅 Adding cron job with schedule: $BACKUP_SCHEDULE${NC}"
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo -e "${GREEN}✅ Cron job added successfully!${NC}"

# Install required Python packages if not already installed
echo -e "${BLUE}📦 Checking Python dependencies...${NC}"

# Check if we have a virtual environment
if [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON_CMD="$PROJECT_ROOT/.venv/bin/python"
    PIP_CMD="$PROJECT_ROOT/.venv/bin/pip"
    echo -e "${GREEN}✅ Using virtual environment${NC}"
else
    PYTHON_CMD="python3"
    PIP_CMD="pip3"
    echo -e "${YELLOW}⚠️  No virtual environment found, using system Python${NC}"
fi

# Install mysql-connector-python if not installed
if ! $PYTHON_CMD -c "import mysql.connector" 2>/dev/null; then
    echo -e "${BLUE}📦 Installing mysql-connector-python...${NC}"
    $PIP_CMD install mysql-connector-python
    echo -e "${GREEN}✅ mysql-connector-python installed${NC}"
else
    echo -e "${GREEN}✅ mysql-connector-python already installed${NC}"
fi

# Run initial health check
echo -e "${BLUE}🔍 Running initial health check...${NC}"
if $PYTHON_CMD "$BACKUP_MANAGER" health; then
    echo -e "${GREEN}✅ Health check passed${NC}"
else
    echo -e "${YELLOW}⚠️  Health check had warnings, but setup continues${NC}"
fi

# Display current cron jobs
echo -e "${BLUE}📋 Current cron jobs for $CURRENT_USER:${NC}"
crontab -l | grep -E "(backup|#)" || echo "No backup-related cron jobs found"

echo ""
echo -e "${GREEN}🎉 Database backup system setup complete!${NC}"
echo ""
echo -e "${BLUE}📖 Usage Instructions:${NC}"
echo "  • Automatic backups will run according to schedule: $BACKUP_SCHEDULE"
echo "  • Manual backup: python3 $BACKUP_MANAGER run"
echo "  • Health check: python3 $BACKUP_MANAGER health"
echo "  • View logs: tail -f $LOG_DIR/backup.log"
echo "  • View cron logs: tail -f $LOG_DIR/backup_cron.log"
echo ""
echo -e "${BLUE}⚙️  Configuration:${NC}"
echo "  • Config file: $BACKUP_CONFIG"
echo "  • Edit the config file to change backup schedule or other settings"
echo "  • After editing config, run: $0 to update cron job"
echo ""
echo -e "${YELLOW}💡 Tips:${NC}"
echo "  • The backup database will be created automatically on first run"
echo "  • Backup schedule format: 'minute hour day month dayofweek'"
echo "  • Examples:"
echo "    - '0 2 * * *'   = Daily at 2:00 AM"
echo "    - '0 3 * * 0'   = Weekly on Sunday at 3:00 AM"
echo "    - '0 1 1 * *'   = Monthly on 1st day at 1:00 AM"
echo ""

# Test run option
read -p "Would you like to run a test backup now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}🧪 Running test backup...${NC}"
    if $PYTHON_CMD "$BACKUP_MANAGER" run; then
        echo -e "${GREEN}🎉 Test backup completed successfully!${NC}"
    else
        echo -e "${RED}❌ Test backup failed. Check the logs for details.${NC}"
    fi
fi

echo -e "${GREEN}✅ Setup complete!${NC}"
