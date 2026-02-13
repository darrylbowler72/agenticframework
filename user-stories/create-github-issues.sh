#!/bin/bash

# Script to create GitHub issues from user story markdown files
# Prerequisites: GitHub CLI (gh) must be installed and authenticated

set -e

echo "================================================"
echo "Creating GitHub Issues for DevOps Agentic Framework"
echo "================================================"
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ Error: GitHub CLI (gh) is not installed."
    echo "Please install it from: https://cli.github.com/"
    echo ""
    echo "Installation:"
    echo "  macOS: brew install gh"
    echo "  Linux: See https://github.com/cli/cli/blob/trunk/docs/install_linux.md"
    echo "  Windows: winget install --id GitHub.cli"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "❌ Error: Not authenticated with GitHub."
    echo "Please run: gh auth login"
    exit 1
fi

echo "✅ GitHub CLI detected and authenticated"
echo ""

# Function to create an issue
create_issue() {
    local title="$1"
    local body_file="$2"
    local labels="$3"

    echo "Creating issue: $title"

    issue_url=$(gh issue create \
        --title "$title" \
        --body-file "$body_file" \
        --label "$labels" \
        2>&1)

    if [ $? -eq 0 ]; then
        echo "✅ Created: $issue_url"
    else
        echo "❌ Failed to create issue: $title"
        echo "Error: $issue_url"
    fi
    echo ""
}

# Create issues for each user story
echo "Creating issues..."
echo ""

# Issue 1: Scaffolding
create_issue \
    "Implement Backstage Software Template for Microservice Scaffolding" \
    "01-scaffolding-backstage-template.md" \
    "enhancement,scaffolding,backstage,codegen-agent,high-priority"

# Issue 2: Chatbot
create_issue \
    "Implement DevOps Chatbot for Natural Language Agent Interaction" \
    "02-devops-chatbot-interface.md" \
    "enhancement,chatbot,developer-experience,nlp,high-priority"

# Issue 3: Auto-Fix Pipelines
create_issue \
    "Implement Intelligent Auto-Remediation for Broken CI/CD Pipelines" \
    "03-auto-fix-broken-pipelines.md" \
    "critical,remediation-agent,automation,cicd,pipeline,high-priority"

echo "================================================"
echo "✅ All issues created successfully!"
echo "================================================"
echo ""
echo "View issues at: https://github.com/darrylbowler72/agenticframework/issues"
