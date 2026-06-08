#!/bin/bash
set -e

PROJECT_DIR="/Users/jacobfeinberg/feinbermetrics"
VENV_DIR="$PROJECT_DIR/venv"
LOG_FILE="/tmp/feinbermetrics-refresh.log"
MINIMUM_ROW_COUNT=100

echo "$(date): Starting schedule refresh" | tee -a "$LOG_FILE"

cd "$PROJECT_DIR"

if [ ! -d "$VENV_DIR" ]; then
    echo "$(date): Creating virtual environment" | tee -a "$LOG_FILE"
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install curl_cffi pandas >> "$LOG_FILE" 2>&1
else
    source "$VENV_DIR/bin/activate"
fi

python3 fetch_schedules.py 2>&1 | tee -a "$LOG_FILE"
python3 export_csv.py 2>&1 | tee -a "$LOG_FILE"

ROWS=$(tail -n +2 schedules.csv | wc -l | tr -d ' ')
if [ "$ROWS" -lt "$MINIMUM_ROW_COUNT" ]; then
    echo "$(date): ERROR — only $ROWS rows fetched, aborting to protect existing data" | tee -a "$LOG_FILE"
    exit 1
fi

git pull --rebase >> "$LOG_FILE" 2>&1
git add schedules.csv pitcher_fip.csv
git diff --staged --quiet || git commit -m "Refresh schedule data $(date +%Y-%m-%d)" >> "$LOG_FILE" 2>&1
git push origin main >> "$LOG_FILE" 2>&1

echo "$(date): Refresh complete — $ROWS rows pushed" | tee -a "$LOG_FILE"
