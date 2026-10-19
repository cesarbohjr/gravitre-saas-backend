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
args = parser.parse_args()
status = json.loads(Path(args.supabase_status).read_text())
assert urlparse(status['API_URL']).hostname in {'localhost', '127.0.0.1'}, 'Local Supabase required'
root = Path(os.environ['RUNNER_TEMP'])
config = root / 'billing-stripe.toml'
cli = ['npx', '--yes', '@stripe/cli@1.54.0', '--config', str(config)]
created = subprocess.run(cli + ['sandboxes', 'create', '--email', 'billing-acceptance@gravitre.app', '--non-interactive'], capture_output=True, text=True, timeout=120, check=True)
match = re.search(r'\{\s*"secret_key"[\s\S]*?\}', created.stdout)
assert match, 'Sandbox provisioning returned no credentials'
sandbox = json.loads(match.group())
key = sandbox['secret_key']
assert '_test_' in key and '_live_' not in key
print('::add-mask::' + key)
remote = stripe.StripeClient(key)
product = remote.v1.products.create({'name': 'Isolated billing acceptance Node'})
price = remote.v1.prices.create({'product': product.id, 'currency': 'usd', 'unit_amount': 5900, 'recurring': {'interval': 'month'}})
log = root / 'billing-stripe-listener.log'
with log.open('w') as output:
    listener = subprocess.Popen(cli + ['listen', '--events', 'checkout.session.completed,checkout.session.async_payment_succeeded,customer.subscription.created,customer.subscription.updated,customer.subscription.deleted,invoice.paid,invoice.payment_failed', '--forward-to', 'http://127.0.0.1:8000/api/webhooks/stripe'], stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
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
values = {
    'SUPABASE_URL': status['API_URL'], 'SUPABASE_ANON_KEY': status['ANON_KEY'],
    'SUPABASE_SERVICE_ROLE_KEY': status['SERVICE_ROLE_KEY'], 'SUPABASE_JWT_SECRET': status['JWT_SECRET'],
    'NEXT_PUBLIC_SUPABASE_URL': status['API_URL'], 'NEXT_PUBLIC_SUPABASE_ANON_KEY': status['ANON_KEY'],
    'STRIPE_SECRET_KEY': key, 'STRIPE_WEBHOOK_SECRET': secret, 'STRIPE_PRICE_ID_NODE_MONTHLY': price.id,
    'NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY': sandbox['publishable_key'],
    'APP_ENV': 'dev', 'DISABLE_AI': 'true', 'COMMERCIAL_OFFERS_ENABLED': 'true',
    'USAGE_SYNC_INTERVAL_SECONDS': '0', 'BILLING_RECONCILIATION_ENABLED': 'false',
    'PUBLIC_APP_URL': 'http://localhost:3000', 'NEXT_PUBLIC_APP_URL': 'http://localhost:3000',
    'PLAYWRIGHT_BASE_URL': 'http://localhost:3000', 'FASTAPI_BASE_URL': 'http://127.0.0.1:8000',
    'NEXT_PUBLIC_PLAYWRIGHT_E2E': '1', 'PLAYWRIGHT_E2E': '1', 'BILLING_ACCEPTANCE_ISOLATED': '1',
}
for name in ['SUPABASE_SERVICE_ROLE_KEY', 'SUPABASE_JWT_SECRET', 'STRIPE_WEBHOOK_SECRET']:
    print('::add-mask::' + values[name])
with Path(os.environ['GITHUB_ENV']).open('a') as output:
    for name, value in values.items():
        assert '\n' not in value
        output.write(f'{name}={value}\n')
print('Configured local Supabase, real sandbox price, and signed webhook forwarding.')
