# Research Agent container image.
# Build:  docker build -t research-agent .
# Web UI: docker run --rm -p 8501:8501 -e RESEARCH_AGENT_API_KEY=... research-agent
# CLI:    docker run --rm -e RESEARCH_AGENT_API_KEY=... research-agent \
#           uv run --frozen research-agent "your question" -v
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy

# A broad-coverage Unicode font so PDF export renders non-Latin (e.g. Vietnamese) text.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# The uv package manager (reproducible installs from the committed lockfile).
COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /uvx /bin/

WORKDIR /app

# Copy metadata + sources needed to build and install the project, then sync the
# locked environment with all optional extras (UI, PDF, DOCX).
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY ui ./ui
RUN uv sync --frozen --all-extras

EXPOSE 8501

# Default entrypoint launches the Streamlit web UI; override the CMD to use the CLI.
CMD ["uv", "run", "--frozen", "streamlit", "run", "ui/app.py", \
     "--server.address=0.0.0.0", "--server.port=8501"]
