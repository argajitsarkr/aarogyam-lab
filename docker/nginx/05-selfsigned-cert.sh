#!/bin/sh
# Generate a self-signed certificate if the configured one does not exist yet
# (local dev, or first production boot before Let's Encrypt has issued one).
set -e
CERT="${SSL_CERT:-/etc/nginx/certs/selfsigned.crt}"
KEY="${SSL_KEY:-/etc/nginx/certs/selfsigned.key}"
if [ ! -f "$CERT" ] || [ ! -f "$KEY" ]; then
  echo "Creating self-signed certificate for ${SERVER_NAME:-localhost} at $CERT"
  mkdir -p "$(dirname "$CERT")" "$(dirname "$KEY")"
  openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
    -keyout "$KEY" -out "$CERT" \
    -subj "/CN=${SERVER_NAME:-localhost}" \
    -addext "subjectAltName=DNS:${SERVER_NAME:-localhost},DNS:localhost,IP:127.0.0.1" >/dev/null 2>&1
fi
