#!/usr/bin/env bash
# Coder autostart hook (docker-basic template): serve the browser generator in
# site/ on the workspace's published dev port. The template already provides
# the virtual display (DISPLAY=:99) for the Python render scripts.
set -eu
cd "$(dirname "$0")/.."
exec python3 -m http.server "${WORKSPACE_DEV_PORT:-8000}" --directory site
