#!/bin/bash
# Start continuous email monitoring

cd "$(dirname "$0")/.."

echo "🚀 Starting Email Monitor"
echo "=================================================="
echo ""
echo "📧 Monitoring for candidate emails with pattern:"
echo "   CODE: Skill Name"
echo ""
echo "   Examples:"
echo "   - BS: SAP Developer"
echo "   - CE: Power BI Lead"
echo "   - XY: Any Skill (works with ANY code!)"
echo ""
echo "⏱️  Checking every 5 minutes (300 seconds)"
echo "🛑 Press Ctrl+C to stop"
echo ""
echo "=================================================="
echo ""

python3 src/email_monitor.py --interval 300
