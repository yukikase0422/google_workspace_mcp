#!/bin/sh
set -e

# Cloud Run supplies PORT; default to 8080 for local use
PORT_ENV="${PORT:-8080}"
export PORT="${PORT_ENV}"
export WORKSPACE_MCP_PORT="${PORT_ENV}"

# Bind on all interfaces unless overridden
BASE_URI="${WORKSPACE_MCP_BASE_URI:-http://0.0.0.0}"
export WORKSPACE_MCP_BASE_URI="${BASE_URI}"

# Build CLI arguments for workspace-mcp
ARGS="--transport streamable-http"

if [ -n "${WORKSPACE_MCP_TOOLS}" ]; then
  ARGS="${ARGS} --tools ${WORKSPACE_MCP_TOOLS}"
fi

if [ -n "${WORKSPACE_MCP_TOOL_TIER}" ]; then
  ARGS="${ARGS} --tool-tier ${WORKSPACE_MCP_TOOL_TIER}"
fi

if [ "${MCP_SINGLE_USER_MODE}" = "true" ] || [ "${MCP_SINGLE_USER_MODE}" = "1" ]; then
  ARGS="${ARGS} --single-user"
fi

echo "Starting workspace-mcp on ${WORKSPACE_MCP_BASE_URI}:${WORKSPACE_MCP_PORT} with args: ${ARGS}"

exec workspace-mcp ${ARGS}
