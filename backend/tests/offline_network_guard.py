"""Opt-in pytest plugin: -p tests.offline_network_guard.

Unit and simulated pipeline runs must fail rather than call real providers.
Do not enable this plugin for explicitly authorized live acceptance tests.
"""
import socket

import pytest


@pytest.fixture(autouse=True)
def prohibit_outbound_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise OSError("Offline verification: outbound network is disabled")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
