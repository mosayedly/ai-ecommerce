import json

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from .forms import CheckoutForm, RegisterForm
from .models import Cart, CartItem, Category, Order, OrderItem, Product, UserActivity
from .services import (
    get_personalized_recommendations,
    get_similar_products,
    get_trending_products,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_or_create_cart(user):
    """Return the user's cart, creating one if it does not exist yet."""
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def cart_payload(cart):
    """Serialize a cart (and its items) into a JSON-friendly dict."""
    items = []
    for item in cart.items.select_related("product").all():
        items.append({
            "id": item.id,
            "product_id": item.product_id,
            "name": item.product.name,
            "slug": item.product.slug,
            "url": reverse("product_detail", args=[item.product.slug]),
            "image": item.product.image.url if item.product.image else "",
            "price": str(item.product.price),
            "quantity": item.quantity,
            "subtotal": str(item.subtotal),
            "stock": item.product.stock,
        })

    return {
        "success": True,
        "cart": {
            "count": sum(item["quantity"] for item in items),
            "item_count": len(items),
            "items": items,
            "total": str(cart.total),
        },
    }


# ---------------------------------------------------------------------------
# Accounts (FR-1)
# ---------------------------------------------------------------------------

def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! Your account has been created.")
            return redirect("home")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    next_url = request.POST.get("next") or request.GET.get("next") or ""

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}
            ):
                return redirect(next_url)
            return redirect("home")
    else:
        form = AuthenticationForm(request)

    return render(request, "accounts/login.html", {"form": form, "next": next_url})


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("home")


# ---------------------------------------------------------------------------
# Catalog (FR-2 / FR-3)
# ---------------------------------------------------------------------------

def home(request):
    featured = Product.objects.filter(status="active", is_featured=True)[:8]
    trending = get_trending_products(limit=8)

    personalized = []
    personalized_fallback = False
    if request.user.is_authenticated:
        personalized, personalized_fallback = get_personalized_recommendations(
            request.user, limit=8
        )

    return render(
        request,
        "store/home.html",
        {
            "featured": featured,
            "trending": trending,
            "personalized": personalized,
            "personalized_fallback": personalized_fallback,
        },
    )


def product_list(request):
    products = Product.objects.filter(status="active").select_related("category")

    q = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "").strip()

    if q:
        products = products.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if category_slug:
        products = products.filter(category__slug=category_slug)

    if q and request.user.is_authenticated:
        UserActivity.objects.create(
            user=request.user,
            activity_type="search",
            metadata={"query": q, "category": category_slug},
        )

    categories = Category.objects.all()
    paginator = Paginator(products.order_by("-created_at"), 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "store/product_list.html",
        {
            "page_obj": page_obj,
            "categories": categories,
            "q": q,
            "active_category": category_slug,
            "category": None,
        },
    )


def category_products(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(status="active", category=category).select_related(
        "category"
    )

    if request.user.is_authenticated:
        UserActivity.objects.create(
            user=request.user, category=category, activity_type="category_view"
        )

    paginator = Paginator(products.order_by("-created_at"), 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "store/product_list.html",
        {
            "page_obj": page_obj,
            "categories": Category.objects.all(),
            "category": category,
            "active_category": category.slug,
            "q": "",
        },
    )


def product_detail(request, slug):
    product = get_object_or_404(Product.objects.select_related("category"), slug=slug)

    # Increment the global view counter atomically, then refresh the instance.
    Product.objects.filter(pk=product.pk).update(views_count=F("views_count") + 1)
    product.refresh_from_db()

    similar, similar_fallback = get_similar_products(product, limit=4)

    if request.user.is_authenticated:
        UserActivity.objects.create(
            user=request.user, product=product, activity_type="view"
        )

    return render(
        request,
        "store/product_detail.html",
        {
            "product": product,
            "similar": similar,
            "similar_fallback": similar_fallback,
        },
    )


# ---------------------------------------------------------------------------
# Cart (FR-4)
# ---------------------------------------------------------------------------

@login_required
def cart_detail(request):
    cart = get_or_create_cart(request.user)
    items = cart.items.select_related("product").all()
    return render(request, "store/cart.html", {"cart": cart, "items": items})


@login_required
@require_GET
def cart_api(request):
    cart = get_or_create_cart(request.user)
    return JsonResponse(cart_payload(cart))


@login_required
@require_POST
def cart_api_add(request):
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON."}, status=400)

    try:
        product_id = int(data.get("product_id"))
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "error": "Invalid product id."}, status=400)

    try:
        quantity = int(data.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1

    if quantity < 1 or quantity > 100:
        return JsonResponse(
            {"success": False, "error": "Quantity must be between 1 and 100."},
            status=400,
        )

    product = get_object_or_404(Product, pk=product_id, status="active")

    cart = get_or_create_cart(request.user)
    item = CartItem.objects.filter(cart=cart, product=product).first()

    new_quantity = (item.quantity if item else 0) + quantity
    if new_quantity > product.stock:
        return JsonResponse(
            {"success": False, "error": "Not enough stock available."},
            status=400,
        )

    if item:
        item.quantity = new_quantity
        item.save()
    else:
        CartItem.objects.create(cart=cart, product=product, quantity=new_quantity)

    UserActivity.objects.create(
        user=request.user, product=product, activity_type="add_to_cart"
    )

    return JsonResponse(cart_payload(cart))


@login_required
@require_POST
def cart_api_update(request):
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON."}, status=400)

    try:
        item_id = int(data.get("item_id"))
        quantity = int(data.get("quantity"))
    except (TypeError, ValueError):
        return JsonResponse(
            {"success": False, "error": "Invalid item id or quantity."},
            status=400,
        )

    if quantity < 1 or quantity > 100:
        return JsonResponse(
            {"success": False, "error": "Quantity must be between 1 and 100."},
            status=400,
        )

    cart = get_or_create_cart(request.user)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)

    if quantity > item.product.stock:
        return JsonResponse(
            {"success": False, "error": "Not enough stock available."},
            status=400,
        )

    item.quantity = quantity
    item.save()

    return JsonResponse(cart_payload(cart))


@login_required
@require_POST
def cart_api_remove(request):
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON."}, status=400)

    try:
        item_id = int(data.get("item_id"))
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "error": "Invalid item id."}, status=400)

    cart = get_or_create_cart(request.user)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    product = item.product
    item.delete()

    UserActivity.objects.create(
        user=request.user, product=product, activity_type="remove_from_cart"
    )

    return JsonResponse(cart_payload(cart))


# ---------------------------------------------------------------------------
# Orders (FR-5)
# ---------------------------------------------------------------------------

@login_required
def checkout(request):
    cart = get_or_create_cart(request.user)
    items = cart.items.select_related("product").all()

    if not items:
        messages.warning(request, "Your cart is empty.")
        return redirect("cart_detail")

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            insufficient = [item for item in items if item.quantity > item.product.stock]
            if insufficient:
                names = ", ".join(item.product.name for item in insufficient)
                form.add_error(None, f"Not enough stock for: {names}.")
            else:
                with transaction.atomic():
                    order = Order.objects.create(
                        user=request.user,
                        shipping_address=form.cleaned_data["shipping_address"],
                        notes=form.cleaned_data["notes"],
                    )
                    for item in items:
                        OrderItem.objects.create(
                            order=order,
                            product=item.product,
                            quantity=item.quantity,
                            price=item.product.price,
                        )
                        Product.objects.filter(pk=item.product.pk).update(
                            stock=F("stock") - item.quantity,
                            purchase_count=F("purchase_count") + item.quantity,
                        )
                        UserActivity.objects.create(
                            user=request.user,
                            product=item.product,
                            activity_type="purchase",
                        )
                    order.recalculate_total()
                    cart.items.all().delete()

                messages.success(request, f"Order {order.order_number} placed successfully!")
                return redirect("order_detail", order_number=order.order_number)
    else:
        form = CheckoutForm()

    return render(
        request,
        "store/checkout.html",
        {"form": form, "cart": cart, "items": items},
    )


@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "store/order_history.html", {"orders": orders})


@login_required
def order_detail(request, order_number):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),
        order_number=order_number,
        user=request.user,
    )
    return render(request, "store/order_detail.html", {"order": order})


# ---------------------------------------------------------------------------
# Recommendations (FR-6)
# ---------------------------------------------------------------------------

@login_required
def recommendations(request):
    personalized, personalized_fallback = get_personalized_recommendations(
        request.user, limit=12
    )
    trending = get_trending_products(limit=8)
    return render(
        request,
        "store/recommendations.html",
        {
            "personalized": personalized,
            "personalized_fallback": personalized_fallback,
            "trending": trending,
        },
    )


@login_required
@require_POST
def recommendation_click(request):
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON."}, status=400)

    try:
        product_id = int(data.get("product_id"))
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "error": "Invalid product id."}, status=400)

    source = str(data.get("source", "ai"))[:30]
    product = get_object_or_404(Product, pk=product_id)

    UserActivity.objects.create(
        user=request.user,
        product=product,
        activity_type="recommendation_click",
        metadata={"source": source},
    )

    return JsonResponse({"success": True})
