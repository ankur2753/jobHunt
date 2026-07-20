#!/bin/bash
# Native Cron wrapper script for Automated Job Search Agent

PROJECT_DIR="/home/ankurkumar/ankur_code/agent"
cd "$PROJECT_DIR" || { echo "Could not cd to $PROJECT_DIR"; exit 1; }

# Enable X11 display access for headed browser automation inside cron
export DISPLAY=:0
export XAUTHORITY=/home/ankurkumar/.Xauthority

# Activate python virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "Virtual environment .venv/bin/activate not found"
    exit 1
fi

# Run the non-interactive python script and log output
mkdir -p logs
python scripts/cron_naukri_apply.py >> logs/cron_naukri_apply_cron.log 2>&1
