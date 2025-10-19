#!/bin/sh
set -e

# Copy SSL certificates to PostgreSQL data directory with correct permissions
mkdir -p /var/lib/postgresql/ssl
cp /tmp/ssl/server-cert.pem /var/lib/postgresql/ssl/
cp /tmp/ssl/server-key.pem /var/lib/postgresql/ssl/
cp /tmp/ssl/ca-cert.pem /var/lib/postgresql/ssl/
chown postgres:postgres /var/lib/postgresql/ssl/*
chmod 600 /var/lib/postgresql/ssl/server-key.pem
chmod 644 /var/lib/postgresql/ssl/server-cert.pem
chmod 644 /var/lib/postgresql/ssl/ca-cert.pem

# Execute the original Docker entrypoint with SSL configuration
exec docker-entrypoint.sh postgres \
  -c ssl=on \
  -c ssl_cert_file=/var/lib/postgresql/ssl/server-cert.pem \
  -c ssl_key_file=/var/lib/postgresql/ssl/server-key.pem \
  -c ssl_ca_file=/var/lib/postgresql/ssl/ca-cert.pem \
  -c ssl_min_protocol_version=TLSv1.2 \
  -c ssl_prefer_server_ciphers=on \
  -c ssl_ciphers='HIGH:!aNULL:!MD5'
