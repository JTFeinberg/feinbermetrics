#!/bin/bash
set -e

PROJECT_DIR="/Users/jacobfeinberg/feinbermetrics"
LOG_FILE="/tmp/feinbermetrics-refresh.log"

echo "$(date): Starting schedule refresh" >> "$LOG_FILE"

cd "$PROJECT_DIR"
source .venv/bin/activate

python fetch_schedules.py >> "$LOG_FILE" 2>&1
python export_csv.py >> "$LOG_FILE" 2>&1

git add schedules.csv
git commit -m "Refresh schedule data $(date +%Y-%m-%d)" >> "$LOG_FILE" 2>&1
git push origin main >> "$LOG_FILE" 2>&1

echo "$(date): Refresh complete" >> "$LOG_FILE"
