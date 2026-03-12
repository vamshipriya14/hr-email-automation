#!/bin/bash
# Check for new emails once and exit

cd "$(dirname "$0")/.."

# Load environment variables if .env exists
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

echo "📬 Checking for new candidate emails..."
echo ""

python3 src/email_monitor.py --once

echo ""
echo "✅ Check complete!"
