"""Flower bundle entrypoints; implementation lives in the audited runtime image."""
from app.ml.federated_runtime import server, client

server_app = server.app
client_app = client.app
