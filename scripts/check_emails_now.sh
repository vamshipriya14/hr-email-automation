#!/bin/bash
# Check for new emails once and exit

cd "$(dirname "$0")/.."

echo "📬 Checking for new candidate emails..."
echo ""

python3 src/email_monitor.py --once

echo ""
echo "✅ Check complete!"
