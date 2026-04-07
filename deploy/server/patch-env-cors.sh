#!/usr/bin/env bash
set -euo pipefail
cd ~/CRM
line='CORS_ORIGINS=["http://192.168.9.17","http://localhost:3500"]'
grep -v '^CORS_ORIGINS=' .env > .env.tmp
echo "$line" >> .env.tmp
mv .env.tmp .env
grep '^CORS_ORIGINS=' .env
