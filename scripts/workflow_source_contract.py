"""Inspect actual installed source jobs while retaining their event provenance.

During migration the old YAML is read directly. After cutover, job bodies come
from the installed canonical lane; only the former event/name metadata comes
from retained source contracts. Event selection is tested separately by replay.
"""
import copy
import json
from pathlib import Path
from runpy import run_path

import yaml


def definition(root: Path, filename: str):
    root = Path(root)
    loader = run_path(str(root / 'scripts/build-canonical-workflows.py'), run_name='__workflow_contract_loader__')['load']
    legacy = root / '.github/workflows' / filename
    if legacy.exists():
        return loader(legacy)
    contracts = json.loads((root / 'docs/delivery/master-qa-workflow-source-contracts.json').read_text())
    source = copy.deepcopy(contracts[Path(filename).stem])
    records = json.loads((root / 'docs/delivery/master-qa-workflow-replacement-parity.json').read_text())['sources']
    record = next(item for item in records if item['source'] == '.github/workflows/' + filename)
    lane = loader(root / '.github/workflows' / ('qa-' + record['lane'] + '.yml'))
    source['jobs'] = {old: lane['jobs'][new] for old, new in record['jobs'].items()}
    return source


def text(root: Path, filename: str):
    return yaml.safe_dump(definition(root, filename), sort_keys=False, allow_unicode=True, width=1200)
