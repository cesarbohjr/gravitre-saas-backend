# Railpack's default Python plan only copies requirements.txt into the install
# layer, so nested `-r requirements-*.txt` includes fail. This Dockerfile copies
# all requirement files before pip install.
FROM python:3.13-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/app/.venv/bin:$PATH"

COPY requirements.txt requirements-core.txt requirements-extras-data.txt requirements-extras-voice.txt ./
RUN python -m venv /app/.venv \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA}

EXPOSE 8080
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
