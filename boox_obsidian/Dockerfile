FROM python:3.13-alpine

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# rclone henter PDF'er fra Drive. nodejs og npm bruges kun af den valgfri Obsidian Headless sync.
RUN apk add --no-cache rclone nodejs npm tzdata ca-certificates \
    && pip install --no-cache-dir "pypdf>=6,<7" \
    && (npm install -g obsidian-headless || echo "Obsidian Headless kunne ikke installeres, sync er sat ud af spil")

WORKDIR /opt/boox
COPY app /opt/boox/app

CMD ["python", "-m", "app"]
