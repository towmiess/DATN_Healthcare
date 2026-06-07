#!/bin/bash
# ================================================================
# START SERVER — Shell script wrapper cho Windows/Linux/Mac
# ================================================================

set -e

cd "$(dirname "$0")/.."

echo "🚀 Healthcare RAG Server Launcher"
echo "=================================="
echo ""

# Parse arguments
LLM_MODE="${1:-auto}"
PORT="${2:-8000}"
RELOAD="${3:-}"

if [ "$RELOAD" = "--reload" ]; then
    RELOAD_FLAG="--reload"
else
    RELOAD_FLAG=""
fi

# Show info
echo "📋 Configuration:"
echo "   LLM Mode: $LLM_MODE"
echo "   Port: $PORT"
echo "   Reload: $RELOAD_FLAG"
echo ""

# Start server
echo "Starting server..."
python scripts/start_server.py --llm "$LLM_MODE" --port "$PORT" $RELOAD_FLAG

echo "✅ Done"
