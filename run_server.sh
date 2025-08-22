#!/usr/bin/env bash
# Run Django server using uv, reading host and port from .env, and keep it running in background

set -a
. ./.env
set +a


GREEN='\033[1;32m'
RED='\033[1;31m'
NC='\033[0m'

LOGDIR="logs"
LOGFILE="$LOGDIR/server.log"

# Create logs directory if it doesn't exist
if [ ! -d "$LOGDIR" ]; then
	mkdir -p "$LOGDIR"
fi

# Start the server in the background, detached from terminal
nohup uv run manage.py runserver "$SERVER_HOST:$SERVER_PORT" > "$LOGFILE" 2>&1 &

PID=$!
sleep 2
if ps -p $PID > /dev/null; then
	echo -e "${GREEN}Server started at http://$SERVER_HOST:$SERVER_PORT${NC}"
	echo -e "${GREEN}See logs on $LOGFILE${NC}"
	echo -e "${GREEN}Server PID: $PID${NC}"
else
	echo -e "${RED}Failed to start server. Check $LOGFILE for details.${NC}"
	exit 1
fi
