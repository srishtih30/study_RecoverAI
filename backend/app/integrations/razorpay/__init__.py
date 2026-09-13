"""
Razorpay integration boundary.

Mandatory rule: this package is the ONLY place the `razorpay` SDK (or raw
Razorpay HTTP calls) may be imported. Nothing else in the backend should
`import razorpay` or hardcode a Razorpay API URL — go through
`app.integrations.razorpay.client.get_razorpay_client()` instead.

Modules:
  * webhook_verifier.py — signature verification
  * event_normalizer.py — raw Razorpay payload -> app.domain.events.NormalizedEvent
  * client.py            — outbound Razorpay API calls (retry charge, payment link, ...)
"""
