# ════════════════════════════════════════════════════════════════
# 🔱 ZERO CUTLOSS EMPIRE — Imperial Agent Image
# Base: python:3.11-slim (NO CUDA REQUIRED — all Agents call
#       Ollama via HTTP API, no direct torch/GPU execution)
# ════════════════════════════════════════════════════════════════
FROM python:3.11-slim

# ── Environment Variables ─────────────────────────────────────
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_ROOT_USER_ACTION=ignore
ENV TZ=UTC

# ── System Dependencies ─────────────────────────────────────
# curl/wget/jq: Shell scripts, health checks, Ollama API probing
# git: Pull plugins, version control
# build-essential: Compiling TA-Lib C library + native extensions
# nodejs/npm: ClawCode Tool Executor runtime (JS tools)
# procps: pkill/pgrep for process management
# Playwright system deps are installed below
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    jq \
    git \
    build-essential \
    nodejs \
    npm \
    procps \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# ── TA-Lib C Library (Technical analysis: RSI/MACD/BB) ───────
# pip install TA-Lib WILL FAIL without this C library!
RUN wget -q http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib/ \
    && ./configure --prefix=/usr \
    && make \
    && make install \
    && cd .. \
    && rm -rf ta-lib-0.4.0-src.tar.gz ta-lib/

# ── Working Directory ────────────────────────────────────────
WORKDIR /app

# ── Install Python Dependencies (layer cache) ───────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Playwright Chromium (for Agent 07 Web Injector) ──────────────
RUN playwright install chromium \
    && playwright install-deps

# ── Create Directory Structure (prevents FileNotFoundError) ───────
RUN mkdir -p \
    /app/logs \
    /app/memory \
    /app/memory/chroma_db \
    /app/dpo_lab/pairs \
    /app/dpo_lab/snapshots \
    /app/dpo_lab/evaluations \
    /app/dpo_lab/CLAW/pairs \
    /app/emf_lab/pairs \
    /app/emf_lab/deep_research_reports \
    /app/aeo_lab \
    /app/inbox \
    /app/inbox/soul_patches \
    /app/boost_scenarios \
    /app/notebooklm_sources \
    /app/security/threat_reports \
    /app/security/opus_queue

# ── Copy codebase ────────────────────────────────────────────
COPY tools/       ./tools/
COPY agents/      ./agents/
COPY scripts/     ./scripts/
COPY config/      ./config/

# ── PYTHONPATH: Enable importing from tools/ and scripts/ ────────
ENV PYTHONPATH="/app:/app/tools:/app/scripts"

# ── Healthcheck: Self check Redis connection ──────────────────
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python3 -c "import redis, os; r=redis.from_url(os.getenv('REDIS_URL','redis://redis:6379')); r.ping()" || exit 1

# Default CMD (overridden by docker-compose per service)
CMD ["python3", "-c", "print('ZCL Imperial Agent ready. Override CMD in docker-compose.')"]
