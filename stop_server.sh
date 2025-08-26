#!/usr/bin/env bash
# stop_server.sh: Stop the pm2 instance for the Django app

GREEN='\033[1;32m'
RED='\033[1;31m'
NC='\033[0m'

echo -e "${GREEN}Stopping pm2 instance for student-attendance-django...${NC}"
pm2 stop student-attendance-django || {
    echo -e "${RED}No running pm2 instance found for student-attendance-django.${NC}"
    exit 1
}

pm2 delete student-attendance-django
echo -e "${GREEN}Stopped and deleted pm2 instance for student-attendance-django.${NC}"
        echo -e "${GREEN}See logs on $LOGFILE${NC}"
        exit 0
    fi
fi
