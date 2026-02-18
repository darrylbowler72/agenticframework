#!/usr/bin/env bash
#
# run-local.sh - Launch the Agentic Framework locally using Podman or Docker
#
# Usage:
#   bash scripts/run-local.sh up       # Start services (reuse cached images)
#   bash scripts/run-local.sh build    # Build/rebuild all container images
#   bash scripts/run-local.sh rebuild  # Force rebuild and start all services
#   bash scripts/run-local.sh down     # Stop all services
#   bash scripts/run-local.sh logs     # Tail logs from all services
#   bash scripts/run-local.sh restart  # Restart all services (no rebuild)
#   bash scripts/run-local.sh status   # Show service status
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.local.yml"
ENV_FILE="$PROJECT_ROOT/.env"

# -------------------------------------------------------------------
# Detect container compose tool (podman-compose > podman compose > docker compose)
# -------------------------------------------------------------------
detect_compose() {
    if command -v podman-compose &>/dev/null; then
        echo "podman-compose"
    elif podman compose version &>/dev/null 2>&1; then
        echo "podman compose"
    elif docker compose version &>/dev/null 2>&1; then
        echo "docker compose"
    elif command -v docker-compose &>/dev/null; then
        echo "docker-compose"
    else
        echo ""
    fi
}

COMPOSE_CMD=$(detect_compose)

if [[ -z "$COMPOSE_CMD" ]]; then
    echo "ERROR: No container compose tool found."
    echo "Install one of: podman-compose, podman (with compose plugin), or docker compose"
    exit 1
fi

echo "Using compose tool: $COMPOSE_CMD"

# -------------------------------------------------------------------
# Validate .env file
# -------------------------------------------------------------------
validate_env() {
    if [[ ! -f "$ENV_FILE" ]]; then
        echo "ERROR: .env file not found at $ENV_FILE"
        echo ""
        echo "Create it from the template:"
        echo "  cp .env.local.template .env"
        echo "  # Then edit .env and fill in your API keys"
        exit 1
    fi

    # Fix Windows CRLF line endings (prevents \r in env var values)
    if file "$ENV_FILE" | grep -q CRLF; then
        sed -i 's/\r$//' "$ENV_FILE"
        echo "Fixed Windows line endings in .env file"
    fi

    # Check required keys are set (not placeholder values)
    local missing=0
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
        key=$(echo "$key" | xargs)  # trim whitespace
        value=$(echo "$value" | xargs)

        if [[ "$key" == "ANTHROPIC_API_KEY" && ( -z "$value" || "$value" == "your_anthropic_api_key_here" ) ]]; then
            echo "ERROR: ANTHROPIC_API_KEY not set in .env"
            missing=1
        fi
        if [[ "$key" == "GITHUB_TOKEN" && ( -z "$value" || "$value" == "your_github_token_here" ) ]]; then
            echo "ERROR: GITHUB_TOKEN not set in .env"
            missing=1
        fi
    done < "$ENV_FILE"

    if [[ $missing -eq 1 ]]; then
        echo ""
        echo "Edit .env and fill in your real API keys."
        exit 1
    fi
}

# -------------------------------------------------------------------
# Commands
# -------------------------------------------------------------------
cmd_up() {
    validate_env
    echo "Starting Agentic Framework (local mode)..."
    echo "Using cached images. Run 'build' or 'rebuild' to update images."
    $COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
    echo ""
    echo "Services starting. Use 'bash scripts/run-local.sh logs' to watch."
    echo ""
    print_urls
}

cmd_build() {
    validate_env
    echo "Building container images..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build
    echo ""
    echo "All images built. Run 'bash scripts/run-local.sh up' to start services."
}

cmd_rebuild() {
    validate_env
    echo "Rebuilding and starting Agentic Framework (local mode)..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build
    echo ""
    echo "Services starting. Use 'bash scripts/run-local.sh logs' to watch."
    echo ""
    print_urls
}

print_urls() {
    echo "Service URLs:"
    echo "  Planner Agent:     http://localhost:8000/health"
    echo "  CodeGen Agent:     http://localhost:8001/health"
    echo "  Remediation Agent: http://localhost:8002/health"
    echo "  Chatbot UI:        http://localhost:8003"
    echo "  Migration Agent:   http://localhost:8004/health"
    echo "  MCP GitHub Server: http://localhost:8100/health"
}

cmd_down() {
    echo "Stopping Agentic Framework..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" down
    echo "All services stopped."
}

cmd_logs() {
    $COMPOSE_CMD -f "$COMPOSE_FILE" logs -f
}

cmd_restart() {
    cmd_down
    cmd_up
}

cmd_status() {
    $COMPOSE_CMD -f "$COMPOSE_FILE" ps
}

# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------
case "${1:-help}" in
    up)      cmd_up ;;
    build)   cmd_build ;;
    rebuild) cmd_rebuild ;;
    down)    cmd_down ;;
    logs)    cmd_logs ;;
    restart) cmd_restart ;;
    status)  cmd_status ;;
    *)
        echo "Usage: bash scripts/run-local.sh {up|build|rebuild|down|logs|restart|status}"
        echo ""
        echo "Commands:"
        echo "  up       Start services using cached images"
        echo "  build    Build/rebuild container images only"
        echo "  rebuild  Force rebuild and start all services"
        echo "  down     Stop and remove all services"
        echo "  logs     Tail logs from all services"
        echo "  restart  Restart services (no rebuild)"
        echo "  status   Show running services"
        exit 1
        ;;
esac
