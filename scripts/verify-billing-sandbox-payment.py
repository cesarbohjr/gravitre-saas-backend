"""Read genuine Stripe Checkout completion and collect a genuine sandbox invoice."""
import argparse
import json
import os
import stripe

parser = argparse.ArgumentParser()
parser.add_argument('--session')
args = parser.parse_args()
key = os.environ['STRIPE_SECRET_KEY']
assert '_test_' in key and '_live_' not in key, 'Sandbox key required'
client = stripe.StripeClient(key)
if args.session:
    session = client.v1.checkout.sessions.retrieve(args.session, {'expand': ['subscription.latest_invoice']})
    subscription = session.get('subscription') or {}
    invoice = subscription.get('latest_invoice') or {}
    from urllib.parse import urlparse
    from supabase import create_client
    assert urlparse(os.environ['SUPABASE_URL']).hostname in {'localhost', '127.0.0.1'}
    db = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
    metadata = session.get('metadata') or {}
    grants = db.table('org_promotional_grants').select('status').eq('id', metadata['offer_grant_id']).eq('org_id', metadata['org_id']).execute().data or []
    billing = db.table('org_billing').select('stripe_subscription_id').eq('org_id', metadata['org_id']).execute().data or []
    items = subscription.get('items', {}).get('data', [])
    print(json.dumps({'session_id': session.id, 'livemode': session.livemode, 'checkout_status': session.status, 'subscription_status': subscription.get('status'), 'trial_end': subscription.get('trial_end'), 'invoice_id': invoice.get('id'), 'invoice_number': invoice.get('number'), 'invoice_status': invoice.get('status'), 'invoice_amount_paid': invoice.get('amount_paid'), 'grant_status': grants[0]['status'] if grants else None, 'subscription_persisted': bool(billing and billing[0]['stripe_subscription_id'] == subscription.get('id')), 'trial_has_only_licensed_items': bool(items) and all(i['price']['recurring'].get('usage_type') == 'licensed' for i in items)}))
else:
    customer = client.v1.customers.create({'name': 'Disposable invoice acceptance', 'payment_method': 'pm_card_visa', 'invoice_settings': {'default_payment_method': 'pm_card_visa'}})
    subscription = client.v1.subscriptions.create({'customer': customer.id, 'items': [{'price': os.environ['STRIPE_PRICE_ID_NODE_MONTHLY']}], 'payment_behavior': 'error_if_incomplete', 'expand': ['latest_invoice']})
    invoice = subscription.latest_invoice
    assert subscription.livemode is False and subscription.status == 'active'
    assert invoice.status == 'paid' and invoice.amount_paid == 5900 and invoice.currency == 'usd'
    client.v1.subscriptions.cancel(subscription.id)
    print(json.dumps({'livemode': False, 'invoice_id': invoice.id, 'invoice_status': invoice.status, 'amount_paid': invoice.amount_paid, 'currency': invoice.currency, 'subscription_canceled_after_verification': True}))
