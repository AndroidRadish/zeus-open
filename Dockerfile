# ZeusOpen v3 Backend Dockerfile
# Packages the FastAPI backend + v3 orchestrator scripts into a runnable container.

FROM python:3.11-slim

LABEL maintainer="zeus-open"
LABEL description="ZeusOpen v3 multi-agent orchestration backend"

# Install system dependencies (git for workspace bootstrapping, graphviz for SVG rendering)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the entire project
COPY . /app

# Expose the default v3 server port
EXPOSE 8234

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8234/health')" || exit 1

# Default: start the v3 runner in serve mode
CMD ["python", ".zeus/v3/scripts/run.py", "--mode", "serve", "--host", "0.0.0.0", "--port", "8234"]
