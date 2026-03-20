#!/bin/bash
# Setup cron jobs for Fortune 1000 dataset refresh
# Monthly: company list + profiles (1st of each month at 2 AM)
# Bi-daily: news + events (every 2 days at 3 AM)

PROJECT_DIR="/Users/sriram/Desktop/AI Projects/Fortune"
PYTHON="$PROJECT_DIR/venv/bin/python"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"

# Remove existing Fortune cron entries
crontab -l 2>/dev/null | grep -v "Fortune.*main.py" | crontab -

# Add new entries
(crontab -l 2>/dev/null
echo "# Fortune 1000 Dataset - Monthly refresh (1st of month, 2 AM)"
echo "0 2 1 * * cd \"$PROJECT_DIR\" && $PYTHON main.py monthly >> \"$LOG_DIR/monthly.log\" 2>&1"
echo "# Fortune 1000 Dataset - Bi-daily refresh (every 2 days, 3 AM)"
echo "0 3 */2 * * cd \"$PROJECT_DIR\" && $PYTHON main.py biweekly >> \"$LOG_DIR/biweekly.log\" 2>&1"
) | crontab -

echo "Cron jobs installed. Current crontab:"
crontab -l
