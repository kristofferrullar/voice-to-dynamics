# ── Stage 1: Python + Node.js base ────────────────────────────────────────────
FROM python:3.12-slim AS base

# Node.js 20 LTS — required for GitHub MCP server (npx @modelcontextprotocol/server-github)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

WORKDIR /app

# ── Stage 2: Install Python dependencies ──────────────────────────────────────
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-editable

# ── Stage 3: Copy application code ────────────────────────────────────────────
COPY . .

# ── Runtime ───────────────────────────────────────────────────────────────────
EXPOSE 8080

# Health check — polls the /status endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/status || exit 1

CMD [".venv/bin/uvicorn", "ui.app:app", "--host", "0.0.0.0", "--port", "8080"]
