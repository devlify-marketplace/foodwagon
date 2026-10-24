# Foodwagon

Foodwagon combines its existing Gulp/Pug theme (`public/` and `src/`) with a Django server-rendered storefront and staff tools. The Django app provides an owner-editable profile, menu, delivery-zone settings, session basket, validated checkout, token-protected order status, Paystack integration, staff dashboard, SEO endpoints, and a green-and-white responsive interface.

## Local Django setup

Python 3.10+ is recommended. The project targets the [Django 5.2 LTS series](https://docs.djangoproject.com/en/5.2/releases/5.2/). From the repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export DJANGO_DEBUG=true
export DJANGO_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
python manage.py migrate
python manage.py seed_demo
python manage.py createsuperuser
python manage.py runserver
```

The public homepage is `http://127.0.0.1:8000/`; Django admin is `/admin/`, and the staff dashboard is `/dashboard/`. The local seed command is explicitly demo-only and idempotent. The Gulp theme workflow remains `npm install && npx gulp` (or `npm run build` where defined).

## Order and payment modes

`FOODWAGON_PAYMENT_MODE` defaults to `demo` when Django debug mode is on and `disabled` otherwise. Demo mode creates no Paystack call, real charge, notification, kitchen fulfilment, or delivery request. Seeded menu items and delivery areas are fictional, editable, and marked `DEMO`; use synthetic customer details only.

Paystack test checkout is available only when a server-side `PAYSTACK_TEST_SECRET_KEY` is configured in test mode. Use it only on an HTTPS staging environment and only with Paystack's official test details. Test payments do not count as real payments and the application never releases test/demo orders for fulfilment.

Production remains fail-closed until the owner supplies verified business identity, real menu/prices, service and delivery/pickup details, opening hours, privacy/terms, a data-handling/retention process, support/fulfilment operations, and Paystack account credentials/configuration. Live payment/order switches default off. No Paystack secret, actual credential, real payment, or deployment is included in this repository update. See [PAYSTACK_INTEGRATION.md](PAYSTACK_INTEGRATION.md) for the current implementation contracts and owner checklist.

## Production configuration

Set a high-entropy `DJANGO_SECRET_KEY`, explicit `DJANGO_ALLOWED_HOSTS`, and appropriate `DJANGO_CSRF_TRUSTED_ORIGINS`. `DJANGO_DEBUG` defaults to false. HTTPS redirect, secure session/CSRF cookies, HSTS for the current host, and content-type/clickjacking protections are enabled for non-debug operation; HSTS coverage for subdomains (`DJANGO_HSTS_INCLUDE_SUBDOMAINS=true`) and browser preload (`DJANGO_HSTS_PRELOAD=true`, which also requires subdomains) are opt-in and should only be enabled after the owner reviews the chosen domain and other services beneath it. Configure `DJANGO_TRUST_X_FORWARDED_PROTO=true` only behind a trusted TLS-terminating proxy that overwrites the forwarded-proto header. Set `DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME` and `DB_SSLMODE=require` for PostgreSQL (use `verify-full` plus the provider's CA configuration where available); SQLite is for local development. Keep credentials in environment/secret storage, never in source control.

Until the production domain is confirmed, Django's `check --deploy` will report `security.W005` and `security.W021` because HSTS is not extended to subdomains or browser preload. This is intentional; both flags should be enabled only after reviewing the domain's subdomain exposure. The rest of the deployment check passes with disposable production settings.

Private basket, checkout, dashboard, and order-status URLs are `noindex`; the sitemap remains empty and robots disallow crawling until owner-verified live settings are active. Public order mutations are POST/CSRF protected. Order totals are recalculated on the server, item prices and payment records are stored as snapshots, callbacks are verified server-to-server, and webhook payloads are signature-checked and deduplicated.

## SEO and administration

Public metadata, canonical/Open Graph tags, a `WebSite` JSON-LD record, `robots.txt`, and `sitemap.xml` are included. SEO indexing stays blocked while the site is demo/test/disabled. Django admin manages the restaurant profile, menu categories/items, operating hours, delivery zones, orders, immutable payment attempts, and webhook audit records. Only a Django superuser can change the live-readiness switches; payment status/amounts are read-only, and demo/test or unpaid orders cannot be marked fulfilled. Staff dashboard and admin routes require authentication.

## Tests

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py check --deploy
```

The tests mock Paystack requests and signed webhook events. They do not call Paystack or create a real charge. `check --deploy` also expects a production-like environment with real deployment configuration; do not silence missing required settings by adding credentials to the repository.
