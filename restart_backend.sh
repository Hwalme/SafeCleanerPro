#!/bin/bash
pkill -f "python app.py" || true
sleep 2
cd /opt/safecleaner_backend
nohup python app.py > /var/log/safecleaner.log 2>&1 &
echo "Backend restarted successfully"
