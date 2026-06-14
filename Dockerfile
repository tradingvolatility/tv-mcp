# Trading Volatility MCP — stateless container for hosted, multi-tenant deployment.
# Runs the HTTP + SSE transport; credentials arrive per request via the Authorization header.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # Serve the remote transport; bind all interfaces (the platform routes to $PORT).
    TV_MCP_TRANSPORT=http \
    HOST=0.0.0.0 \
    PORT=8080

WORKDIR /app

# Install dependencies first for better layer caching.
# AGENTS.md is force-included into the package (see pyproject) and served at /AGENTS.md.
COPY pyproject.toml README.md AGENTS.md ./
COPY src ./src
# Upgrade pip + setuptools too: the slim base ships an old setuptools with known CVEs
# (e.g. CVE-2024-6345). The app builds with hatchling and doesn't import setuptools at
# runtime, but keep the image clean for dependency scanners.
RUN pip install --upgrade pip setuptools && pip install .

# Drop privileges: run as a non-root user so any future dependency RCE can't act as root.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Stateless: credentials arrive per request via the Authorization / X-Api-Key header.
# Use /health (not /healthz) — Cloud Run reserves paths ending in "z".
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8080\")}/health')" || exit 1

CMD ["python", "-m", "tv_mcp"]
