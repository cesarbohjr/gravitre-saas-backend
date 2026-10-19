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
    print(json.dumps({'session_id': session.id, 'livemode': session.livemode, 'checkout_status': session.status, 'subscription_status': subscription.get('status'), 'trial_end': subscription.get('trial_end'), 'invoice_status': invoice.get('status'), 'invoice_amount_paid': invoice.get('amount_paid')}))
else:
    customer = client.v1.customers.create({'name': 'Disposable invoice acceptance', 'payment_method': 'pm_card_visa', 'invoice_settings': {'default_payment_method': 'pm_card_visa'}})
    subscription = client.v1.subscriptions.create({'customer': customer.id, 'items': [{'price': os.environ['STRIPE_PRICE_ID_NODE_MONTHLY']}], 'payment_behavior': 'error_if_incomplete', 'expand': ['latest_invoice']})
    invoice = subscription.latest_invoice
    assert subscription.livemode is False and subscription.status == 'active'
    assert invoice.status == 'paid' and invoice.amount_paid == 5900 and invoice.currency == 'usd'
    client.v1.subscriptions.cancel(subscription.id)
    print(json.dumps({'livemode': False, 'invoice_id': invoice.id, 'invoice_status': invoice.status, 'amount_paid': invoice.amount_paid, 'currency': invoice.currency, 'subscription_canceled_after_verification': True}))
