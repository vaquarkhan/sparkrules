# Runtime image for SparkRules API + Workbench UI
FROM python:3.11-slim AS builder

WORKDIR /app

COPY pyproject.toml README.md LICENSE CITATION.cff /app/
COPY src /app/src

RUN pip install --no-cache-dir ".[api]"

FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/src /app/src

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

LABEL org.opencontainers.image.title="sparkrules" \
      org.opencontainers.image.version="1.1.0" \
      org.opencontainers.image.description="Drools-style business rule engine for Python" \
      org.opencontainers.image.source="https://github.com/vaquarkhan/sparkrules" \
      org.opencontainers.image.licenses="Apache-2.0"

CMD ["uvicorn", "sparkrules.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
