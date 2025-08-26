#!/usr/bin/env bash
# generate_ssl.sh: Generate self-signed SSL certificate and key for local HTTPS

set -e

CERT_DIR="ssl"
KEY_FILE="$CERT_DIR/server.key"
CERT_FILE="$CERT_DIR/server.crt"
PEM_FILE="$CERT_DIR/server.pem"

mkdir -p "$CERT_DIR"

# Generate private key
echo "Generating private key..."
openssl genrsa -out "$KEY_FILE" 2048

# Generate certificate signing request (CSR)
echo "Generating certificate signing request..."
openssl req -new -key "$KEY_FILE" -out "$CERT_DIR/server.csr" -subj "/C=IN/ST=State/L=City/O=Organization/OU=OrgUnit/CN=localhost"

# Generate self-signed certificate
echo "Generating self-signed certificate..."
openssl x509 -req -days 365 -in "$CERT_DIR/server.csr" -signkey "$KEY_FILE" -out "$CERT_FILE"

# Combine key and cert to PEM (for some servers)
cat "$KEY_FILE" "$CERT_FILE" > "$PEM_FILE"

# Clean up CSR
echo "Cleaning up..."
rm "$CERT_DIR/server.csr"

echo "SSL certificate and key generated in $CERT_DIR/"
echo "Key: $KEY_FILE"
echo "Cert: $CERT_FILE"
echo "PEM: $PEM_FILE"
