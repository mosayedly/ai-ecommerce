"""FR-6 AI Product Recommendation service.

This module wraps whichever AI provider is selected via ``AI_PROVIDER`` —
DeepSeek, Google Gemini, OpenAI, Groq, Mistral, Together, OpenRouter, Ollama or
any custom OpenAI-compatible endpoint — through the ``openai`` SDK, and
provides the three recommendation flows required by the SRS:

* Personalized recommendations (``source="ai"``) -> persisted + cached.
* Similar products          (``source="similar"``) -> AI-ranked, transient.
* Trending products         (``source="trending"``) -> deterministic DB ranking.

Every AI entry point fails *soft*: if the key is missing, the network times out,
or the model returns invalid JSON, the service falls back to deterministic
results instead of raising.
"""

import json
import logging
from collections import Counter

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import OrderItem, Product, Recommendation, UserActivity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "https://api.deepseek.com"
RECOMMENDATION_TTL_SECONDS = getattr(settings, "RECOMMENDATION_TTL_SECONDS", 6 * 60 * 60)

MAX_CANDIDATES = 40
MAX_REASON_LENGTH = 200

SYSTEM_PROMPT = (
    "You are a helpful product recommendation assistant for an e-commerce store. "
    "Recommend products the customer is likely to be interested in. "
    "Respond ONLY with valid JSON that matches the requested schema. "
    "Do not include markdown, code fences, or any extra commentary."
)

_client = None
_client_signature = None


# ---------------------------------------------------------------------------
# AI client (any OpenAI-compatible provider)
# ---------------------------------------------------------------------------

# Providers that run locally and therefore need no real API key. The OpenAI
# SDK still requires *some* key string, so a placeholder is sent instead.
KEYLESS_PROVIDERS = {"ollama"}


def _get_client():
    """Return a lazily-created AI client for the active provider, or ``None``."""
    global _client, _client_signature

    api_key = getattr(settings, "AI_API_KEY", "")
    if not api_key and getattr(settings, "AI_PROVIDER", "") in KEYLESS_PROVIDERS:
        api_key = "not-needed"
    base_url = getattr(settings, "AI_BASE_URL", DEFAULT_BASE_URL)
    signature = (api_key, base_url)

    if _client is not None and _client_signature == signature:
        return _client
    if not api_key:
        logger.warning(
            "No API key configured for AI provider '%s'; AI recommendations are disabled.",
            getattr(settings, "AI_PROVIDER", "deepseek"),
        )
        return None
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("The openai SDK is not installed; AI recommendations are disabled.")
        return None
    _client = OpenAI(api_key=api_key, base_url=base_url)
    _client_signature = signature
    return _client


# ---------------------------------------------------------------------------
# User context building
# ---------------------------------------------------------------------------

def build_user_context(user, activity_limit=50, order_limit=20):
    """Aggregate a user's recent activity + orders into a compact structure."""
    activities = (
        UserActivity.objects.filter(user=user)
        .select_related("product__category", "category")
        .order_by("-created_at")[:activity_limit]
    )

    category_counts = Counter()
    recently_viewed = []
    searched = []
    added_to_cart = []
    purchased = []

    for activity in activities:
        category = activity.category
        if category is None and activity.product and activity.product.category:
            category = activity.product.category
        if category:
            category_counts[category.name] += 1

        if activity.activity_type == "view" and activity.product:
            recently_viewed.append(activity.product.name)
        elif activity.activity_type == "search":
            query = (activity.metadata or {}).get("query")
            if query:
                searched.append(query)
        elif activity.activity_type == "add_to_cart" and activity.product:
            added_to_cart.append(activity.product.name)

    order_items = (
        OrderItem.objects.filter(order__user=user)
        .exclude(order__status="cancelled")
        .select_related("product__category")
        .order_by("-created_at")[:order_limit]
    )
    for item in order_items:
        purchased.append(item.product.name)
        if item.product.category:
            category_counts[item.product.category.name] += 1

    return {
        "top_categories": [name for name, _ in category_counts.most_common(5)],
        "recently_viewed": _dedupe(recently_viewed)[:10],
        "searched": _dedupe(searched)[:10],
        "cart": _dedupe(added_to_cart)[:10],
        "purchased": _dedupe(purchased)[:10],
    }


def _dedupe(values):
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


# ---------------------------------------------------------------------------
# Candidate catalog
# ---------------------------------------------------------------------------

def _candidate_products_for_user(user, top_categories, limit=MAX_CANDIDATES):
    """Return active, in-stock products most relevant to the user."""
    base = Product.objects.filter(status="active", stock__gt=0).select_related("category")

    purchased_ids = set(
        OrderItem.objects.filter(order__user=user)
        .exclude(order__status="cancelled")
        .values_list("product_id", flat=True)
    )

    products = list(base.exclude(pk__in=purchased_ids))
    if not products:
        products = list(base)

    def sort_key(product):
        in_interest = 1 if product.category and product.category.name in top_categories else 0
        return (in_interest, product.purchase_count, product.views_count)

    products.sort(key=sort_key, reverse=True)
    return products[:limit]


def _candidate_products_similar(anchor, limit=MAX_CANDIDATES):
    """Return a candidate pool for 'similar to anchor' recommendations."""
    candidates = []
    if anchor.category:
        candidates = list(
            Product.objects.filter(status="active", category=anchor.category)
            .exclude(pk=anchor.pk)
            .select_related("category")
        )

    if len(candidates) < limit:
        price = float(anchor.price or 0)
        low, high = price * 0.7, price * 1.3
        extras = list(
            Product.objects.filter(status="active", price__gte=low, price__lte=high)
            .exclude(pk=anchor.pk)
            .exclude(pk__in=[c.pk for c in candidates])
            .select_related("category")
        )
        candidates += extras

    if len(candidates) < limit:
        fill = list(
            Product.objects.filter(status="active")
            .exclude(pk=anchor.pk)
            .exclude(pk__in=[c.pk for c in candidates])
            .select_related("category")
            .order_by("-purchase_count", "-views_count")[: limit - len(candidates)]
        )
        candidates += fill

    return candidates[:limit]


def _serialize_catalog(products):
    """Serialize products into a compact, token-efficient catalog."""
    catalog = []
    for product in products:
        description = (product.description or "").strip().replace("\n", " ")
        catalog.append({
            "id": product.pk,
            "name": product.name,
            "category": product.category.name if product.category else "",
            "price": str(product.price),
            "description": description[:120],
            "purchase_count": product.purchase_count,
            "views_count": product.views_count,
        })
    return catalog


# ---------------------------------------------------------------------------
# AI call + parsing
# ---------------------------------------------------------------------------

def call_ai(system_prompt, user_prompt):
    """Call the active AI provider and return parsed JSON, or ``None`` on any failure.

    Every supported provider exposes an OpenAI-compatible chat-completions
    endpoint, so a single implementation covers all of them. Which provider
    (and model / base URL / timeout) is used comes from the unified ``AI_*``
    settings, computed in ``config/settings.py`` from ``AI_PROVIDER``.
    """
    client = _get_client()
    if client is None:
        return None
    try:
        response = client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            response_format={"type": "json_object"},
            timeout=settings.AI_TIMEOUT,
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("%s returned invalid JSON: %s", settings.AI_PROVIDER, exc)
        return None
    except Exception as exc:  # network errors, timeouts, API errors, etc.
        logger.warning("%s call failed (%s): %s", settings.AI_PROVIDER, type(exc).__name__, exc)
        return None


def parse_recommendations(data, limit=None):
    """Validate/normalize model output into a list of dict items."""
    if not isinstance(data, dict):
        return []

    raw = data.get("recommendations")
    if not isinstance(raw, list):
        raw = data.get("items")
    if not isinstance(raw, list):
        return []

    results = []
    seen = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            product_id = int(entry.get("product_id") or entry.get("id"))
        except (TypeError, ValueError):
            continue
        if product_id in seen:
            continue

        reason = str(entry.get("reason", "")).strip()
        if len(reason) > MAX_REASON_LENGTH:
            reason = reason[:MAX_REASON_LENGTH]
        try:
            score = float(entry.get("score", 0.5))
        except (TypeError, ValueError):
            score = 0.5
        score = max(0.0, min(1.0, score))

        seen.add(product_id)
        results.append({"product_id": product_id, "reason": reason, "score": score})
        if limit and len(results) >= limit:
            break

    return results


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def persist_recommendations(user, items, source):
    """Replace this user's recommendations for ``source`` with fresh rows."""
    if not items:
        return []

    valid_products = {
        product.pk: product
        for product in Product.objects.filter(
            pk__in=[item["product_id"] for item in items]
        )
    }

    rows = []
    for item in items:
        product = valid_products.get(item["product_id"])
        if product is None:
            continue
        rows.append(
            Recommendation(
                user=user,
                product=product,
                reason=item["reason"],
                score=item["score"],
                source=source,
            )
        )

    with transaction.atomic():
        Recommendation.objects.filter(user=user, source=source).delete()
        if rows:
            Recommendation.objects.bulk_create(rows)

    return rows


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _personalized_prompt(context, catalog, limit):
    lines = []
    if context["top_categories"]:
        lines.append("Top categories of interest: " + ", ".join(context["top_categories"]))
    if context["recently_viewed"]:
        lines.append("Recently viewed: " + ", ".join(context["recently_viewed"]))
    if context["searched"]:
        lines.append("Recent searches: " + ", ".join(context["searched"]))
    if context["cart"]:
        lines.append("Currently in cart: " + ", ".join(context["cart"]))
    if context["purchased"]:
        lines.append("Purchased before: " + ", ".join(context["purchased"]))

    profile = "\n".join(lines) if lines else "(new customer with no history yet)"

    return (
        f"Customer profile:\n{profile}\n\n"
        f"Catalog (choose product ids only from this list):\n{json.dumps(catalog)}\n\n"
        f"Pick {limit} products this customer would most likely buy. "
        f"Prefer relevant, in-stock items and avoid repeating items they already own. "
        f"Respond with JSON in exactly this shape: "
        f'{{"recommendations":[{{"product_id": 1, "reason": "short friendly reason", "score": 0.0}}]}} '
        f"where score is a confidence from 0.0 to 1.0."
    )


def _similar_prompt(anchor, catalog, limit):
    return (
        f"Anchor product the customer is currently viewing:\n"
        f"name: {anchor.name}\n"
        f"category: {anchor.category.name if anchor.category else 'unknown'}\n"
        f"price: {anchor.price}\n"
        f"description: {(anchor.description or '').strip()[:200]}\n\n"
        f"Catalog (choose product ids only from this list):\n{json.dumps(catalog)}\n\n"
        f"Pick {limit} products that are most similar or complementary to the anchor. "
        f"Do not include the anchor product itself. "
        f"Respond with JSON in exactly this shape: "
        f'{{"recommendations":[{{"product_id": 1, "reason": "short reason", "score": 0.0}}]}} '
        f"where score is a confidence from 0.0 to 1.0."
    )


# ---------------------------------------------------------------------------
# Public recommendation flows
# ---------------------------------------------------------------------------

def get_trending_products(limit=8):
    """Deterministic trending ranking (no AI, no persistence)."""
    products = Product.objects.filter(status="active").order_by(
        "-purchase_count", "-views_count", "-created_at"
    )[:limit]

    results = []
    for product in products:
        if product.purchase_count > 0:
            reason = f"Trending · {product.purchase_count} sold"
        elif product.views_count > 0:
            reason = f"Popular · {product.views_count} views"
        else:
            reason = "New arrival"
        results.append({
            "product": product,
            "reason": reason,
            "score": 0.0,
            "source": "trending",
        })
    return results


def get_personalized_recommendations(user, limit=8):
    """Return AI personalized recommendations, cached via ``created_at`` TTL.

    Returns ``(results, used_fallback)`` where ``results`` is a list of dicts
    with ``product``, ``reason``, ``score`` and ``source`` keys.
    """
    now = timezone.now()
    newest = Recommendation.objects.filter(user=user, source="ai").order_by("-created_at").first()
    if newest and (now - newest.created_at).total_seconds() < RECOMMENDATION_TTL_SECONDS:
        cached = (
            Recommendation.objects.filter(user=user, source="ai")
            .select_related("product")
            .order_by("-score", "-created_at")[:limit]
        )
        return _recommendation_dicts(cached, "ai"), False

    context = build_user_context(user)
    candidates = _candidate_products_for_user(user, context["top_categories"])
    catalog = _serialize_catalog(candidates)

    data = call_ai(SYSTEM_PROMPT, _personalized_prompt(context, catalog, limit))
    items = parse_recommendations(data, limit=limit) if data else []

    if not items:
        return _fallback_personalized(context, limit), True

    rows = persist_recommendations(user, items, "ai")
    return _recommendation_dicts(rows, "ai"), False


def get_similar_products(anchor, limit=4):
    """Return similar products for an anchor product (AI + deterministic fallback)."""
    candidates = _candidate_products_similar(anchor)
    if not candidates:
        return [], True

    catalog = _serialize_catalog(candidates)
    data = call_ai(SYSTEM_PROMPT, _similar_prompt(anchor, catalog, limit))
    items = parse_recommendations(data, limit=limit) if data else []

    if not items:
        return _fallback_similar(anchor, candidates, limit), True

    by_id = {product.pk: product for product in candidates}
    results = []
    for item in items:
        product = by_id.get(item["product_id"])
        if product is None:
            continue
        results.append({
            "product": product,
            "reason": item["reason"] or _similar_reason(anchor, product),
            "score": item["score"],
            "source": "similar",
        })
    return results, False


# ---------------------------------------------------------------------------
# Fallbacks
# ---------------------------------------------------------------------------

def _fallback_personalized(context, limit):
    products = []
    if context["top_categories"]:
        products = list(
            Product.objects.filter(
                status="active", stock__gt=0, category__name__in=context["top_categories"]
            ).order_by("-purchase_count", "-views_count")[:limit]
        )

    if len(products) < limit:
        fill = (
            Product.objects.filter(status="active", stock__gt=0)
            .exclude(pk__in=[p.pk for p in products])
            .order_by("-purchase_count", "-views_count")[: limit - len(products)]
        )
        products += list(fill)

    results = []
    for product in products:
        reason = "Popular in your interests" if context["top_categories"] else "Popular right now"
        results.append({"product": product, "reason": reason, "score": 0.0, "source": "ai"})
    return results


def _fallback_similar(anchor, candidates, limit):
    results = []
    for product in candidates[:limit]:
        results.append({
            "product": product,
            "reason": _similar_reason(anchor, product),
            "score": 0.0,
            "source": "similar",
        })
    return results


def _similar_reason(anchor, product):
    if anchor.category and product.category and anchor.category == product.category:
        return f"Same category · {product.category.name}"
    return "Similar product"


def _recommendation_dicts(rows, source):
    return [
        {
            "product": row.product,
            "reason": row.reason,
            "score": row.score,
            "source": source,
        }
        for row in rows
    ]
