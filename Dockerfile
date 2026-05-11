FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DISPLAY=:99 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    dbus-x11 \
    xauth \
    curl \
    ca-certificates \
    fonts-liberation \
    fonts-noto-color-emoji \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libgtk-3-0 \
    libasound2 \
    libxshmfence1 \
    libx11-xcb1 \
    libdrm2 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir uv

COPY pyproject.toml README.md ./

COPY uv.lock* ./

RUN uv sync --frozen --no-dev || uv sync --no-dev

RUN uv run playwright install chromium

COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

CMD ["/entrypoint.sh"]

