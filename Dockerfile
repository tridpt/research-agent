# Research Agent container image (hardened multi-stage build).
# Build:  docker build -t research-agent .
# Web UI: docker run --rm -p 8501:8501 -e RESEARCH_AGENT_API_KEY=... research-agent
# CLI:    docker run --rm -e RESEARCH_AGENT_API_KEY=... research-agent \
#           research-agent "your question" -v

# --------------------------------------------------------------------------
# Stage 1: build the locked virtual environment (dev tooling excluded).
# --------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# The uv package manager (reproducible installs from the committed lockfile).
COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /uvx /bin/

WORKDIR /app

# Install only runtime extras (UI, PDF, DOCX) — never the dev/test toolchain —
# into a self-contained /app/.venv from the committed lockfile.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY ui ./ui
RUN uv sync --frozen --extra ui --extra pdf --extra docx

# --------------------------------------------------------------------------
# Stage 2: minimal runtime image, running as a non-root user.
# --------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/app/.venv/bin:$PATH" \
    HOME=/home/appuser

# A broad-coverage Unicode font so PDF export renders non-Latin (e.g.
# Vietnamese) text. Installed in the runtime stage because it is read at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser

WORKDIR /app

# Copy the pre-built environment and application code, owned by the non-root user.
COPY --from=builder --chown=appuser:appuser /app /app

USER appuser

EXPOSE 8501

# Fail the container health check if Streamlit stops serving.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", \
         "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=4).status==200 else 1)"]

# Default entrypoint launches the Streamlit web UI; override the CMD to use the
# CLI, e.g. `docker run ... research-agent research-agent "question" -v`.
CMD ["streamlit", "run", "ui/app.py", \
     "--server.address=0.0.0.0", "--server.port=8501"]
