"""Private, acceptance-only HTTPS transport. Never imported by production workers.

The normal browser destination validator rejects all private IPs. This module
binds one generated synthetic hostname to the inspected Docker bridge and a
single ephemeral receiver port, only in the acceptance worker and its derived
gateway image. No task, header, DNS answer or model output selects that route.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import http.client
import ipaddress
import json
from pathlib import Path
import re
import shutil
import socket
import ssl
import subprocess
import sys


@dataclass(frozen=True)
class FixtureRoute:
    host: str
    address: str
    port: int

    def __post_init__(self):
        if not re.fullmatch(r'qa-[0-9a-f]{32}\.example\.invalid', self.host):
            raise ValueError('Invalid disposable fixture hostname')
        ip = ipaddress.ip_address(self.address)
        if (ip.version != 4 or not ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_unspecified or ip.is_multicast or ip.is_reserved):
            raise ValueError('Invalid disposable fixture bridge')
        if type(self.port) is not int or not 1024 <= self.port <= 65535:
            raise ValueError('Invalid disposable fixture port')

    def resolve(self, host):
        if host != self.host:
            raise ValueError('Outside disposable fixture scope')
        return [self.address]


class FixtureSocket:
    """Module-local gateway socket facade, never a global socket patch."""
    def __init__(self, route, delegate=socket):
        self.route, self.delegate = route, delegate

    def create_connection(self, address, *args, **kwargs):
        # The unchanged gateway already verified CONNECT hostname, port 443
        # and persisted authority. Only that exact numeric destination maps.
        if address != (self.route.address, 443):
            raise ValueError('Outside disposable fixture transport')
        return self.delegate.create_connection((self.route.address, self.route.port), *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.delegate, name)


def issue_fixture_certificate(root: Path, host: str):
    if not re.fullmatch(r'qa-[0-9a-f]{32}\.example\.invalid', host):
        raise ValueError('Invalid disposable fixture hostname')
    ca, ca_key, cert, key, csr = (root / name for name in
        ('ca.crt', 'ca.key', 'fixture.crt', 'fixture.key', 'fixture.csr'))
    def openssl(*args):
        subprocess.run(['openssl', *map(str,args)], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    openssl('req','-x509','-newkey','rsa:2048','-nodes','-days','1',
        '-subj','/CN=Gravitre disposable fixture CA','-addext','basicConstraints=critical,CA:TRUE,pathlen:0',
        '-addext','keyUsage=critical,keyCertSign,cRLSign','-keyout',ca_key,'-out',ca)
    openssl('req','-new','-newkey','rsa:2048','-nodes','-subj','/CN='+host,'-keyout',key,'-out',csr)
    ext=root/'leaf.ext'
    ext.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:'+host+'\n')
    openssl('x509','-req','-in',csr,'-CA',ca,'-CAkey',ca_key,'-CAcreateserial','-days','1','-extfile',ext,'-out',cert)
    ca_key.unlink()
    key.chmod(0o600)
    return ca,cert,key


def probe_private_https(address, port, host, ca, page):
    # Numeric socket address; SNI and hostname verification use the exact
    # synthetic name. No resolver, no redirect and no certificate bypass.
    context=ssl.create_default_context(cafile=str(ca) if ca is not None else None)
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    with socket.create_connection((address,port),timeout=5) as raw:
        with context.wrap_socket(raw,server_hostname=host) as tls:
            tls.sendall(('GET /page HTTP/1.1\r\nHost: '+host+'\r\nConnection: close\r\n\r\n').encode('ascii'))
            response=http.client.HTTPResponse(tls)
            try:
                response.begin()
                if response.status!=200 or response.read(len(page)+1)!=page:
                    raise ValueError('Unexpected disposable fixture response')
            finally:response.close()


# Chromium's local NSS trust database is on the per-job writable workspace;
# only the ephemeral CA public certificate enters these derived images.
CHROMIUM_WRAPPER = """#!/bin/sh
set -eu
test "$HOME" = /workspace
for arg in "$@"; do
    case "$arg" in
        --ignore-certificate-errors*|--allow-insecure-localhost*|--ignore-ssl-errors*)
            echo 'Certificate bypass forbidden in acceptance browser' >&2
            exit 1 ;;
    esac
done
for db in "$HOME/.pki/nssdb" "$HOME/.local/share/pki/nssdb"; do
    mkdir -p "$db"
    if [ ! -f "$db/cert9.db" ]; then
        certutil -N --empty-password -d "sql:$db"
    fi
    certutil -A -d "sql:$db" -n gravitre-disposable-fixture -t 'C,,' -i /runner/fixture-ca.crt
done
exec /usr/bin/chromium-original "$@"
"""


def build_fixture_images(root: Path, route: FixtureRoute, ca: Path):
    # Build contexts contain only public certificate, exact route and source.
    # The receiver key and all IAM credentials remain outside Docker contexts.
    for base,tag in (('native-browser','native-fixture-browser'),
                     ('native-playwright-comparison','native-fixture-playwright')):
        context=root/tag;context.mkdir(mode=0o700)
        shutil.copyfile(ca,context/'fixture-ca.crt')
        (context/'chromium').write_text(CHROMIUM_WRAPPER)
        (context/'Dockerfile').write_text(
            'FROM '+base+'\nUSER root\n'
            'RUN apt-get update && apt-get install -y --no-install-recommends libnss3-tools && rm -rf /var/lib/apt/lists/*\n'
            'RUN mv /usr/bin/chromium /usr/bin/chromium-original\n'
            'COPY fixture-ca.crt /runner/fixture-ca.crt\n'
            'COPY chromium /usr/bin/chromium\n'
            'RUN chmod 0755 /usr/bin/chromium && chmod 0644 /runner/fixture-ca.crt\n'
            'USER 10001:10001\n')
        subprocess.run(['docker','build','-q','-t',tag,str(context)],check=True,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=300)
    context=root/'fixture-gateway';context.mkdir(mode=0o700)
    shutil.copyfile(Path(__file__),context/'private_https_fixture.py')
    (context/'fixture-route.json').write_text(json.dumps(asdict(route)))
    (context/'gateway.py').write_text('from private_https_fixture import run_gateway\nrun_gateway()\n')
    (context/'Dockerfile').write_text(
        'FROM native-tenant-gateway\nUSER root\n'
        'RUN mv /runner/gateway.py /runner/gateway_impl.py\n'
        'COPY gateway.py private_https_fixture.py fixture-route.json /runner/\n'
        'RUN chmod 0444 /runner/fixture-route.json\nUSER 10001:10001\n')
    subprocess.run(['docker','build','-q','-t','native-fixture-gateway',str(context)],check=True,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=120)


def run_gateway():
    # Run the original CONNECT/authorization/relay implementation unchanged,
    # with a narrowly scoped resolver and transport in this derived image only.
    import gateway_impl
    route=FixtureRoute(**json.loads(Path('/runner/fixture-route.json').read_text()))
    config=json.loads(sys.stdin.buffer.read(65537))
    if config.get('allowed_hosts') != [route.host]:
        raise ValueError('Private fixture gateway requires exact approved host')
    gateway_impl.CONFIG=config
    gateway_impl.public_addresses=route.resolve
    gateway_impl.socket=FixtureSocket(route)
    gateway_impl.BoundedHTTPServer(('0.0.0.0',8080),gateway_impl.Handler).serve_forever()
