"""Read-only sequencing: older actor-wide native probes must finish first."""
import json
import os
import time
import urllib.request

REPO = 'cesarbohjr/gravitre-saas-backend'


def main():
    if os.environ.get('GITHUB_REPOSITORY') != REPO:
        raise ValueError('acceptance repository mismatch')
    current = int(os.environ['GITHUB_RUN_ID'])
    token = os.environ['GH_TOKEN']
    endpoint = 'https://api.github.com/repos/' + REPO + '/actions/runs'

    def get(url):
        request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token,
            'Accept': 'application/vnd.github+json'})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    # Snapshot only predecessors. Newer commits must not create a wait cycle.
    runs = get(endpoint + '?branch=feat%2Fphase2-dialogue-intelligence&event=pull_request&per_page=100')['workflow_runs']
    pending = {r['id'] for r in runs if r['id'] < current and
        r['name'] == 'Voice gates 2 and 3 execution' and r['status'] != 'completed'}
    deadline = time.monotonic() + 1200
    while pending:
        pending = {run for run in pending if get(endpoint + '/' + str(run))['status'] != 'completed'}
        if not pending:
            break
        print('Waiting for predecessor acceptance runs:', sorted(pending), flush=True)
        if time.monotonic() >= deadline:
            raise TimeoutError('predecessor acceptance executions still active; native trials NOT RUN')
        time.sleep(10)
    print('PREDECESSOR_ACCEPTANCE_RUNS_TERMINAL')


if __name__ == '__main__':
    main()
