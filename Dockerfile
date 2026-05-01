# Runtime image for SparkRules API + Workbench UI
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md LICENSE CITATION.cff /app/
COPY src /app/src

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "sparkrules.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
