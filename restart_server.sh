#!/usr/bin/env bash
# restart_server.sh: Gracefully restart the Django application

set -e

GREEN='\033[1;32m'
RED='\033[1;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_NAME="student-attendance-django"

echo -e "${YELLOW}Starting graceful server restart...${NC}"

# Check if pm2 process exists
if pm2 list | grep -q "$PROJECT_NAME"; then
    echo -e "${GREEN}Restarting existing pm2 process: $PROJECT_NAME${NC}"
    pm2 restart "$PROJECT_NAME" || {
        echo -e "${RED}Failed to restart pm2 process. Attempting stop/start...${NC}"
        pm2 stop "$PROJECT_NAME" 2>/dev/null || true
        pm2 delete "$PROJECT_NAME" 2>/dev/null || true
        bash ./run_server.sh
    }
else
    echo -e "${YELLOW}No existing pm2 process found. Starting fresh...${NC}"
    bash ./run_server.sh
fi

echo -e "${GREEN}Server restart completed successfully${NC}"
