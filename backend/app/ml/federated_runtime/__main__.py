"""The deployed control-plane entrypoint always requires mutual TLS."""
import os
import ssl

import uvicorn


def main():
    from app.ml.federated_runtime.control import runtime_profile
    runtime_profile()
    uvicorn.run('app.ml.federated_runtime.control:app', host='0.0.0.0', port=8443, workers=1,
        ssl_certfile=os.environ['FEDERATED_CONTROL_TLS_CERT_FILE'],
        ssl_keyfile=os.environ['FEDERATED_CONTROL_TLS_KEY_FILE'],
        ssl_ca_certs=os.environ['FEDERATED_CONTROL_TLS_CA_FILE'], ssl_cert_reqs=ssl.CERT_REQUIRED)


if __name__ == '__main__':
    main()
