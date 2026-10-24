# Foodwagon Paystack checkout

## Paystack contract used

This integration follows Paystack's current official documentation:

- [Transactions API](https://paystack.com/docs/api/transaction/): initialize with `POST /transaction/initialize`, bearer-secret authentication, email, a unique reference, amount in the currency subunit, NGN currency, and a fully qualified callback URL. The API returns a hosted `authorization_url` and reference. Verify the reference server-to-server using `GET /transaction/verify/:reference`; the response includes status, reference, amount, currency, and transaction domain.
- [API introduction and supported currencies](https://paystack.com/docs/api/): API requests use `https://api.paystack.co`; the key selects the environment. NGN uses kobo, so ₦100 is sent as 10,000 kobo. Paystack currently documents a ₦50 (5,000-kobo) NGN transaction minimum.
- [Webhooks](https://paystack.com/docs/payments/webhooks/): `x-paystack-signature` is an HMAC-SHA512 signature over the exact raw request body, keyed by the matching secret. Foodwagon verifies it before processing, records a payload digest to deduplicate repeated deliveries, and checks the verified reference, test/live domain, NGN currency, and exact expected kobo amount before marking payment successful. Duplicate or unknown events are safely acknowledged; invalid signatures are rejected.
- [Test payments](https://paystack.com/docs/payments/test-payments/): use the official test environment and Paystack's test data. Test orders are always marked as non-fulfilment examples in Foodwagon.
- [Test and live API keys](https://support.paystack.com/en/articles/2123458) and [Test Mode and Live Mode](https://support.paystack.com/en/articles/2129922): test and live keys are separate, and Test Mode is for sandbox transactions without real money. The key stays server-side in environment/secret storage.

Foodwagon does not collect or store payment-card details. It sends an order's server-calculated NGN total to Paystack, checks that the returned checkout URL belongs to `checkout.paystack.com`, verifies callback results server-to-server, and also accepts signed webhooks. The order page does not expose customer contact or delivery-address fields.

## Checkout modes

- **Demo:** Local rehearsal only. `python manage.py seed_demo` creates editable fictional menu items and an example delivery zone clearly marked `DEMO`. The checkout requires synthetic customer data, stores an explicitly demo order, and makes no provider, notification, kitchen, or delivery call.
- **Paystack test:** Used only when `FOODWAGON_PAYMENT_MODE=test` and a server-side `PAYSTACK_TEST_SECRET_KEY` with the test-key prefix is configured. It must run on an HTTPS staging host. Use synthetic customer details and Paystack's official test payment scenarios. A successful test transaction is recorded as test-only and is never released for fulfilment.
- **Disabled:** The production default. No public checkout or order is accepted until a matching payment mode is configured.
- **Live:** Not enabled by this change. No live key was configured or used, no real payment was initiated, and no deployment was performed.

## Owner/deployment configuration

For a private HTTPS staging setup, store the test key in the deployment's secret manager and configure only:

```text
FOODWAGON_PAYMENT_MODE=test
PAYSTACK_TEST_SECRET_KEY=<test secret stored outside source control>
PAYSTACK_API_TIMEOUT_SECONDS=10
```

Do not put credentials in `.env` files committed to Git, notebooks, browser JavaScript, or logs. The staging base URL must be HTTPS and explicitly listed in Django's allowed hosts/CSRF trusted origins. Configure the Paystack webhook in the matching test environment to:

```text
https://<staging-host>/payments/paystack/webhook/
```

Paystack cannot deliver webhooks to localhost. A public endpoint should only be configured after the owner deliberately chooses and secures a staging host; this repository change does not deploy one.

## Live-mode gates

A real charge is possible only after all gates below are deliberately configured. They all remain off or incomplete in this repository's current state:

1. `FOODWAGON_PAYMENT_MODE=live`, a server-side `PAYSTACK_LIVE_SECRET_KEY`, and explicit `LIVE_ORDERING_ENABLED`, `LIVE_PAYMENTS_ENABLED`, and `FOODWAGON_LIVE_CHECKOUT_APPROVED` environment switches.
2. A non-demo Restaurant Profile in Django admin, with both profile live switches and the owner readiness confirmation set. Only a Django superuser can edit these activation switches.
3. Verified business name, support contacts, actual business/pickup address, service area, operating hours, privacy notice URL, terms URL, owner-confirmed handling/retention process, and support/fulfilment procedures.
4. Active non-demo menu category/items, real prices, and active non-demo delivery zones/fees. The owner must verify that the menu, address and fulfilment options are accurate before opening orders.
5. Public HTTPS, production PostgreSQL, valid allowed-host/CSRF configuration, secret storage, database backups, monitoring, webhook registration, and a completed end-to-end staging test.

The current owner-provided business identity, menu, prices, delivery rules/hours, pickup details, legal copy, payment account configuration, and Paystack credentials are still unconfigured. Do not enable live checkout until those details are verified and the owner authorizes production setup.

## Operational handling

Orders, item/price snapshots, live terms/privacy URL snapshots, payment attempts, and webhook audit records appear in the authenticated Django admin. Payment totals and payment status are read-only; demo/test orders cannot be marked fulfilled, and unpaid live orders cannot be released from the staff admin. A failed payment can be retried from the private order-status page only when the same environment is configured. Amount, currency, reference, test/live domain, and order state are checked before a successful payment is accepted.

The application intentionally sends no confirmation email, kitchen ticket, delivery request, or pickup notification. Those integrations, along with an owner-approved data retention and privacy process, are prerequisites for calling the service operationally live.

## Verification

The Django test suite uses mocked Paystack initialize/verify responses and synthetic webhook signatures. It tests basket and checkout behavior, idempotency, invalid signatures, mismatched amount/currency/domain, replayed submissions, and live-off gates. Tests make no external Paystack request or real charge.
