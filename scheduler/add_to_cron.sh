(crontab -l 2>/dev/null; echo "0 23 * * * python scheduler.py") | crontab -

