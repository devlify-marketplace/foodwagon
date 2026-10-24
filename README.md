# Foodwagon

This repository contains the existing Gulp-based design theme (`public/` and `src/`) and a Django server-rendered storefront/admin project. The Django work provides an owner-editable profile, menu catalogue, service configuration models, staff administration, SEO endpoints, and a redesigned green-and-white interface.

## Local Django setup

Python 3.10+ is recommended. From the repository root:

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

The public homepage is `http://127.0.0.1:8000/`; staff administration is `/admin/`, and the staff dashboard is `/dashboard/`. In local development, static files are served from the existing `public/assets/` tree. The Gulp theme workflow remains `npm install && npx gulp` (or `npm run build` where defined).

## Current operating boundary

The setup command creates only an editable Foodwagon profile with the confirmed public project contact details: `sadiq@devlify.com.ng` and `+2349034303594`. It intentionally does **not** seed menu items, prices, address, service areas, delivery fees, pickup location, or opening hours. Populate those fields only with owner-verified information in Django admin. Synthetic sample content, if created for private testing, must remain clearly marked `is_demo` and must not be represented as a live offering.

Online cart submission, ordering, payment, email fulfilment, and delivery are not implemented. The public order endpoints return HTTP 503 and do not accept/store customer data. The profile's live-order and live-payment flags default off; changing a flag does not implement the missing integration. Do not enable live service until business terms, a payment provider, fulfilment flows, security controls, and end-to-end tests have been added and reviewed.

## Production configuration

Set a high-entropy `DJANGO_SECRET_KEY`, explicit `DJANGO_ALLOWED_HOSTS`, and `DJANGO_CSRF_TRUSTED_ORIGINS` as appropriate. `DJANGO_DEBUG` defaults to false. HTTPS redirect, secure session/CSRF cookies, HSTS, and content-type/clickjacking protections are enabled for non-debug operation. Configure `DJANGO_TRUST_X_FORWARDED_PROTO=true` only behind a trusted TLS-terminating proxy that overwrites the forwarded-proto header. Set `DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME` for PostgreSQL; the local default is SQLite. Keep credentials in environment/secret storage, never in source control.

Before any real launch, configure and verify the actual public business identity, menu, pricing/tax, pickup and delivery rules, hours, privacy/legal copy, customer support, payment and fulfilment integrations, production database/backups, monitoring, and operational procedures. No deployment is performed by this project setup.

## SEO and administration

Public metadata, canonical/Open Graph tags, a `WebSite` JSON-LD record, `robots.txt`, and `sitemap.xml` are included. The protected Django admin manages restaurant profile, menu categories/items, operating hours, delivery-zone configuration, and historical demo records. Staff-only dashboard and admin routes require authentication.

## Tests

```sh
python manage.py check
python manage.py test
python manage.py check --deploy
```
