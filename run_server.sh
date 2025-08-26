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
echo -e "${GREEN}Starting app with pm2...${NC}"
pm2 start pm2.config.json --env production
echo -e "${GREEN}App started with pm2. Use 'pm2 logs' to view logs.${NC}"
