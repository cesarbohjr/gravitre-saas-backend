"""Configure disposable local Supabase and a claimable Stripe sandbox for CI."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlparse
import stripe

parser = argparse.ArgumentParser()
parser.add_argument('--supabase-status', required=True)
parser.add_argument('--auth-only', action='store_true')
args = parser.parse_args()
status = json.loads(Path(args.supabase_status).read_text())
assert urlparse(status['API_URL']).hostname in {'localhost', '127.0.0.1'}, 'Local Supabase required'
values = {
    'SUPABASE_URL': status['API_URL'], 'SUPABASE_ANON_KEY': status['ANON_KEY'],
    'SUPABASE_SERVICE_ROLE_KEY': status['SERVICE_ROLE_KEY'], 'SUPABASE_JWT_SECRET': status['JWT_SECRET'],
    'NEXT_PUBLIC_SUPABASE_URL': status['API_URL'], 'NEXT_PUBLIC_SUPABASE_ANON_KEY': status['ANON_KEY'],
    'NEXT_PUBLIC_SUPABASE_AUTH_URL': 'http://localhost:3000', 'SUPABASE_PROJECT_URL': status['API_URL'],
    'APP_ENV': 'dev', 'DISABLE_AI': 'true', 'COMMERCIAL_OFFERS_ENABLED': 'true',
    'USAGE_SYNC_INTERVAL_SECONDS': '0', 'BILLING_RECONCILIATION_ENABLED': 'false',
    'PUBLIC_APP_URL': 'http://localhost:3000', 'NEXT_PUBLIC_APP_URL': 'http://localhost:3000',
    'PLAYWRIGHT_BASE_URL': 'http://localhost:3000', 'FASTAPI_BASE_URL': 'http://127.0.0.1:8000',
    'NEXT_PUBLIC_PLAYWRIGHT_E2E': '1', 'PLAYWRIGHT_E2E': '1', 'BILLING_ACCEPTANCE_ISOLATED': '1',
}
for name in ['SUPABASE_SERVICE_ROLE_KEY', 'SUPABASE_JWT_SECRET']:
    print('::add-mask::' + values[name])
with Path(os.environ['GITHUB_ENV']).open('a') as output:
    for name, value in values.items():
        assert '\n' not in value
        output.write(f'{name}={value}\n')
if args.auth_only:
    print('Configured disposable local Supabase for genuine role sign-in.')
    raise SystemExit(0)
root = Path(os.environ['RUNNER_TEMP'])
config = root / 'billing-stripe.toml'
cli = ['npx', '--yes', '@stripe/cli@1.54.0', '--config', str(config)]
provided_key = os.environ.get('STRIPE_TEST_SECRET_KEY', '')
provided_public = os.environ.get('STRIPE_TEST_PUBLISHABLE_KEY', '')
legacy_key = os.environ.get('STRIPE_EXISTING_SECRET_KEY', '')
legacy_public = os.environ.get('STRIPE_EXISTING_PUBLISHABLE_KEY', '')
if not provided_key and '_test_' in legacy_key and legacy_public.startswith('pk_test_'):
    provided_key, provided_public = legacy_key, legacy_public
if provided_key:
    sandbox = {'secret_key': provided_key, 'publishable_key': provided_public}
    assert sandbox['publishable_key'].startswith('pk_test_'), 'Sandbox publishable key required'
else:
    if os.environ.get('BILLING_REQUIRE_STRIPE_TEST_KEYS') == '1':
        raise RuntimeError('Configure STRIPE_TEST_SECRET_KEY and STRIPE_TEST_PUBLISHABLE_KEY as repository Actions secrets from a dedicated Stripe sandbox.')
    created = subprocess.run(cli + ['sandboxes', 'create', '--email', 'billing-acceptance@gravitre.app', '--non-interactive'], capture_output=True, text=True, timeout=120, check=True)
    match = re.search(r'\{\s*"secret_key"[\s\S]*?\}', created.stdout)
    if not match:
        diagnostics = re.sub(r'\b(?:[srpk]+(?:cs)?_(?:test|live)_|whsec_)[A-Za-z0-9]+', '[REDACTED]', created.stdout + created.stderr)
        diagnostics = re.sub(r'https://[^\s\"\']+', '[REDACTED_URL]', diagnostics)
        raise RuntimeError('Sandbox unavailable. Configure STRIPE_TEST_SECRET_KEY and STRIPE_TEST_PUBLISHABLE_KEY as Actions secrets. ' + diagnostics[-1500:])
    sandbox = json.loads(match.group())
key = sandbox['secret_key']
assert '_test_' in key and '_live_' not in key
print('::add-mask::' + key)
remote = stripe.StripeClient(key)
product = remote.v1.products.create({'name': 'Isolated billing acceptance Node'})
price = remote.v1.prices.create({'product': product.id, 'currency': 'usd', 'unit_amount': 5900, 'recurring': {'interval': 'month'}})
log = root / 'billing-stripe-listener.log'
with log.open('w') as output:
    listener = subprocess.Popen(cli + ['listen', '--events', 'checkout.session.completed,checkout.session.async_payment_succeeded,customer.subscription.created,customer.subscription.updated,customer.subscription.deleted,invoice.paid,invoice.payment_failed', '--forward-to', 'http://127.0.0.1:8000/api/webhooks/stripe'], stdout=output, stderr=subprocess.STDOUT, start_new_session=True, env={**os.environ, 'STRIPE_API_KEY': key})
secret = None
for _ in range(90):
    found = re.search(r'whsec_[A-Za-z0-9]+', log.read_text(errors='replace'))
    if found:
        secret = found.group(); break
    if listener.poll() is not None:
        diagnostics = re.sub(r'\b(?:[srpk]+(?:cs)?_(?:test|live)_|whsec_)[A-Za-z0-9]+', '[REDACTED]', log.read_text(errors='replace'))
        raise RuntimeError('Stripe listener exited before readiness: ' + diagnostics[-2000:])
    time.sleep(1)
assert secret, 'Stripe listener did not become ready'
print('::add-mask::' + secret)
with Path(os.environ['GITHUB_ENV']).open('a') as output:
    for name, value in {'STRIPE_SECRET_KEY': key, 'STRIPE_WEBHOOK_SECRET': secret, 'STRIPE_PRICE_ID_NODE_MONTHLY': price.id, 'NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY': sandbox['publishable_key']}.items():
        assert '\n' not in value
        output.write(f'{name}={value}\n')
print('Configured local Supabase, real sandbox price, and signed webhook forwarding.')
