#!/bin/bash
# Load environment variables from .env file

ENV_FILE="$(dirname "$0")/../.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: .env file not found"
    echo ""
    echo "Please create .env file:"
    echo "  cp .env.example .env"
    echo "  # Then edit .env with your credentials"
    exit 1
fi

# Export all variables from .env
set -a
source "$ENV_FILE"
set +a

echo "✅ Environment variables loaded from .env"
