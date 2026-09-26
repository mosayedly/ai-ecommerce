"""End-to-end browser tests (Playwright) for the AI-Powered E-Commerce System.

Run with the Django dev server already listening on http://127.0.0.1:8000:

    pytest tests/e2e_test.py -v -s

A real Chromium browser drives the app so that the Vanilla-JavaScript ``fetch()``
calls in ``static/js/main.js`` (add-to-cart, recommendation clicks) and
``static/js/cart.js`` (update/remove) are exercised — not just server-rendered HTML.

The suite is split into flows A–H that all share ONE browser session/page.
"""

from __future__ import annotations

import os
import re
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from playwright.sync_api import expect

# ---------------------------------------------------------------------------
# Django bootstrap (pytest-django is not used; we configure Django ourselves).
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
# Playwright's sync API runs an asyncio event loop in the test thread; Django's
# async-safety guard would otherwise reject every ORM call made by the tests.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

import django  # noqa: E402

django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.db import connections  # noqa: E402

from store.models import (  # noqa: E402
    Category,
    Order,
    Product,
    Recommendation,
    UserActivity,
)

BASE_URL = "http://127.0.0.1:8000"
SCREENSHOTS_DIR = PROJECT_ROOT / "docs" / "screenshots"

TEST_USERNAME = "e2e_tester"
TEST_EMAIL = "e2e_tester@example.com"
TEST_PASSWORD = "E2eStrongPass!23"

# Shared state between flows (one browser session, sequential tests).
STATE: dict = {}

CATEGORY_NAMES = ["Electronics", "Books", "Clothing"]

# (name, category, price, stock, is_featured)
PRODUCT_SPECS = [
    ("Gaming Mouse", "Electronics", "49.99", 25, True),
    ("Wireless Mouse", "Electronics", "29.99", 40, False),
    ("Mechanical Keyboard", "Electronics", "89.99", 15, True),
    ("Clean Code", "Books", "39.99", 30, False),
    ("The Pragmatic Programmer", "Books", "44.99", 20, False),
    ("Cotton T-Shirt", "Clothing", "19.99", 50, False),
    ("Denim Jacket", "Clothing", "79.99", 10, False),
    ("Running Shoes", "Clothing", "99.99", 8, False),
]

# Generic fallback reasons that are NOT considered "AI explanations".
GENERIC_REASONS = {
    "Similar product",
    "Popular in your interests",
    "Popular right now",
    "New arrival",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def shot(page, filename: str) -> None:
    """Save a full-page screenshot into docs/screenshots/."""
    path = SCREENSHOTS_DIR / filename
    page.screenshot(path=str(path), full_page=True)
    print(f"    [screenshot] {path} ({path.stat().st_size} bytes)")


def add_product_to_cart(page, slug: str, quantity: int = 1) -> None:
    """Open a product page and submit the add-to-cart form (Vanilla-JS fetch)."""
    page.goto(f"{BASE_URL}/products/{slug}/")
    form = page.locator(".add-to-cart-form")
    expect(form).to_be_visible()
    form.locator("input[name='quantity']").fill(str(quantity))
    form.locator("button[type='submit']").click()


def cart_row(page, product_name: str):
    """Return the cart table row for a product name."""
    return page.locator("#cart-container tbody tr").filter(has_text=product_name)


def login(page, username: str, password: str) -> None:
    page.goto(f"{BASE_URL}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.get_by_role("button", name="Login").click()
    page.wait_for_load_state("load")


# ---------------------------------------------------------------------------
# Session fixtures: Flow A data setup + ONE browser session
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def e2e_data():
    """Flow A — deterministic catalog + a clean test user, before the browser starts."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    product_names = [spec[0] for spec in PRODUCT_SPECS]

    # Remove any leftovers from a previous run so stock/purchase deltas are exact.
    User.objects.filter(username=TEST_USERNAME).delete()
    Order.objects.filter(items__product__name__in=product_names).distinct().delete()
    Product.objects.filter(name__in=product_names).delete()

    categories = {}
    for name in CATEGORY_NAMES:
        category, _ = Category.objects.get_or_create(name=name)
        categories[name] = category

    products = {}
    for name, category_name, price, stock, featured in PRODUCT_SPECS:
        products[name] = Product.objects.create(
            name=name,
            category=categories[category_name],
            price=Decimal(price),
            stock=stock,
            status="active",
            is_featured=featured,
            description=(
                f"{name} — genuine {category_name} product used by the E2E test suite."
            ),
        )

    STATE["categories"] = categories
    STATE["products"] = products
    STATE["initial_stock"] = {p.pk: p.stock for p in products.values()}
    STATE["initial_purchase_count"] = {p.pk: p.purchase_count for p in products.values()}

    print(
        f"\n[A] seeded {len(categories)} categories / {len(products)} products "
        f"(2 featured); removed any pre-existing '{TEST_USERNAME}' user"
    )

    yield STATE

    connections.close_all()


@pytest.fixture(scope="session")
def e2e_page(browser, e2e_data):
    """A single Chromium page reused by every flow (one browser session)."""
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    context.set_default_timeout(30000)
    page = context.new_page()
    page.set_default_timeout(30000)
    print("\n[browser] Chromium context/page created (headless)")
    yield page
    context.close()


# ---------------------------------------------------------------------------
# Flow A — data setup
# ---------------------------------------------------------------------------
def test_a_setup_data(e2e_data):
    """A. 3 categories, 8 products (2 featured), stale test user removed."""
    assert len(e2e_data["categories"]) == 3
    assert Product.objects.filter(name__in=[s[0] for s in PRODUCT_SPECS]).count() == 8
    assert (
        Product.objects.filter(
            is_featured=True, name__in=[s[0] for s in PRODUCT_SPECS]
        ).count()
        == 2
    )
    assert not User.objects.filter(username=TEST_USERNAME).exists()
    print("[A] PASS — categories=3, products=8 (featured=2), e2e_tester absent")


# ---------------------------------------------------------------------------
# Flow B — anonymous browsing, search, category filter, product detail
# ---------------------------------------------------------------------------
def test_b_anonymous_browsing(e2e_page):
    """B. Home, product list, search, category filter, product detail."""
    page = e2e_page

    # --- B1: home page -----------------------------------------------------
    response = page.goto(f"{BASE_URL}/")
    assert response.status == 200, f"GET / returned {response.status}"
    expect(page.get_by_role("heading", name="Featured Products")).to_be_visible()
    shot(page, "01_home.png")

    # --- B2: product list --------------------------------------------------
    response = page.goto(f"{BASE_URL}/products/")
    assert response.status == 200, f"GET /products/ returned {response.status}"
    cards = page.locator(".product-card")
    count = cards.count()
    assert count >= 8, f"expected at least 8 product cards, found {count}"
    shot(page, "02_product_list.png")

    # --- B3: search "mouse" ------------------------------------------------
    page.fill("input[name='q']", "mouse")
    page.get_by_role("button", name="Search").click()
    page.wait_for_load_state("load")
    assert "q=mouse" in page.url, f"search did not navigate with q=mouse: {page.url}"
    expect(page.locator(".product-card h3", has_text="Gaming Mouse").first).to_be_visible()

    # --- B4: filter by Electronics ----------------------------------------
    page.goto(f"{BASE_URL}/products/")
    page.select_option("select[name='category']", "electronics")
    page.get_by_role("button", name="Search").click()
    page.wait_for_load_state("load")
    expect(page.locator(".product-card h3", has_text="Gaming Mouse").first).to_be_visible()
    expect(page.locator(".product-card h3", has_text="Wireless Mouse").first).to_be_visible()
    assert page.locator(".product-card h3", has_text="Clean Code").count() == 0, (
        "Books product leaked into the Electronics filter"
    )
    assert page.locator(".product-card h3", has_text="Cotton T-Shirt").count() == 0, (
        "Clothing product leaked into the Electronics filter"
    )

    # --- B5: open a product detail page -----------------------------------
    page.locator(".product-card h3", has_text="Gaming Mouse").first.click()
    page.wait_for_load_state("load")
    assert page.url.rstrip("/").endswith("/products/gaming-mouse"), page.url
    # Similar products calls the AI service; allow up to 30s (per test rules).
    expect(page.get_by_role("heading", name="Similar Products")).to_be_visible(
        timeout=30000
    )
    shot(page, "03_product_detail.png")
    print("[B] PASS — home/list/search/filter/detail all verified")


# ---------------------------------------------------------------------------
# Flow C — registration, logged-in navbar, logout
# ---------------------------------------------------------------------------
def test_c_registration_and_logout(e2e_page):
    """C. Register e2e_tester, assert navbar, then log out."""
    page = e2e_page

    page.goto(f"{BASE_URL}/accounts/register/")
    expect(page.get_by_role("heading", name="Register")).to_be_visible()
    shot(page, "04_register.png")

    page.fill("#id_username", TEST_USERNAME)
    page.fill("#id_email", TEST_EMAIL)
    page.fill("#id_password1", TEST_PASSWORD)
    page.fill("#id_password2", TEST_PASSWORD)
    page.get_by_role("button", name="Register").click()
    page.wait_for_load_state("load")

    # Registration logs the user straight in -> navbar shows "Hi, e2e_tester".
    expect(page.locator(".nav-user")).to_contain_text(TEST_USERNAME)
    assert User.objects.filter(username=TEST_USERNAME).exists(), "user was not created"

    # --- logout (POST-only) ------------------------------------------------
    page.get_by_role("button", name="Logout").click()
    page.wait_for_load_state("load")
    # Scope to the navbar: anonymous product cards also render a "Login to buy" link.
    expect(
        page.locator(".nav-links").get_by_role("link", name="Login", exact=True)
    ).to_be_visible()
    expect(page.locator(".nav-user")).to_have_count(0)
    expect(page.locator("#cart-count")).to_have_count(0)
    print("[C] PASS — registration auto-login + POST logout verified")


# ---------------------------------------------------------------------------
# Flow D — cart CRUD through the Vanilla-JS fetch API (no page reloads)
# ---------------------------------------------------------------------------
def test_d_cart_fetch_api(e2e_page):
    """D. Add/update/remove via fetch; badge + totals update without reload."""
    page = e2e_page
    mouse = STATE["products"]["Gaming Mouse"]
    wmouse = STATE["products"]["Wireless Mouse"]

    login(page, TEST_USERNAME, TEST_PASSWORD)
    expect(page.locator(".nav-user")).to_contain_text(TEST_USERNAME)

    # A logged-in search — this records the 'search' UserActivity checked in flow H.
    page.goto(f"{BASE_URL}/products/?q=mouse")
    expect(page.locator(".product-card h3", has_text="Gaming Mouse").first).to_be_visible()

    # --- D1: add first product (fetch, no reload) --------------------------
    add_product_to_cart(page, "gaming-mouse", 1)
    expect(page.locator("#cart-count")).to_have_text("1")
    assert "/products/gaming-mouse" in page.url, (
        "add-to-cart navigated away — it must be fetch-only"
    )

    # --- D2: add second product -------------------------------------------
    add_product_to_cart(page, "wireless-mouse", 1)
    expect(page.locator("#cart-count")).to_have_text("2")
    assert "/products/wireless-mouse" in page.url

    # --- D3: cart page shows 2 rows with correct subtotals -----------------
    page.goto(f"{BASE_URL}/cart/")
    rows = page.locator("#cart-container tbody tr")
    expect(rows).to_have_count(2)
    expect(cart_row(page, "Gaming Mouse").locator(".subtotal")).to_have_text(
        f"${mouse.price}"
    )
    expect(cart_row(page, "Wireless Mouse").locator(".subtotal")).to_have_text(
        f"${wmouse.price}"
    )
    expect(page.locator("#cart-total")).to_have_text(f"${mouse.price + wmouse.price}")
    shot(page, "05_cart.png")

    # --- D4: change quantity 1 -> 3 through the UI (fetch, no reload) ------
    cart_url = page.url
    row = cart_row(page, "Gaming Mouse")
    item_id = row.get_attribute("data-item-id")
    qty_input = row.locator(".qty-input")
    expected_total = mouse.price * 3 + wmouse.price
    # Set the value and dispatch exactly ONE bubbling change event, then wait for
    # the fetch round-trip so no stale response can race the removal below.
    with page.expect_response(lambda r: "/cart/api/update/" in r.url) as update_info:
        qty_input.evaluate(
            "el => { el.value = '3';"
            " el.dispatchEvent(new Event('change', { bubbles: true })); }"
        )
    assert update_info.value.status == 200, "cart update API did not return 200"
    expect(page.locator("#cart-total")).to_have_text(f"${expected_total}")
    expect(page.locator("#cart-count")).to_have_text("4")
    assert page.url == cart_url, "quantity update triggered a page reload"

    # --- D5: remove the qty-3 row -> badge back to 1 -----------------------
    with page.expect_response(lambda r: "/cart/api/remove/" in r.url) as remove_info:
        page.locator(f"button.remove-item[data-item-id='{item_id}']").click()
    assert remove_info.value.status == 200, "cart remove API did not return 200"
    expect(page.locator("#cart-container tbody tr")).to_have_count(1)
    expect(page.locator("#cart-count")).to_have_text("1")
    assert page.url == cart_url, "remove triggered a page reload"
    print("[D] PASS — fetch add/update/remove; badge & total changed without reload")


# ---------------------------------------------------------------------------
# Flow E — checkout
# ---------------------------------------------------------------------------
def test_e_checkout(e2e_page):
    """E. Bring the cart to 3 items, place the order, verify the order page."""
    page = e2e_page
    mouse = STATE["products"]["Gaming Mouse"]
    wmouse = STATE["products"]["Wireless Mouse"]

    # Cart holds Wireless Mouse x1 -> add Gaming Mouse x2 => 3 items total.
    expect(page.locator("#cart-count")).to_have_text("1")
    add_product_to_cart(page, "gaming-mouse", 2)
    expect(page.locator("#cart-count")).to_have_text("3")

    page.goto(f"{BASE_URL}/orders/checkout/")
    expect(page.get_by_role("heading", name="Checkout")).to_be_visible()
    shot(page, "06_checkout.png")

    expected_total = mouse.price * 2 + wmouse.price
    expect(page.locator(".order-summary .total")).to_have_text(
        f"Total: ${expected_total}"
    )

    page.fill("#id_shipping_address", "221B Baker Street, London NW1 6XE")
    page.fill("#id_notes", "E2E automated test order")
    page.get_by_role("button", name="Place Order").click()
    page.wait_for_load_state("load")

    assert re.match(
        r"^http://127\.0\.0\.1:8000/orders/[0-9A-F]{32}/$", page.url
    ), f"checkout did not redirect to an order detail page: {page.url}"
    order_number = page.url.rstrip("/").rsplit("/", 1)[-1]
    STATE["order_number"] = order_number
    STATE["purchased"] = {mouse.pk: 2, wmouse.pk: 1}

    expect(page.get_by_role("heading", name=f"Order {order_number}")).to_be_visible()
    table = page.locator("table.orders-table")
    expect(table).to_contain_text("Gaming Mouse")
    expect(table).to_contain_text("Wireless Mouse")
    expect(table.locator("tfoot")).to_contain_text(f"${expected_total}")
    expect(page.locator("#cart-count")).to_have_text("0")  # cart cleared
    shot(page, "07_order_detail.png")

    order = Order.objects.get(order_number=order_number)
    assert order.total_price == expected_total, (
        f"order total {order.total_price} != {expected_total}"
    )
    print(f"[E] PASS — order {order_number} placed (total ${order.total_price}); cart cleared")


# ---------------------------------------------------------------------------
# Flow F — stock + purchase_count verification (ORM, after checkout)
# ---------------------------------------------------------------------------
def test_f_stock_and_purchase_count():
    """F. Each purchased product lost stock and gained purchase_count."""
    purchased = STATE["purchased"]
    for product_id, qty in purchased.items():
        product = Product.objects.get(pk=product_id)
        expected_stock = STATE["initial_stock"][product_id] - qty
        expected_purchases = STATE["initial_purchase_count"][product_id] + qty
        assert product.stock == expected_stock, (
            f"{product.name}: stock is {product.stock}, expected {expected_stock}"
        )
        assert product.purchase_count == expected_purchases, (
            f"{product.name}: purchase_count is {product.purchase_count}, "
            f"expected {expected_purchases}"
        )
    order = Order.objects.get(order_number=STATE["order_number"])
    assert order.items.count() == len(purchased)
    print(
        f"[F] PASS — stock/purchase_count correct for {len(purchased)} products "
        f"(order {order.order_number})"
    )


# ---------------------------------------------------------------------------
# Flow G — AI recommendations (works with a DeepSeek or Gemini key)
# ---------------------------------------------------------------------------
def test_g_recommendations(e2e_page):
    """G. Home 'Recommended for You' + /recommendations/ with a real AI reason."""
    page = e2e_page

    # Drop the 6h cache so the AI is called now that the user has real history.
    Recommendation.objects.filter(user__username=TEST_USERNAME).delete()

    page.goto(f"{BASE_URL}/")
    expect(page.get_by_role("heading", name="Recommended for You")).to_be_visible(
        timeout=30000
    )

    response = page.goto(f"{BASE_URL}/recommendations/")
    assert response.status == 200, f"GET /recommendations/ returned {response.status}"
    cards = page.locator(".recommendation-card")
    expect(cards.first).to_be_visible(timeout=30000)
    card_count = cards.count()
    assert card_count >= 1, "no recommendation cards rendered"
    shot(page, "08_recommendations.png")

    reasons = [r.strip() for r in page.locator(".rec-reason").all_inner_texts()]
    non_generic = [r for r in reasons if len(r) > 30 and r not in GENERIC_REASONS]
    assert non_generic, (
        f"expected at least one non-generic AI reason (>30 chars); got: {reasons}"
    )
    print(
        f"[G] PASS — {card_count} cards on /recommendations/; "
        f"AI reason example: {non_generic[0][:90]!r}"
    )


# ---------------------------------------------------------------------------
# Flow H — UserActivity verification (ORM)
# ---------------------------------------------------------------------------
def test_h_user_activity():
    """H. 'view', 'search' (query='mouse') and 'purchase' activities exist."""
    user = User.objects.get(username=TEST_USERNAME)
    activities = UserActivity.objects.filter(user=user)

    views = activities.filter(activity_type="view")
    assert views.exists(), "no 'view' UserActivity rows for e2e_tester"

    searches = activities.filter(activity_type="search")
    assert searches.exists(), "no 'search' UserActivity rows for e2e_tester"
    assert any((a.metadata or {}).get("query") == "mouse" for a in searches), (
        "no search activity with query='mouse'"
    )

    purchases = activities.filter(activity_type="purchase")
    assert purchases.exists(), "no 'purchase' UserActivity rows after checkout"

    print(
        f"[H] PASS — total={activities.count()} views={views.count()} "
        f"search={searches.count()} purchase={purchases.count()}"
    )
