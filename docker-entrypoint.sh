#!/bin/bash
set -e

# Start Xvfb background daemon for headed Playwright execution
Xvfb :99 -ac -screen 0 1920x1080x24 &
sleep 1

exec "$@"
