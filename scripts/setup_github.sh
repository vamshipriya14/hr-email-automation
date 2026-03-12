#!/bin/bash
# Setup GitHub repository and push code

set -e

REPO_NAME="hr-email-automation"
GITHUB_TOKEN="$1"

if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ Error: GitHub token required"
    echo "Usage: ./setup_github.sh YOUR_GITHUB_TOKEN"
    exit 1
fi

echo "🚀 Setting up GitHub repository: $REPO_NAME"
echo "=================================================="

# Navigate to repo directory
cd "$(dirname "$0")/.."

# Initialize git if not already
if [ ! -d ".git" ]; then
    echo "📁 Initializing git repository..."
    git init
    git add .
    git commit -m "Initial commit: HR Email Automation System

- Email parser with multi-candidate support
- IMAP monitoring for automatic processing
- Duplicate detection (marks, always inserts)
- Both vertical and horizontal table formats
- Background service support
- Complete documentation

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
else
    echo "✅ Git repository already initialized"
fi

# Create GitHub repo using API
echo ""
echo "📦 Creating GitHub repository..."

RESPONSE=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    https://api.github.com/user/repos \
    -d "{\"name\":\"$REPO_NAME\",\"description\":\"Automated HR candidate email processing system\",\"private\":false}")

# Check if repo was created or already exists
if echo "$RESPONSE" | grep -q "\"name\": \"$REPO_NAME\""; then
    echo "✅ GitHub repository created successfully"
elif echo "$RESPONSE" | grep -q "name already exists"; then
    echo "✅ GitHub repository already exists"
else
    echo "⚠️  Response: $RESPONSE"
fi

# Get GitHub username
USERNAME=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    https://api.github.com/user | grep -o '"login": *"[^"]*"' | cut -d'"' -f4)

if [ -z "$USERNAME" ]; then
    echo "❌ Could not determine GitHub username"
    exit 1
fi

echo "👤 GitHub username: $USERNAME"

# Set remote
REMOTE_URL="https://${GITHUB_TOKEN}@github.com/${USERNAME}/${REPO_NAME}.git"

if git remote | grep -q "origin"; then
    echo "🔄 Updating remote origin..."
    git remote set-url origin "$REMOTE_URL"
else
    echo "➕ Adding remote origin..."
    git remote add origin "$REMOTE_URL"
fi

# Push to GitHub
echo ""
echo "📤 Pushing to GitHub..."
git branch -M main
git push -u origin main

echo ""
echo "=================================================="
echo "✅ SUCCESS!"
echo "=================================================="
echo ""
echo "🎉 Repository created and pushed to GitHub!"
echo ""
echo "📍 Repository URL:"
echo "   https://github.com/${USERNAME}/${REPO_NAME}"
echo ""
echo "🔗 Clone URL:"
echo "   https://github.com/${USERNAME}/${REPO_NAME}.git"
echo ""
echo "=================================================="
