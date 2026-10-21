# Private retrieval federation runtime

This optional deployment reuses the existing retrieval ranker. It does not introduce a new intelligence engine or automatically promote aggregates. Main API runtime does not install Flower or PyDP.

## Deployment contract

Build from `backend` using `docker build -f federated-runtime/Dockerfile .`. Pin the resulting image by digest. All Flower ServerApp/ClientApp executors must use that same audited image, with runtime dependency installation disabled. The app bundle supplies source; dependencies are preinstalled by this Dockerfile. Never install this image with source database service-role or blob read/write keys.

Provision a TLS SuperLink with authenticated SuperNode enrollment and durable SQLite state. Run each tenant SuperNode with a distinct authenticated node identity and `org_id` node configuration. Mount only that tenant's RSA private parameter key via `FEDERATED_PARAMETER_PRIVATE_KEY_FILE`. Public node IDs, organization UUIDs and distinct RSA public keys are recorded in the independently reviewed registry. Encryption key size is 3072–8192 bits. The source API alone reads registry artifacts and encrypts five canonical ranker parameters to the tenant's key; raw documents, examples, labels, counts and global store keys never enter Flower.

Use the installed Flower 1.41 CLI's documented production TLS flags and authenticated SuperNode configuration. No insecure mode is supported. For the control process mount `$FLWR_HOME/config.toml` containing:

```toml
[superlink]
default = "production"
[superlink.production]
address = "<private-superlink-control-address>"
root-certificates = "/run/secrets/superlink-ca.pem"
insecure = false
```

Mount `FEDERATED_CONTROL_TLS_CERT_FILE`, `FEDERATED_CONTROL_TLS_KEY_FILE`, and `FEDERATED_CONTROL_TLS_CA_FILE`; the entrypoint requires client certificates. The API coordinator needs its separately scoped client certificate/key/CA. Mount durable `/data` for the controller and ServerApp (shared round/candidate files), and separate durable per-tenant `/data` for privacy ledgers. Never share tenant private keys or privacy-ledger directories. Restrict all Flower runtime APIs to the private network; authenticate executor connections and disable dynamic runtime dependency installation.

Configure the independently signed audit manifest/public key, immutable deployment digest, feature schema digest, node-registry digest, owner/legal review, expiration, organization-level replace-one DP parameters and total round limit. `FEDERATED_CONSENT_SERVICE_URL` points at the main API's `/api/admin/ml/federation/consent`; its distinct minimum-32-character secret authorizes only metadata readback. The callback must use HTTPS. Main API requires the corresponding secret and public registry; Flower containers receive no database credentials.

## Operation and recovery

The existing company-learning reconciler detects 100 distinct currently approved tenants with compatible deployed rankers and dispatches an encrypted cohort. Every participant is rechecked before contribution and release. Exactly 100 nodes must complete Flower SecAgg+; the client applies Google DP Gaussian noise with replace-one sensitivity and a durable composed RDP budget before releasing a masked contribution. No plaintext FedAvg fallback exists.

The controller persists the Flower run ID and reads official `flwr ls` source state. On restart, GET round readback reconciles a known run without redispatching. Unknown dispatch identity remains blocked. Privacy reservations are never refunded or reset by failure/restart. Operators must reconcile an unknown reservation from the actual source record rather than delete ledgers.

Output is a private aggregate **candidate**, never a deployed artifact or proof of customer outcomes. Adoption still requires independent per-organization held-out validation and the existing promotion gate. No production federation is authorized by synthetic tests. An independent privacy review, provisioned authenticated compute and at least 100 real tenant approvals are mandatory deployment prerequisites.
