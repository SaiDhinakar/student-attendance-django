#!/bin/bash
# test_admin_endpoints.sh - Test the admin management endpoints

# Configuration
BASE_URL="https://localhost:8443"
ADMIN_USER="your_admin_username"
ADMIN_PASS="your_admin_password"

echo "Testing Admin Management Endpoints"
echo "=================================="

# First, login and get session cookie
echo "1. Logging in..."
LOGIN_RESPONSE=$(curl -s -c cookies.txt -b cookies.txt \
  -X POST "${BASE_URL}/auth/login/" \
  -d "username=${ADMIN_USER}&password=${ADMIN_PASS}" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --insecure)

if [[ $? -eq 0 ]]; then
  echo "✓ Login request sent"
else
  echo "✗ Login failed"
  exit 1
fi

# Test status endpoint
echo "2. Checking server status..."
STATUS_RESPONSE=$(curl -s -b cookies.txt \
  -X GET "${BASE_URL}/admin/status/" \
  -H "Accept: application/json" \
  --insecure)

if [[ $? -eq 0 ]]; then
  echo "✓ Status endpoint accessible"
  echo "Response: ${STATUS_RESPONSE}" | jq '.' 2>/dev/null || echo "${STATUS_RESPONSE}"
else
  echo "✗ Status endpoint failed"
fi

# Test update endpoint (uncomment when ready to actually update)
echo "3. Testing update endpoint (dry run)..."
echo "⚠️  Skipping actual update - uncomment below to run real update"

# Uncomment the following lines to actually trigger an update:
# UPDATE_RESPONSE=$(curl -s -b cookies.txt \
#   -X POST "${BASE_URL}/admin/update/" \
#   -H "Accept: application/json" \
#   -H "Content-Type: application/json" \
#   --insecure)
# 
# if [[ $? -eq 0 ]]; then
#   echo "✓ Update endpoint accessible"
#   echo "Response: ${UPDATE_RESPONSE}" | jq '.' 2>/dev/null || echo "${UPDATE_RESPONSE}"
# else
#   echo "✗ Update endpoint failed"
# fi

echo "4. Testing dashboard access..."
DASHBOARD_RESPONSE=$(curl -s -b cookies.txt \
  -X GET "${BASE_URL}/admin/dashboard/" \
  --insecure)

if [[ $? -eq 0 ]] && [[ "${DASHBOARD_RESPONSE}" == *"Server Update Dashboard"* ]]; then
  echo "✓ Dashboard accessible"
else
  echo "✗ Dashboard access failed"
fi

# Cleanup
rm -f cookies.txt

echo ""
echo "Testing completed!"
echo "Dashboard URL: ${BASE_URL}/admin/dashboard/"
