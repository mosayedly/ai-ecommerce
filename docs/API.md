# API Documentation — AI-Powered E-Commerce System

**Version:** 1.0 · **Framework:** Django 6.1.1 · **Base URL:** `http://127.0.0.1:8000`

The project exposes two kinds of endpoints:

- **HTML endpoints** — server-rendered Django templates, intended for the browser.
- **JSON endpoints** — action-based APIs consumed by Vanilla JavaScript (`fetch`) or any HTTP client.

The complete URL configuration lives in `config/urls.py` (project) and `store/urls.py` (application).
Entity/relationship details are in the ER diagram: [`docs/erd.png`](erd.png) / [`docs/erd.dot`](erd.dot).

---

## Conventions

### Authentication

The application uses Django **session authentication** (login sets a `sessionid` cookie).

| Situation | Behaviour |
| --- | --- |
| Anonymous request to a login-required endpoint | `302 Found` → `/accounts/login/?next=<original-path>` |
| Login | `POST /accounts/login/` |
| Logout | `POST /accounts/logout/` (GET is rejected with `405`) |

Endpoints marked **Required** below use the `@login_required` decorator.

### CSRF protection

Every `POST` is protected by Django's `CsrfViewMiddleware`.

- **JSON/AJAX POSTs** must send the cookie value in a header:

  ```http
  Content-Type: application/json
  X-CSRFToken: <csrftoken cookie value>
  ```

- **HTML form POSTs** must include `{% csrf_token %}`.

A missing or invalid token returns `403 Forbidden`.

### Cart JSON envelope

Every `/cart/api/*` response uses the same envelope:

```json
{
  "success": true,
  "cart": {
    "count": 3,
    "item_count": 2,
    "items": [
      {
        "id": 12,
        "product_id": 5,
        "name": "Wireless Mouse",
        "slug": "wireless-mouse",
        "url": "/products/wireless-mouse/",
        "image": "/media/products/mouse.png",
        "price": "29.99",
        "quantity": 2,
        "subtotal": "59.98",
        "stock": 40
      }
    ],
    "total": "89.97"
  }
}
```

On validation errors the shape is:

```json
{ "success": false, "error": "Not enough stock available." }
```

`count` is the sum of quantities; `item_count` is the number of distinct line items.
All money values are serialized as **strings** (Django `Decimal`).

### Status codes used

| Code | Meaning |
| --- | --- |
| `200` | Success (HTML page rendered or JSON returned) |
| `302` | Redirect (login required, after login/logout, after checkout) |
| `400` | Invalid JSON body or failed validation |
| `403` | Missing/invalid CSRF token |
| `404` | Object not found or not owned by the current user |
| `405` | Wrong HTTP method for the endpoint |

---

## 1. Home

| | |
| --- | --- |
| **Method** | `GET` |
| **URL** | `/` (name: `home`) |
| **Auth required** | No (personalized section appears only when authenticated) |

**Request body (JSON):** none.

**Response:** `text/html` — `store/home.html`.
Context contains `featured` (up to 8 featured active products), `trending`
(up to 8 products ranked by `purchase_count`, then `views_count`) and, for a
logged-in user, `personalized` + `personalized_fallback` (FR-6).

**Status codes:** `200`.

**Example**

```bash
curl -s http://127.0.0.1:8000/ -o home.html
```

---

## 2. Product list, search & filters

| | |
| --- | --- |
| **Method** | `GET` |
| **URL** | `/products/` (name: `product_list`) |
| **Auth required** | No (a search by a logged-in user is recorded as `UserActivity`) |

**Query parameters**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `q` | string | No | Case-insensitive search over `name` and `description` |
| `category` | slug | No | Restrict to a category slug |
| `page` | integer | No | Page number, 12 products per page |

**Request body (JSON):** none.

**Response:** `text/html` — `store/product_list.html`.
Context: `page_obj` (Django `Page`), `categories`, `q`, `active_category`, `category`.
Only products with `status="active"` are shown, newest first.

**Status codes:** `200`.

**Example**

```bash
curl -s "http://127.0.0.1:8000/products/?q=keyboard&category=electronics&page=1" -o results.html
```

---

## 3. Products by category

| | |
| --- | --- |
| **Method** | `GET` |
| **URL** | `/categories/<slug>/` (name: `category_products`) |
| **Auth required** | No (logged-in visits are recorded as `category_view`) |

**Path parameters**

| Parameter | Type | Description |
| --- | --- | --- |
| `slug` | slug | Category slug, e.g. `electronics` |

**Request body (JSON):** none.
**Query parameters:** `page` (12 products per page).

**Response:** `text/html` — `store/product_list.html` filtered to the category.

**Status codes:** `200`; `404` if no category has that slug.

**Example**

```bash
curl -s http://127.0.0.1:8000/categories/electronics/ -o category.html
```

---

## 4. Product detail

| | |
| --- | --- |
| **Method** | `GET` |
| **URL** | `/products/<slug>/` (name: `product_detail`) |
| **Auth required** | No (logged-in views are recorded as `view`) |

**Path parameters:** `slug` — product slug.

**Request body (JSON):** none.

**Response:** `text/html` — `store/product_detail.html`.
Each request atomically increments `views_count`; context includes `product`,
`similar` and `similar_fallback` (FR-6 similar products).

**Status codes:** `200`; `404` if no product has that slug.

**Example**

```bash
curl -s http://127.0.0.1:8000/products/wireless-mouse/ -o product.html
```

---

## 5. Cart page

| | |
| --- | --- |
| **Method** | `GET` |
| **URL** | `/cart/` (name: `cart_detail`) |
| **Auth required** | **Yes** |

**Request body (JSON):** none.

**Response:** `text/html` — `store/cart.html` with `cart` and `items`.
The page renders the initial cart and then uses `static/js/cart.js` against the
JSON endpoints below.

**Status codes:** `200`; `302` to `/accounts/login/?next=/cart/` when anonymous.

**Example**

```bash
curl -s -b cookies.txt http://127.0.0.1:8000/cart/ -o cart.html
```

---

## 6. Get cart (JSON)

| | |
| --- | --- |
| **Method** | `GET` |
| **URL** | `/cart/api/` (name: `cart_api`) |
| **Auth required** | **Yes** |

**Request body (JSON):** none.

**Response (JSON):** the cart envelope (`success: true`, `cart` object).
A `Cart` row is created lazily on first access.

**Status codes:** `200`; `302` when anonymous; `405` for any method other than `GET`.

**Example**

```bash
curl -s -b cookies.txt http://127.0.0.1:8000/cart/api/
```

```json
{
  "success": true,
  "cart": {
    "count": 2,
    "item_count": 1,
    "items": [
      {
        "id": 12,
        "product_id": 5,
        "name": "Wireless Mouse",
        "slug": "wireless-mouse",
        "url": "/products/wireless-mouse/",
        "image": "/media/products/mouse.png",
        "price": "29.99",
        "quantity": 2,
        "subtotal": "59.98",
        "stock": 40
      }
    ],
    "total": "59.98"
  }
}
```

---

## 7. Add to cart (JSON)

| | |
| --- | --- |
| **Method** | `POST` |
| **URL** | `/cart/api/add/` (name: `cart_api_add`) |
| **Auth required** | **Yes** |

**Request body (JSON)**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `product_id` | integer | Yes | ID of an `active` product |
| `quantity` | integer | No | Quantity to add, default `1`; final quantity must be 1–100 |

```json
{ "product_id": 5, "quantity": 2 }
```

**Response (JSON):** the full cart envelope after the change.
If the product is already in the cart its quantity is incremented.

**Status codes**

| Code | Condition |
| --- | --- |
| `200` | Item added |
| `302` | Anonymous user |
| `400` | Invalid JSON, invalid `product_id`, quantity out of range, or quantity exceeds `stock` |
| `404` | Product does not exist or is not `active` |

**Example**

```bash
curl -s -X POST http://127.0.0.1:8000/cart/api/add/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF" \
  -b cookies.txt \
  -d '{"product_id": 5, "quantity": 2}'
```

---

## 8. Update cart item quantity (JSON)

| | |
| --- | --- |
| **Method** | `POST` |
| **URL** | `/cart/api/update/` (name: `cart_api_update`) |
| **Auth required** | **Yes** |

**Request body (JSON)**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `item_id` | integer | Yes | `CartItem.id` (from the cart envelope) |
| `quantity` | integer | Yes | New quantity, 1–100 |

```json
{ "item_id": 12, "quantity": 3 }
```

**Response (JSON):** the full cart envelope after the change.

**Status codes**

| Code | Condition |
| --- | --- |
| `200` | Quantity updated |
| `302` | Anonymous user |
| `400` | Invalid JSON, invalid `item_id`/`quantity`, quantity outside 1–100, or quantity exceeds `stock` |
| `404` | Item not found in the current user's cart |

**Example**

```bash
curl -s -X POST http://127.0.0.1:8000/cart/api/update/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF" \
  -b cookies.txt \
  -d '{"item_id": 12, "quantity": 3}'
```

---

## 9. Remove from cart (JSON)

| | |
| --- | --- |
| **Method** | `POST` |
| **URL** | `/cart/api/remove/` (name: `cart_api_remove`) |
| **Auth required** | **Yes** |

**Request body (JSON)**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `item_id` | integer | Yes | `CartItem.id` to remove |

```json
{ "item_id": 12 }
```

**Response (JSON):** the full cart envelope after removal.

**Status codes**

| Code | Condition |
| --- | --- |
| `200` | Item removed |
| `302` | Anonymous user |
| `400` | Invalid JSON or invalid `item_id` |
| `404` | Item not found in the current user's cart |

**Example**

```bash
curl -s -X POST http://127.0.0.1:8000/cart/api/remove/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF" \
  -b cookies.txt \
  -d '{"item_id": 12}'
```

---

## 10. Checkout / place order

| | |
| --- | --- |
| **Method** | `GET` (show form) · `POST` (place order) |
| **URL** | `/orders/checkout/` (name: `checkout`) |
| **Auth required** | **Yes** |

**GET** — renders `store/checkout.html` with the `CheckoutForm`, the `cart` and
its `items`. If the cart is empty the user is redirected to `/cart/` with a
warning message.

**POST request body (HTML form, `application/x-www-form-urlencoded`)**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `csrfmiddlewaretoken` | string | Yes | Django CSRF token |
| `shipping_address` | string | Yes | Shipping address (textarea) |
| `notes` | string | No | Optional order notes |

There is no JSON body for this endpoint — it is a standard HTML form POST.

**Response**

- Success → `302` to `/orders/<order_number>/`.
- Invalid form or insufficient stock → `200`, the page is re-rendered with
  validation errors.
- On success the order is created inside `transaction.atomic()`:
  `OrderItem.price` is snapshotted, `Product.stock` is decremented and
  `purchase_count` incremented with `F()` expressions, a `purchase`
  `UserActivity` is written for each line, and the cart is cleared.

**Status codes:** `200` (form / re-render with errors); `302` (empty cart or
successful order).

**Example**

```bash
curl -s -X POST http://127.0.0.1:8000/orders/checkout/ \
  -b cookies.txt \
  -d "csrfmiddlewaretoken=$CSRF" \
  -d "shipping_address=221B Baker Street, London NW1 6XE" \
  -d "notes=Leave at reception"
```

---

## 11. Order history

| | |
| --- | --- |
| **Method** | `GET` |
| **URL** | `/orders/` (name: `order_history`) |
| **Auth required** | **Yes** |

**Request body (JSON):** none.

**Response:** `text/html` — `store/order_history.html`.
Context `orders` contains only the current user's orders, newest first.

**Status codes:** `200`; `302` when anonymous.

**Example**

```bash
curl -s -b cookies.txt http://127.0.0.1:8000/orders/ -o orders.html
```

---

## 12. Order detail

| | |
| --- | --- |
| **Method** | `GET` |
| **URL** | `/orders/<order_number>/` (name: `order_detail`) |
| **Auth required** | **Yes** |

**Path parameters:** `order_number` — the 32-character uppercase order number
(e.g. `A1B2C3D4E5F6...`).

**Request body (JSON):** none.

**Response:** `text/html` — `store/order_detail.html` with `order` and its
`items` (product, quantity, snapshot price, subtotal).

**Status codes:** `200`; `302` when anonymous; `404` if the order does not exist
**or belongs to another user**.

**Example**

```bash
curl -s -b cookies.txt http://127.0.0.1:8000/orders/A1B2C3D4E5F6.../ -o order.html
```

---

## 13. AI recommendations page

| | |
| --- | --- |
| **Method** | `GET` |
| **URL** | `/recommendations/` (name: `recommendations`) |
| **Auth required** | **Yes** |

**Request body (JSON):** none.

**Response:** `text/html` — `store/recommendations.html`.
Context:

| Key | Description |
| --- | --- |
| `personalized` | Up to 12 AI recommendations (`product`, `reason`, `score`, `source`) |
| `personalized_fallback` | `true` when deterministic fallback was used |
| `trending` | Up to 8 deterministic trending products |

**Status codes:** `200`; `302` when anonymous.

**Example**

```bash
curl -s -b cookies.txt http://127.0.0.1:8000/recommendations/ -o recs.html
```

---

## 14. Log a recommendation click

| | |
| --- | --- |
| **Method** | `POST` |
| **URL** | `/recommendations/click/` (name: `recommendation_click`) |
| **Auth required** | **Yes** |

Appends a `UserActivity(activity_type="recommendation_click")` row used as a
signal for future recommendations. Activity rows are append-only.

**Request body (JSON)**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `product_id` | integer | Yes | Clicked product ID |
| `source` | string | No | Where the click came from, default `"ai"`, max 30 chars |

```json
{ "product_id": 5, "source": "ai" }
```

**Response (JSON)**

```json
{ "success": true }
```

**Status codes**

| Code | Condition |
| --- | --- |
| `200` | Click recorded |
| `302` | Anonymous user |
| `400` | Invalid JSON or invalid `product_id` |
| `404` | Product does not exist |

**Example**

```bash
curl -s -X POST http://127.0.0.1:8000/recommendations/click/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF" \
  -b cookies.txt \
  -d '{"product_id": 5, "source": "ai"}'
```

---

## 15. Register

| | |
| --- | --- |
| **Method** | `GET` (show form) · `POST` (create account) |
| **URL** | `/accounts/register/` (name: `register`) |
| **Auth required** | No (an already-authenticated user is redirected to `/`) |

**POST request body (HTML form)**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `csrfmiddlewaretoken` | string | Yes | Django CSRF token |
| `username` | string | Yes | Unique username |
| `email` | string | Yes | Unique e-mail (case-insensitive check) |
| `password1` | string | Yes | Password (validated by `AUTH_PASSWORD_VALIDATORS`) |
| `password2` | string | Yes | Password confirmation, must match `password1` |

**Response**

- Success → `302` to `/`; the new user is logged in automatically.
- Invalid data (duplicate username/email, weak/mismatched password) → `200`
  with `store/accounts/register.html` re-rendered and field errors.

**Status codes:** `200`; `302` (success or already logged in); `403` (bad CSRF).

**Example**

```bash
curl -s -c cookies.txt -b cookies.txt -X POST http://127.0.0.1:8000/accounts/register/ \
  -d "csrfmiddlewaretoken=$CSRF" \
  -d "username=jane" \
  -d "email=jane@example.com" \
  -d "password1=S3curePass!23" \
  -d "password2=S3curePass!23"
```

---

## 16. Login

| | |
| --- | --- |
| **Method** | `GET` (show form) · `POST` (authenticate) |
| **URL** | `/accounts/login/` (name: `login`) |
| **Auth required** | No (an already-authenticated user is redirected to `/`) |

**POST request body (HTML form)**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `csrfmiddlewaretoken` | string | Yes | Django CSRF token |
| `username` | string | Yes | Username |
| `password` | string | Yes | Password |
| `next` | string | No | Relative URL to redirect to after login (validated against allowed hosts) |

**Response**

- Success → `302` to `next` when it is a safe local URL, otherwise to `/`.
- Invalid credentials → `200` with `store/accounts/login.html` and form errors.

**Status codes:** `200`; `302`; `403` (bad CSRF).

**Example**

```bash
curl -s -c cookies.txt -b cookies.txt -X POST http://127.0.0.1:8000/accounts/login/ \
  -d "csrfmiddlewaretoken=$CSRF" \
  -d "username=jane" \
  -d "password=S3curePass!23" \
  -d "next=/cart/"
```

---

## 17. Logout

| | |
| --- | --- |
| **Method** | `POST` only (`@require_POST`) |
| **URL** | `/accounts/logout/` (name: `logout`) |
| **Auth required** | No decorator, but it destroys the current session |

**POST request body (HTML form)**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `csrfmiddlewaretoken` | string | Yes | Django CSRF token |

**Response:** `302` to `/` (session destroyed, success message queued).

**Status codes:** `302` on success; `403` (bad CSRF); `405` for `GET`/`PUT`/`DELETE`.

**Example**

```bash
curl -s -b cookies.txt -c cookies.txt -X POST http://127.0.0.1:8000/accounts/logout/ \
  -d "csrfmiddlewaretoken=$CSRF"
```

---

## Appendix — endpoint summary

| # | Method | URL | Auth | Response |
| --- | --- | --- | --- | --- |
| 1 | GET | `/` | Optional | HTML |
| 2 | GET | `/products/` | Optional | HTML |
| 3 | GET | `/categories/<slug>/` | Optional | HTML |
| 4 | GET | `/products/<slug>/` | Optional | HTML |
| 5 | GET | `/cart/` | Yes | HTML |
| 6 | GET | `/cart/api/` | Yes | JSON |
| 7 | POST | `/cart/api/add/` | Yes | JSON |
| 8 | POST | `/cart/api/update/` | Yes | JSON |
| 9 | POST | `/cart/api/remove/` | Yes | JSON |
| 10 | GET/POST | `/orders/checkout/` | Yes | HTML |
| 11 | GET | `/orders/` | Yes | HTML |
| 12 | GET | `/orders/<order_number>/` | Yes | HTML |
| 13 | GET | `/recommendations/` | Yes | HTML |
| 14 | POST | `/recommendations/click/` | Yes | JSON |
| 15 | GET/POST | `/accounts/register/` | No | HTML |
| 16 | GET/POST | `/accounts/login/` | No | HTML |
| 17 | POST | `/accounts/logout/` | No | Redirect |
| — | GET | `/admin/` | Staff | Django admin (FR-2, FR-5) |

Authentication is required for `/cart/`, all `/cart/api/*`, all `/orders/*` and
`/recommendations/`; anonymous requests are redirected to `/accounts/login/?next=...`.

---

## Appendix — error examples

```json
{ "success": false, "error": "Invalid JSON." }
```

```json
{ "success": false, "error": "Invalid item id or quantity." }
```

```json
{ "success": false, "error": "Quantity must be between 1 and 100." }
```

```json
{ "success": false, "error": "Not enough stock available." }
```

```json
{ "success": false, "error": "Invalid product id." }
```
