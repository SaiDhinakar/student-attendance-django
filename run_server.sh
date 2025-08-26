sleep 2
#!/usr/bin/env bash
# run_server.sh: Start Django app with pm2, generate SSL if needed, and use .env

set -e

GREEN='\033[1;32m'
RED='\033[1;31m'
NC='\033[0m'

# Load environment variables from .env
if [ -f .env ]; then
	set -a
	. ./.env
	set +a
fi

# Generate SSL certs if not present
if [ ! -f ssl/server.key ] || [ ! -f ssl/server.crt ]; then
	echo -e "${GREEN}Generating SSL certificates...${NC}"
	bash generate_ssl.sh
fi

# Generate SSL and then start app with pm2

echo -e "${GREEN}Stopping any existing pm2 instance for student-attendance-django...${NC}"
pm2 delete student-attendance-django 2>/dev/null || true
pm2 save

# Ensure SSL certs exist
if [ ! -f ssl/server.key ] || [ ! -f ssl/server.crt ]; then
	echo -e "${GREEN}Generating SSL certificates...${NC}"
	bash generate_ssl.sh
fi

# Export SSL env vars for Django
export SSL_KEY_PATH="$(pwd)/ssl/server.key"
export SSL_CERT_PATH="$(pwd)/ssl/server.crt"

echo -e "${GREEN}Starting app with pm2 (HTTPS enabled)...${NC}"
pm2 start pm2.config.json --env production --only student-attendance-django --update-env
echo -e "${GREEN}App started with pm2. Use 'pm2 logs' to view logs.${NC}"
