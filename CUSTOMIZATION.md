# CUSTOMIZATION.md — Making It Yours

This guide shows you how to extend and re-brand the **AI-Powered E-Commerce
System**. Every section has a copy-pasteable snippet and tells you **where** the
change goes.

You have the complete source code, so **every file is yours to edit**. There are
no restrictions on what you can change — only on what you can redistribute (see
`LICENSE.txt`).

> **Tip:** before you start experimenting, make a backup copy of the project
> folder. Then you can always compare against a working version:
> `cp -r ai_ecommerce ~/ai_ecommerce_backup`

---

## 1. Add a New Product Field

Goal: give every product a `brand`, show it on cards and on the detail page.

### 1a. The model — `store/models.py`

Inside `class Product(models.Model)`, add the field next to the other simple
fields (e.g. right after `status`):

```python
    brand = models.CharField(max_length=100, blank=True)
```

> Use `blank=True` so existing rows stay valid. If you want it mandatory, use
> `max_length=100` without `blank=True` — but then migrations will ask for a
> one-off default.

### 1b. The migration

```bash
python manage.py makemigrations store
#   -> store/migrations/0003_product_brand.py
python manage.py migrate
```

### 1c. The admin — `store/admin.py`

Make the field visible and searchable in `ProductAdmin`:

```python
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name", "brand", "category", "price", "stock",
        "status", "is_featured", "views_count", "purchase_count", "created_at",
    )
    list_filter = ("status", "is_featured", "category", "brand", "created_at")
    search_fields = ("name", "slug", "description", "brand")
    prepopulated_fields = {"slug": ("name",)}
```

### 1d. The templates

`templates/store/partials/product_card.html` — add under the `<h3>`:

```html
{% if product.brand %}<p class="brand">{{ product.brand }}</p>{% endif %}
```

`templates/store/product_detail.html` — add after the category paragraph:

```html
{% if product.brand %}<p class="brand">Brand: {{ product.brand }}</p>{% endif %}
```

### 1e. (Optional) style it — `static/css/styles.css`

```css
.brand { color: var(--muted); font-size: 0.85rem; margin: 0; }
```

**Summary of files touched:** model → migration → admin → 2 templates → CSS.
That is the standard Django rhythm for *any* new field.

---

## 2. Add a New View and URL

Goal: a **New Arrivals** page at `/new/` listing the 12 most recently added
active products, with pagination.

### 2a. The view — `store/views.py`

`Paginator`, `Product` and `Category` are already imported at the top of this
file, so you only add the function (put it near the other catalog views):

```python
@require_GET
def new_arrivals(request):
    """Show the most recently added active products."""
    products = Product.objects.filter(status="active").order_by("-created_at")
    page_obj = Paginator(products, 12).get_page(request.GET.get("page"))
    return render(request, "store/product_list.html", {
        "page_obj": page_obj,
        "categories": Category.objects.all(),
        "q": "",
        "active_category": "",
    })
```

It reuses the existing `templates/store/product_list.html`, which expects
exactly those context keys (`page_obj`, `categories`, `q`, `active_category`).

### 2b. The URL — `store/urls.py`

Add one line inside `urlpatterns`:

```python
    path("new/", views.new_arrivals, name="new_arrivals"),
```

### 2c. Link it — `templates/base.html`

In the navbar, next to the existing "Products" link:

```html
<a href="{% url 'new_arrivals' %}">New</a>
```

Visiting <http://127.0.0.1:8000/new/> now works.

### 2d. Returning JSON instead of HTML (bonus)

For a tiny API endpoint, return `JsonResponse` (already imported):

```python
@require_GET
def product_count_api(request):
    return JsonResponse({
        "success": True,
        "active_products": Product.objects.filter(status="active").count(),
    })
```

```python
    path("api/product-count/", views.product_count_api, name="product_count_api"),
```

**Pattern to remember:** `view function` → `urls.py path()` → `template (or
JSON)` → `nav link`. The same four steps add any page to this project.

---

## 3. Customize the AI Prompt

The AI behaviour lives in **`store/services.py`**. Two places control the
"personality" of the assistant.

### 3a. The system prompt (≈ lines 40–45)

```python
SYSTEM_PROMPT = (
    "You are a helpful product recommendation assistant for an e-commerce store. "
    "Recommend products the customer is likely to be interested in. "
    "Respond ONLY with valid JSON that matches the requested schema. "
    "Do not include markdown, code fences, or any extra commentary."
)
```

This sets the model's role and forbids prose around the JSON. To change the
tone, edit the strings — for example:

```python
SYSTEM_PROMPT = (
    "You are a friendly shopping assistant for a small electronics store. "
    "Sound enthusiastic but concise, and recommend at most a few products. "
    "Respond ONLY with valid JSON that matches the requested schema. "
    "Do not include markdown, code fences, or any extra commentary."
)
```

### 3b. The user prompt builder (≈ lines 340–348, `_personalized_prompt`)

```python
    return (
        f"Customer profile:\n{profile}\n\n"
        f"Catalog (choose product ids only from this list):\n{json.dumps(catalog)}\n\n"
        f"Pick {limit} products this customer would most likely buy. "
        f"Prefer relevant, in-stock items and avoid repeating items they already own. "
        f"Respond with JSON in exactly this shape: "
        f'{"recommendations":[{"product_id": 1, "reason": "short friendly reason", "score": 0.0}]} '
        f"where score is a confidence from 0.0 to 1.0."
    )
```

`_similar_prompt()` (≈ lines 351–364) does the same for "Similar Products".
Useful knobs nearby:

| Constant / line | Default | Effect |
| --- | --- | --- |
| `MAX_CANDIDATES = 40` | 40 | How many products are sent to the model (↑ = better picks, ↑ cost) |
| `MAX_REASON_LENGTH = 200` | 200 | Truncation limit for the AI's explanation |
| `temperature=0.4` (in `call_ai`) | 0.4 | Lower = more predictable, higher = more creative |
| `response_format={"type": "json_object"}` | JSON | Keeps output parseable — leave this on |

### 3c. Ideas worth trying

- Ask for a **shorter, punchier** `reason` (e.g. max 12 words).
- Add a rule like *"prefer items under $50"* to the user prompt.
- Bump `MAX_CANDIDATES` to 80 and compare the quality of the picks.
- Add a new public function in `services.py` (e.g. `get_bundle_suggestions()`)
  and call it from a view — follow the shape of `get_trending_products()`.

---

## 4. Change the CSS Theme

All styling lives in **`static/css/styles.css`**, and the colours are defined
once as CSS variables at the very top (lines 1–11):

```css
:root {
    --primary: #4f46e5;
    --primary-dark: #4338ca;
    --danger: #dc2626;
    --text: #1f2937;
    --muted: #6b7280;
    --bg: #f9fafb;
    --card: #ffffff;
    --border: #e5e7eb;
    --radius: 8px;
}
```

Change those values and the whole site follows — buttons, links, badges, the
hero gradient and focus states all reference `var(--primary)`, etc.

**Example: an emerald theme**

```css
:root {
    --primary: #059669;
    --primary-dark: #047857;
    --danger: #dc2626;
    --text: #111827;
    --muted: #6b7280;
    --bg: #f8fafc;
    --card: #ffffff;
    --border: #e2e8f0;
    --radius: 12px;
}
```

**Example: a dark theme** (also flip the text/bg/card values)

```css
:root {
    --primary: #8b5cf6;
    --primary-dark: #7c3aed;
    --danger: #f87171;
    --text: #f9fafb;
    --muted: #9ca3af;
    --bg: #0f172a;
    --card: #1e293b;
    --border: #334155;
    --radius: 8px;
}
```

Two things to keep in mind:

- The hero uses a hard-coded gradient partner (`--primary` → `#7c3aed`). If your
  new primary clashes with purple, edit `.hero` near line 49.
- The status pills (`.status-paid`, `.status-shipped`, …) are hard-coded
  pastel colours around lines 116–122 — adjust them if you go dark.

Templates also reference classes like `btn-primary`, `product-card`, `price`,
`stock`, `rec-score`; restyle those in the same file rather than editing HTML.

---

## 5. Add a New Category

No code required — do it in the admin:

1. Go to <http://127.0.0.1:8000/admin/> and log in.
2. Click **Categories → Add category**.
3. Fill in:
   - **Name** — e.g. `Home & Kitchen`
   - **Slug** — leave blank; it is generated automatically. (If you type one,
     it must be unique.)
   - **Description** — optional.
4. **Save**.
5. Now open **Products → Add product**, and pick your new category in the
   **Category** dropdown.

The new category immediately appears in the catalog filter dropdown on
`/products/` and is reachable at `/categories/<slug>/`.

**Prefer the shell?** The same thing in one line:

```bash
python manage.py shell -c "from store.models import Category; \
Category.objects.get_or_create(name='Home & Kitchen', \
defaults={'description': 'Kitchen and home essentials'})"
```

**Renaming a category:** edit it in the admin. The slug stays stable, so
existing URLs keep working. **Deleting** a category does not delete its
products — `Product.category` uses `on_delete=models.SET_NULL`, so those
products simply become "uncategorised".

---

## 6. Change the AI Provider / Model (and Other AI Settings)

These values are read from the environment by `config/settings.py` at startup.
`AI_PROVIDER` selects the active provider and the unified `AI_*` values below it
are the ones the code actually reads (`store/services.py` never looks at the
provider-specific settings directly):

```python
# AI provider selection (FR-6)
AI_PROVIDER = os.getenv('AI_PROVIDER', 'deepseek').lower()

# DeepSeek (used when AI_PROVIDER == 'deepseek')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DEEPSEEK_BASE_URL = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
DEEPSEEK_TIMEOUT = int(os.getenv('DEEPSEEK_TIMEOUT', '20'))

# Google Gemini (used when AI_PROVIDER == 'gemini')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_BASE_URL = os.getenv('GEMINI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta/openai/')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
GEMINI_TIMEOUT = int(os.getenv('GEMINI_TIMEOUT', '20'))

if AI_PROVIDER == 'gemini':
    AI_API_KEY, AI_BASE_URL = GEMINI_API_KEY, GEMINI_BASE_URL
    AI_MODEL, AI_TIMEOUT = GEMINI_MODEL, GEMINI_TIMEOUT
else:
    AI_API_KEY, AI_BASE_URL = DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL
    AI_MODEL, AI_TIMEOUT = DEEPSEEK_MODEL, DEEPSEEK_TIMEOUT

RECOMMENDATION_TTL_SECONDS = int(os.getenv('RECOMMENDATION_TTL_SECONDS', '21600'))
```

### The easy way — `.env`

Edit `.env` in the project root and **restart the server**:

```dotenv
AI_PROVIDER=deepseek
DEEPSEEK_MODEL=deepseek-reasoner
DEEPSEEK_TIMEOUT=30
RECOMMENDATION_TTL_SECONDS=3600
```

| Setting | What it does | Notes |
| --- | --- | --- |
| `AI_PROVIDER` | Which provider the engine uses | `deepseek` (default) or `gemini` |
| `DEEPSEEK_MODEL` | Which DeepSeek model answers | `deepseek-chat` (fast, default) or `deepseek-reasoner` (slower, deeper) |
| `GEMINI_MODEL` | Which Gemini model answers | `gemini-2.0-flash` (free tier) |
| `DEEPSEEK_TIMEOUT` / `GEMINI_TIMEOUT` | Per-request timeout (seconds) | Raise to `30` on slow connections |
| `RECOMMENDATION_TTL_SECONDS` | How long personalized picks are cached | `3600` = refresh hourly; `0` = always re-ask the AI |
| `DEEPSEEK_BASE_URL` / `GEMINI_BASE_URL` | API endpoint | Only change for a compatible proxy/self-host |
| `DEEPSEEK_API_KEY` / `GEMINI_API_KEY` | Your secret keys | Leave the active one empty to run in no-AI fallback mode |

> DeepSeek currently routes `deepseek-chat` to `deepseek-flash` server-side.
> This is transparent to the application.

### The hard way — `config/settings.py`

You can also change the **default** value (the second argument of `os.getenv`)
directly in `config/settings.py`. Note that `.env` always wins at runtime, so
prefer editing `.env` unless you want a different fallback.

**Verifying your change:** load the homepage while logged in, watch the
"Recommended for You" section, and check the server log for
`deepseek call failed ...` / `gemini call failed ...` lines (the prefix is
whatever `AI_PROVIDER` is set to). If you see several, the model name may be
invalid for your API key — try `deepseek-chat` or `gemini-2.0-flash`.

---

## 7. Reset the Database

⚠️ **Destructive.** This deletes every product, order, cart and user. Back up
first if the data matters.

### Option A — drop and recreate (cleanest)

```bash
# Stop the dev server first (Ctrl+C), then:
dropdb -h 127.0.0.1 -U ecommerce_user ecommerce_db
createdb -h 127.0.0.1 -U ecommerce_user ecommerce_db

python manage.py migrate
python manage.py createsuperuser
```

On PostgreSQL 15+ re-grant schema rights after recreating:

```sql
\c ecommerce_db
GRANT ALL ON SCHEMA public TO ecommerce_user;
```

### Option B — wipe the schema from psql

```sql
\c ecommerce_db
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO ecommerce_user;
```

then `python manage.py migrate` again.

### Option C — flush data but keep the tables

```bash
python manage.py flush          # deletes all rows, keeps the schema
python manage.py createsuperuser
```

> `flush` does **not** touch the migration history — it clears application data
> only, so the schema stays intact.

### Migrations-only reset (when a migration is broken)

```bash
# Roll the app back to zero, then re-apply
python manage.py migrate store zero
python manage.py migrate
```

If you changed a model and want to start its migration history from scratch:
delete the files in `store/migrations/` **except** `__init__.py`, then
`makemigrations store && migrate`.

---

## 8. Quick Reference

| I want to… | Where |
| --- | --- |
| Re-brand colours | `static/css/styles.css` `:root` variables (§ 4) |
| Reword the UI | `templates/**/*.html` |
| Add a product / category | Django admin `/admin/` (§ 5) |
| Switch AI model / timeout / cache | `.env` (§ 6) |
| Change the AI prompt | `store/services.py` (§ 3) |
| Add a product field | `models.py` + migration + `admin.py` + templates (§ 1) |
| Add a page | `views.py` + `urls.py` + template (§ 2) |
| Reset all data | `dropdb` / `flush` (§ 7) |

**Where to go next:** `GUIDE.md` for the architecture and file-by-file tour,
`docs/API.md` for every endpoint, `docs/erd.png` for the data model, and
`README.md` for the full technical reference.



