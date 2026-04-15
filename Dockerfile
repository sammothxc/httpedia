FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/sammothxc/httpedia"
LABEL org.opencontainers.image.description="Wikipedia proxy serving pure HTML 3.2 for vintage browsers"
LABEL org.opencontainers.image.licenses="GPL-3.0"

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r httpedia && useradd -r -g httpedia -m httpedia

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY httpedia.py .
COPY static/ static/

RUN chown -R httpedia:httpedia /app

USER httpedia

EXPOSE 80

CMD ["gunicorn", "--bind", "0.0.0.0:80", "--workers", "2", "httpedia:app"]
