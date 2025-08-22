#!/usr/bin/env bash
# Stop the Django server started by run_server.sh (using uv)


GREEN='\033[1;32m'
RED='\033[1;31m'
NC='\033[0m'

LOGDIR="logs"
LOGFILE="$LOGDIR/server.log"

# Create logs directory if it doesn't exist
if [ ! -d "$LOGDIR" ]; then
    mkdir -p "$LOGDIR"
fi

# Find the PID of the running uv server from the log or by process name
PID=$(ps aux | grep 'uv run manage.py runserver' | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
    echo -e "${RED}No running uv Django server process found.${NC}"
    exit 1
else
    kill "$PID"
    sleep 1
    if ps -p $PID > /dev/null; then
        echo -e "${RED}Failed to stop server process with PID $PID.${NC}"
        exit 1
    else
        echo -e "${GREEN}Stopped Django server process with PID $PID.${NC}"
        echo -e "${GREEN}See logs on $LOGFILE${NC}"
        exit 0
    fi
fi
