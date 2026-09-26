# GUIDE.md — Student Learning Guide

Welcome! This guide explains how the **AI-Powered E-Commerce System** is put
together and how to get it running on your machine. It is written for a learner:
read it top to bottom once, then use it as a reference.

Everything mentioned here is **plain, readable source code**. Whenever you see a
file name, open it and follow along — that is the fastest way to learn this
codebase.

---

## 1. What This Application Is

A complete e-commerce web app built with **Django 6.1.1** on **PostgreSQL**,
with the front end written in **HTML5 + CSS3 + Vanilla JavaScript** (no React,
Angular or Vue), and an **AI recommendation engine** powered by the **DeepSeek
or Google Gemini API**.

It covers six functional areas:

| Ref | Feature | Where |
| --- | --- | --- |
| FR-1 | Authentication (register / login / logout) | `store/views.py` |
| FR-2 | Product management via Django admin | `store/admin.py`, `/admin/` |
| FR-3 | Browsing, search, category filter, product detail | `store/views.py` |
| FR-4 | Cart with a JSON API + Vanilla-JS UI | `store/views.py`, `static/js/cart.js` |
| FR-5 | Orders / atomic checkout / history | `store/views.py` |
| FR-6 | AI recommendations (personalized, similar, trending) | `store/services.py` |

---

## 2. Prerequisites

- **Python 3.12+**
- **PostgreSQL 14+** running locally
- **pip / venv** (bundled with Python)
- An **AI API key** *(optional)*: **Gemini** (free) or **DeepSeek** (paid).
  See `SETUP.md` §5 — without a key the store still works; only the AI features
  fall back to deterministic suggestions.

---

## 3. Architecture — How a Request Flows

```
                    BROWSER  (HTML + CSS + Vanilla JS)
                       |                       ^
              HTTP request / fetch()      HTML or JSON
                       v                       |
              +------------------+             |
              | config/urls.py   |  root URLconf: /admin/ + include(store.urls)
              +------------------+
                       |
                       v
              +------------------+      URL pattern -> view function
              | store/urls.py    |      (e.g. product_detail, cart_api_add)
              +------------------+
                       |
                       v
              +--------------------------------------------------+
              | store/views.py   -- the controller layer          |
              |  * reads request / form data                      |
              |  * talks to the ORM (store/models.py)             |
              |  * calls the AI engine (store/services.py)        |
              |  * renders templates/  OR  returns JsonResponse   |
              +--------------------------------------------------+
                 |                 |                    |
                 v                 v                    v
        +----------------+  +-----------------+  +---------------------+
        | store/models   |  | store/services  |  | templates/ +        |
        | ORM -> Postgres|  | DeepSeek AI     |  | static/ (render)    |
        +----------------+  +-----------------+  +---------------------+
                 |                 |
                 v                 v
          PostgreSQL DB      DeepSeek API (HTTPS)
```

**Request lifecycle (example: viewing one product)**

1. The browser requests `/products/<slug>/`.
2. `config/urls.py` delegates to `store/urls.py`, which matches
   `path("products/<slug:slug>/", views.product_detail, name="product_detail")`.
3. `store/views.py :: product_detail()` loads the product from PostgreSQL via
   the ORM, increments `views_count`, and records a `UserActivity` row
   (`activity_type="view"`).
4. It asks `store/services.py :: get_similar_products()` for AI-ranked
   "Similar Products". If DeepSeek is unreachable, the service silently falls
   back to deterministic same-category results.
5. The view renders `templates/store/product_detail.html` with a context dict.
6. `store/context_processors.py :: cart_context()` adds `cart_count` to every
   template, so the navbar badge is always correct.

**Request lifecycle (example: add to cart — no page reload)**

1. `static/js/cart.js` sends `fetch("/cart/api/add/", {method:"POST", ...})`
   with the CSRF token.
2. `store/views.py :: cart_api_add()` validates stock/quantity, updates the
   `CartItem`, and returns JSON (`{"success": true, "cart": {...}}`).
3. JavaScript re-renders the badge and totals from that JSON — the page never
   reloads.

---

## 4. Project Structure Explained

```
ai_ecommerce/
├── manage.py                  # Django's command-line entry point
├── requirements.txt           # runtime dependencies
├── requirements-dev.txt       # test-only dependencies (pytest, Playwright)
├── .env.example               # template for your local .env (copy it!)
├── README.md                  # full technical documentation
├── README_BUYER.md            # license + getting started (for you)
├── GUIDE.md                   # <-- you are here
├── CUSTOMIZATION.md           # how to modify the project
├── LICENSE.txt                # license terms (please read)
├── config/                    # PROJECT configuration (settings & root URLs)
│   ├── settings.py            #   DB, static/media, DeepSeek keys, INSTALLED_APPS
│   ├── urls.py                #   root URLconf  (/admin/  +  store.urls)
│   ├── wsgi.py / asgi.py      #   server entry points
│   └── __init__.py
├── store/                     # THE APPLICATION (all features live here)
│   ├── models.py              #   Category, Product, Cart, CartItem, Order,
│   │                          #   OrderItem, UserActivity, Recommendation
│   ├── views.py               #   every view / JSON endpoint (FR-1 -> FR-6)
│   ├── services.py            #   FR-6 AI engine (DeepSeek) <- the interesting bit
│   ├── forms.py               #   RegisterForm, CheckoutForm
│   ├── urls.py                #   app URL routes
│   ├── admin.py               #   admin configuration (FR-2, FR-5)
│   ├── context_processors.py  #   injects cart_count into all templates
│   ├── migrations/            #   database schema history
│   └── tests.py               #   Django test placeholder
├── templates/                 # server-rendered HTML
│   ├── base.html
│   ├── accounts/              #   login.html, register.html
│   └── store/                 #   home, product_list, product_detail, cart,
│       └── partials/          #   checkout, order_*, recommendations + partials
├── static/                    # front-end assets
│   ├── css/styles.css         #   all styling (uses CSS variables)
│   ├── js/main.js             #   small UI helpers
│   ├── js/cart.js             #   cart JSON API client (Vanilla JS)
│   └── img/placeholder.svg
├── media/                     # user-uploaded product images (created at runtime)
└── docs/
    ├── API.md                 # every HTTP endpoint, documented
    └── erd.png                # entity-relationship diagram
```

**`config/` vs `store/` — the mental model**

- **`config/`** is the *project*: global settings and the root URL table. You
  rarely touch it except to change settings.
- **`store/`** is the *application*: models (data), views (behaviour), URLs
  (routing), admin (back office), and services (the AI engine).

---

## 5. Where the AI Logic Lives — `store/services.py`

> The AI engine supports both **DeepSeek** and **Gemini** transparently. Which one
> is used is controlled by `AI_PROVIDER` in `.env`. Function names below
> refer to the generic AI call — see `call_ai()` in `store/services.py`.

This is the heart of **FR-6**. Read it in this order:

| Part | What it does |
| --- | --- |
| `AI_PROVIDER` + `AI_*` settings | `config/settings.py` reads `AI_PROVIDER` (`deepseek` or `gemini`) and exposes one unified `AI_API_KEY` / `AI_BASE_URL` / `AI_MODEL` / `AI_TIMEOUT`, so the rest of the code never cares which provider is active. |
| `SYSTEM_PROMPT` | Tells the model it is a product-recommendation assistant that must reply with **JSON only**. |
| `_get_client()` | Lazily builds the AI client (DeepSeek or Gemini, both OpenAI-compatible). Returns `None` (and logs a warning) if there is no API key or the `openai` SDK is missing. |
| `build_user_context(user)` | Aggregates the user's recent `UserActivity` rows (views, searches, cart adds) and past `OrderItem` rows into `top_categories`, `recently_viewed`, `searched`, `cart`, `purchased`. |
| `_candidate_products_for_user()` | Builds the candidate pool: active + in-stock products, excluding items already bought, ranked by category interest / sales / views. |
| `_candidate_products_similar(anchor)` | Candidate pool for "similar to this product": same category first, then nearby price, then popular fill. |
| `_serialize_catalog(products)` | Turns products into a compact JSON catalog (`id, name, category, price, description[:120]`) to keep the prompt small and cheap. |
| `_personalized_prompt()` / `_similar_prompt()` | Format the user profile + catalog + a strict output schema into the user prompt. |
| `call_ai(system, user)` | Calls the active provider (DeepSeek or Gemini) with `temperature=0.4` and `response_format={"type": "json_object"}`; returns parsed JSON or `None` on **any** failure. |
| `parse_recommendations(data)` | Validates the model's JSON: keeps only known product ids, truncates reasons to 200 chars, clamps `score` to 0.0–1.0. |
| `persist_recommendations()` | Saves results to the `Recommendation` table (unique per user + product + source). |
| `get_trending_products()` | Deterministic ranking by `purchase_count`, then `views_count` — **no AI**. |
| `get_personalized_recommendations(user)` | Returns cached rows while fresh (< `RECOMMENDATION_TTL_SECONDS`, default 6 h); otherwise calls the AI, persists, and returns `(results, used_fallback)`. |
| `get_similar_products(anchor)` | AI-ranked similar items for the product detail page. |

**The key design idea: fail soft.** If the key is missing, the network times
out, or the model returns garbage, `call_ai()` returns `None`, and the
caller returns deterministic results instead of raising an error. The shop never
breaks because of the AI.

`CUSTOMIZATION.md` § 3 shows the exact lines to edit if you want to change the
prompts yourself.

---

## 6. Setup and Run

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create the PostgreSQL database and role (once)
sudo -u postgres psql
#   inside psql:
#     CREATE DATABASE ecommerce_db;
#     CREATE USER ecommerce_user WITH PASSWORD 'ecommerce_pass';
#     GRANT ALL PRIVILEGES ON DATABASE ecommerce_db TO ecommerce_user;
#     \c ecommerce_db
#     GRANT ALL ON SCHEMA public TO ecommerce_user;
#     ALTER SCHEMA public OWNER TO ecommerce_user;
#     \q

# 4. Create your .env (never commit it)
cp .env.example .env
#   then edit .env: DJANGO_SECRET_KEY, DB_PASSWORD, AI_PROVIDER, and the
#   matching API key (DEEPSEEK_API_KEY or GEMINI_API_KEY) ...

# 5. Apply migrations (creates all tables)
python manage.py migrate

# 6. Create an admin account
python manage.py createsuperuser

# 7. Run the development server
python manage.py runserver
```

Then open:

- Storefront → <http://127.0.0.1:8000/>
- Admin → <http://127.0.0.1:8000/admin/>

---

## 7. Seeding Test Data

The fastest way to get something on screen is the Django shell. This creates two
categories and four products (two featured):

```bash
python manage.py shell
```

```python
from decimal import Decimal
from store.models import Category, Product

electronics, _ = Category.objects.get_or_create(
    name="Electronics", defaults={"description": "Gadgets and devices"})
books, _ = Category.objects.get_or_create(
    name="Books", defaults={"description": "Printed and digital books"})

products = [
    ("Wireless Mouse", electronics, "29.99", 25, True,
     "Ergonomic 2.4 GHz wireless mouse with silent clicks."),
    ("Mechanical Keyboard", electronics, "89.99", 12, True,
     "Hot-swappable RGB mechanical keyboard, blue switches."),
    ("USB-C Hub", electronics, "39.50", 30, False,
     "7-in-1 hub: HDMI, USB 3.0, SD card reader and power delivery."),
    ("Django for Beginners", books, "24.00", 40, False,
     "A friendly introduction to building web apps with Django."),
]

for name, category, price, stock, featured, description in products:
    Product.objects.get_or_create(
        name=name,
        defaults={
            "category": category,
            "price": Decimal(price),
            "stock": stock,
            "is_featured": featured,
            "status": "active",
            "description": description,
        },
    )

print("Seeded", Product.objects.count(), "products in",
      Category.objects.count(), "categories")
```

Or save the block as `seed.py` (without the `print`) and run it
non-interactively:

```bash
python manage.py shell -c "$(cat seed.py)"
```

Slugs are generated automatically by `unique_slugify()` in `store/models.py`, so
you never set them by hand. You can also add data through `/admin/` — see
`CUSTOMIZATION.md` § 5.

---

## 8. Common Troubleshooting

### Database connection errors

```
django.db.utils.OperationalError: connection to server at "127.0.0.1", port 5432 failed
```

- Is PostgreSQL running? `sudo systemctl status postgresql`
- Do the `DB_*` values in `.env` match a real role and database?
  `psql -h 127.0.0.1 -U ecommerce_user -d ecommerce_db -c "SELECT 1;"`
- On PostgreSQL 15+ grant schema rights (see § 6, step 3).
- `permission denied for schema public` →
  `GRANT ALL ON SCHEMA public TO ecommerce_user;`

### AI errors (DeepSeek or Gemini)

| Symptom | Cause | Fix |
| --- | --- | --- |
| Recommendations show without AI reasons | The active API key is empty → fallback mode | Set `DEEPSEEK_API_KEY` or `GEMINI_API_KEY` (whichever matches `AI_PROVIDER`) in `.env`, restart the server |
| `deepseek call failed (AuthenticationError)` / `gemini call failed (AuthenticationError)` in logs | Bad/expired key | Re-issue it at platform.deepseek.com or aistudio.google.com |
| `deepseek call failed (APITimeoutError)` / `gemini call failed (APITimeoutError)` | Slow network | Raise `DEEPSEEK_TIMEOUT` / `GEMINI_TIMEOUT` in `.env` (e.g. `30`) |
| `deepseek returned invalid JSON` / `gemini returned invalid JSON` | Model replied with non-JSON | Transient; the app falls back automatically |

The AI is **optional** — the store, cart and orders work entirely without it.

### Migration problems

- `You have N unapplied migrations` → `python manage.py migrate`
- `no such table: store_product` → you forgot `migrate`
- Model changed but "No changes detected" → save `models.py` and confirm
  `store` is in `INSTALLED_APPS`
- Start over (destructive!) → see `CUSTOMIZATION.md` § 7

### Static files look broken

`STATIC_URL = 'static/'` is served automatically while `DEBUG=True`. With
`DEBUG=False`, run `python manage.py collectstatic`.

### Port already in use

```bash
python manage.py runserver 8001
```

### `ModuleNotFoundError` / import errors

This is almost always an environment problem, not a code problem:

- Is your virtual environment activated? (`source venv/bin/activate`)
- Did you install the dependencies? (`pip install -r requirements.txt`)
- Are you running commands from the folder that contains `manage.py`?
- Did you add a new app to `INSTALLED_APPS` in `config/settings.py`?

---

## 9. Where To Go Next

1. Open `CUSTOMIZATION.md` and try the recipes (add a field, add a page,
   re-theme the CSS, add a category).
2. Browse `docs/API.md` for every endpoint and `docs/erd.png` for the data model.
3. Read `README.md` for the complete technical reference.
4. Log in to `/admin/` and watch `UserActivity` and `Recommendation` rows appear
   as you use the store — then re-read `store/services.py` with that data in
   mind.

Happy learning!



