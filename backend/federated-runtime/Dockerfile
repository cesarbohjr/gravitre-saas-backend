# Build from the backend directory. Immutable image digest must be independently
# audited and bound to the manifest before this runtime accepts a round.
FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FLWR_TELEMETRY_ENABLED=0 PYTHONPATH=/app/federated-runtime
COPY requirements-core.txt ./
COPY federated-runtime/requirements.txt ./federated-runtime/requirements.txt
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r federated-runtime/requirements.txt
COPY app ./federated-runtime/app
COPY federated-runtime ./federated-runtime
RUN useradd --uid 10001 --create-home gravitre && mkdir /data && chown gravitre /data
WORKDIR /app/federated-runtime
USER gravitre
VOLUME ["/data"]
EXPOSE 8443
CMD ["python", "-m", "app.ml.federated_runtime"]
