FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (better layer caching). pyproject.toml defines the
# package + the [gemini] extra (google-genai) used in production.
COPY pyproject.toml .
COPY resume_tailor ./resume_tailor
COPY api ./api

RUN pip install --no-cache-dir -e ".[gemini]"

EXPOSE 8000

# 0.0.0.0 so the container accepts connections from outside itself.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
