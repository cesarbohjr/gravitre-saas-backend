"""Flower SecAgg+ server: exactly 100 distinct enrolled, consenting tenants."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np
from flwr.common import FitIns, ndarrays_to_parameters, parameters_to_ndarrays
from flwr.server import ServerConfig
from flwr.server.compat.legacy_context import LegacyContext
from flwr.server.strategy import FedAvg
from flwr.server.workflow import DefaultWorkflow, SecAggPlusWorkflow
from flwr.serverapp import ServerApp

from app.ml.federated_learning import verified_privacy_profile
from app.ml.federated_runtime.privacy import runtime_settings, current_permission, data_root, feature_schema_digest


class ApprovedCohortStrategy(FedAvg):
    def __init__(self, round_id, roster, enrollment, profile, digest, settings, sealed_parameters=None):
        super().__init__(fraction_fit=1, fraction_evaluate=0, min_fit_clients=100,
            min_evaluate_clients=0, min_available_clients=100, accept_failures=False,
            initial_parameters=ndarrays_to_parameters([np.zeros(5)]))
        self.round_id, self.roster, self.enrollment = round_id, roster, enrollment
        self.profile, self.digest, self.settings = profile, digest, settings
        self.selected = {}
        self.sealed_parameters = sealed_parameters or {}

    def configure_fit(self, server_round, parameters, client_manager):
        eligible = []
        seen = set()
        for node in sorted(client_manager.all().values(), key=lambda client: client.node_id):
            org = self.enrollment.get(str(node.node_id))
            if org not in self.roster or org in seen:
                continue
            current_permission(org, self.settings, self.digest)
            eligible.append((node, org))
            seen.add(org)
        if len(eligible) < 100:
            raise ValueError("100 distinct authenticated and currently consenting tenant nodes required")
        eligible = eligible[:100]
        self.selected = {node.node_id: org for node, org in eligible}
        config = {"round_id":self.round_id, "audit_digest":self.digest, "program_id":self.profile["program_id"]}
        return [(node, FitIns(parameters,{**config,'sealed_parameters':json.dumps(self.sealed_parameters[org])}))
                for node,org in eligible]

    def aggregate_fit(self, server_round, results, failures):
        # SecAgg+ calls this only after unmasking the shared aggregate. Flower
        # puts the same aggregate in each legacy FitRes. Plain FedAvg responses
        # (different individual parameter sets) are explicitly rejected here.
        if failures or len(results) != 100 or len({client.node_id for client, _ in results}) != 100:
            raise ValueError("Incomplete secure cohort; aggregate not released")
        aggregate = parameters_to_ndarrays(results[0][1].parameters)
        if len(aggregate) != 1 or aggregate[0].shape != (5,) or not np.isfinite(aggregate[0]).all():
            raise ValueError("Invalid secure aggregate")
        for client, result in results:
            org = self.selected.get(client.node_id)
            if not org:
                raise ValueError("Unexpected tenant node in aggregate")
            current_permission(org, self.settings, self.digest)
            values = parameters_to_ndarrays(result.parameters)
            if len(values) != 1 or not np.array_equal(values[0], aggregate[0]):
                raise ValueError("Unmasked individual update returned instead of a secure aggregate")
        # Candidate only. Existing per-org validation/promotion must independently
        # approve adoption; a completed FL round is not inference/outcome proof.
        destination = data_root()/f"candidate-{self.round_id}.npz"
        temporary = destination.with_suffix('.pending')
        with temporary.open('wb') as output:
            np.savez_compressed(output, schema=np.array([1]), parameters=aggregate[0], audit_digest=np.array(self.digest))
        os.chmod(temporary, 0o600)
        temporary.replace(destination)
        return ndarrays_to_parameters(aggregate), {}


app = ServerApp()


@app.main()
def main(grid, context):
    settings = runtime_settings()
    profile, digest = verified_privacy_profile(settings)
    if feature_schema_digest() != profile['feature_schema_sha256']:
        raise ValueError('Audited feature schema mismatch')
    round_id = context.run_config.get('round-id')
    if not isinstance(round_id, str) or not re.fullmatch(r'[a-f0-9]{64}', round_id):
        raise ValueError('Control-plane round identity required')
    request = json.loads((data_root()/f'round-{round_id}.json').read_text())
    if request['audit_digest'] != digest or request['program_id'] != profile['program_id']:
        raise ValueError('Round request belongs to a different audited program')
    from app.ml.federated_projection import audited_enrollment
    records = audited_enrollment(settings,profile)
    enrollment = {node_id:record['org_id'] for node_id,record in records.items()}
    strategy = ApprovedCohortStrategy(round_id,set(request['participants']),enrollment,profile,digest,settings,request['sealed_contributions'])
    legacy = LegacyContext(context=context, config=ServerConfig(num_rounds=1), strategy=strategy)
    sigma = 2 * profile['clipping_norm'] * profile['noise_multiplier']
    secure = SecAggPlusWorkflow(num_shares=1.0, reconstruction_threshold=1.0,
                                max_weight=1, clipping_range=max(profile['clipping_norm'],12*sigma), timeout=120)
    DefaultWorkflow(fit_workflow=secure)(grid, legacy)
    if not (data_root()/f'candidate-{round_id}.npz').is_file():
        raise ValueError('Secure round produced no validated candidate')
