# Channel Pro Manager Django API

Production-oriented Django 5 REST backend with PostgreSQL, Redis, Celery, JWT authentication, dynamic database-backed RBAC, audit logging, OpenAPI, Docker, and an Nginx/Gunicorn production overlay. The image uses Python 3.13.

## Architecture

```text
backend/config/                 split settings, URLs, Celery, ASGI/WSGI
backend/apps/users/             email-based custom user and auth API
backend/apps/customers/         tenants, owners, and customer memberships
backend/apps/staff/             tenant-scoped staff management
backend/apps/companies/         customer-owned companies and logo uploads
backend/apps/modules/           dynamic application modules and seed command
backend/apps/permissions/       module-scoped permission codenames
backend/apps/roles/             roles and explicit role-permission assignments
backend/apps/orders/            example business module using shared RBAC
backend/apps/core/              permissions, audit, pagination, errors, tasks, tests
docker/django/                  Python image and PostgreSQL wait entrypoint
docker/nginx/                   production reverse proxy
requirements/                   base/development/production dependency sets
```

The authorization path is `User -> CustomerMembership -> Customer -> Role -> RolePermission -> Permission -> Module`. Platform administrators use Django's `is_superuser` and have no artificial RBAC role. Every customer has one owner membership; owners have full access to their own tenant without individual permission rows. Staff have one tenant role and share all tenant data, while permissions control their allowed actions. Modules and permission codenames are database records, and the shared permission class maps REST actions to `view/create/update/delete`.

Tenant querysets derive the customer from the authenticated membership and never trust a frontend `customer_id`. Cross-tenant object IDs resolve as `404`. Important records use deactivation (`is_active`, `deleted_at`) rather than physical deletion, active owner memberships cannot be deleted directly, and customer/staff/role writes use atomic transactions.

## Development setup

1. Copy the sample configuration and replace every placeholder:

   ```bash
   cp .env.example .env
   ```

2. Build, start, migrate, seed, and create an administrator:

   ```bash
   docker compose build
   docker compose up -d
   docker compose exec web python manage.py migrate
   docker compose exec web python manage.py seed_permissions
   docker compose exec web python manage.py createsuperuser
   ```

3. Open Swagger at <http://localhost:8000/api/docs/>. Enter an access token using `Bearer <token>`.

Development mounts `backend/` into all Python services, so source changes are immediately visible. PostgreSQL and Redis have health checks; the Django entrypoint also waits for PostgreSQL.

Useful commands:

```bash
docker compose down
docker compose logs -f web
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_permissions
docker compose exec web python manage.py shell
docker compose exec web python manage.py test
```

The example Celery task can be queued in a shell with:

```python
from apps.core.tasks import example_task
example_task.delay()
```

The compose stack runs `web`, `db`, `redis`, `celery_worker`, and `celery_beat`.

## Authentication and RBAC workflow

Obtain tokens with `POST /api/v1/auth/login/` using `email` and `password`. Refresh at `/auth/token/refresh/`; logout accepts `{"refresh": "..."}` and blacklists the token. `/auth/me/` returns the account, roles, and flattened effective permissions. `/auth/permissions/` returns the frontend-friendly module/action matrix.

Customer management is restricted to platform superusers. Creating a customer atomically provisions the owner User and owner CustomerMembership. The owner can then create tenant-scoped roles by posting permission codenames:

```json
{
  "name": "Order Manager",
  "permissions": ["orders.view", "orders.create", "orders.update"]
}
```

The slug is generated from the name when omitted. Creating a customer also provisions its email-based login account; the password is write-only and never returned. Assign active roles atomically:

```json
{
  "first_name": "John",
  "last_name": "Smith",
  "email": "john@example.com",
  "password": "use-a-strong-unique-password"
}
```

Owners create staff inside their current tenant:

```json
{
  "first_name": "Jane",
  "last_name": "Operator",
  "email": "jane@example.com",
  "password": "use-a-strong-unique-password",
  "role_id": 3
}
```

## Endpoints

| Area | Endpoints |
|---|---|
| Authentication | `POST auth/login/`, `POST auth/token/refresh/`, `POST auth/logout/`, `GET auth/me/`, `GET auth/permissions/` |
| Modules | CRUD `modules/`, plus `GET modules/permission-matrix/` |
| Permissions | Grouped `GET permissions/`; superadmin mutation endpoints |
| Roles | Tenant-scoped CRUD `roles/` with permission codenames |
| Customers | CRUD `customers/` |
| Staff | Tenant-scoped CRUD `staff/` |
| Companies | Customer-owned CRUD `companies/` with a single `name` and multipart logo upload |
| Orders | CRUD `orders/` |
| OpenAPI | `GET /api/schema/`, `GET /api/docs/` |

All application endpoints above are under `/api/v1/`. Customers support `search`, exact `company`, `role`, `is_active`, pagination, and ordering by `created_at`, `first_name`, `last_name`, or `company`. Orders demonstrate `orders.view/create/update/delete` exactly.

The idempotent seed creates Dashboard, Customers, Companies, Orders, Products, Inventory, Warehouses, Shipments, Reports, Marketplaces, Staff, Roles, Settings, and Integrations with module-appropriate permissions such as `orders.cancel`, `inventory.adjust`, `reports.export`, and `marketplaces.manage`.

## Tests

Inside Docker:

```bash
docker compose exec web python manage.py test
```

For a quick local SQLite test (not a production configuration):

```bash
USE_SQLITE=True ../.venv/bin/python manage.py test
```

Run the latter from `backend/`. Tests cover JWT, owner creation, customer/staff authentication, tenant owner bypass, staff permission enforcement, shared tenant records, cross-tenant URL manipulation, foreign-role rejection, self-escalation prevention, superuser bypass, soft deletion, and idempotent seeding.

## Production

Set strong unique secrets, `DEBUG=False`, real host/origin lists, database credentials, HTTPS, and `DJANGO_SETTINGS_MODULE=config.settings.production`. Then run:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py migrate
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
```

The overlay switches Django to Gunicorn, adds Nginx, removes the direct web port, and enables secure cookies, proxy SSL handling, HSTS, and production settings. Back up PostgreSQL and uploaded media, terminate TLS at the proxy/load balancer, rotate secrets, restrict network exposure, and monitor web/Celery/Redis/PostgreSQL in the deployment platform.
# Amazon order import

After configuring an Amazon channel, enabling at least one marketplace, and applying migrations, orders can be synchronized with:

```bash
python backend/manage.py migrate
python backend/manage.py sync_orders <channel_id>
```

The authenticated API equivalent is `POST /api/v1/channels/<channel_id>/sync-orders/`. Imports are incremental after the first 14-day download, follow Amazon pagination, and upsert both orders and order items. The Celery task `apps.orders.tasks.sync_channel_orders` is available for scheduled/background execution.

Amazon calls use `python-amazon-sp-api`, currently pinned to the compatible 2.1 release series. Provider-specific calls stay behind `apps.orders.services.amazon`, allowing Orders, Reports, Feeds, Listings, Finances, and other SP-API clients to be added without leaking SDK details into views or models.

## WooCommerce CSV product import

Like the legacy Laravel `ImportWooProducts` job, this imports a WooCommerce CSV export (not a live Woo REST API sync). Send a multipart request to `POST /api/v1/channels/<woo_channel_id>/woo-product-import/` with `file`, `warehouse_id`, and optional `language_code` (default `en`). The response contains an import ID; poll `GET /api/v1/channels/<woo_channel_id>/woo-product-import/<import_id>/` for counts and completion status. A Celery worker must be running to process queued imports.

The importer recognizes the Italian WooCommerce export headings used by the Laravel job. It upserts products, translations, variations, attributes, prices, dimensions, and warehouse stock by SKU. Remote image fetching is not included yet; source CSV files are retained for diagnostics and retries, so configure media-file retention and access controls accordingly.

Amazon seller credentials can also be configured manually for a particular channel:

```http
PUT /api/v1/channels/<channel_id>/amazon-credentials/
Content-Type: application/json

{
  "seller_id": "A1EXAMPLESELLER",
  "refresh_token": "Atzr|..."
}
```

Use `PATCH` to rotate individual fields. Tokens are encrypted at rest and are never included in the response. The customer's shared LWA client ID, LWA client secret, and SP-API application ID remain under `/api/v1/channel-settings/`.
