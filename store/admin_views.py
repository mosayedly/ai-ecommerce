"""Views for the custom admin dashboard (separate from Django admin at /admin/).

Phase 1: dashboard home with key metrics.
Phase 2: full CRUD for products and categories.
Includes Order, User and Activity Log management (Phase 3).
"""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, ProtectedError, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .admin_forms import CategoryAdminForm, ProductAdminForm
from .decorators import staff_required
from .models import Category, Order, Product, UserActivity

# Order statuses that count as realized revenue.
REVENUE_STATUSES = ["paid", "processing", "shipped", "delivered"]

# List pages in the dashboard show this many rows per page.
DASHBOARD_PAGE_SIZE = 15

# The activity log is a high-volume feed, so it shows more rows per page.
DASHBOARD_ACTIVITY_PAGE_SIZE = 25


@staff_required
def dashboard_home(request):
    """Admin dashboard home with key metrics."""
    User = get_user_model()
    now = timezone.now()
    last_30_days = now - timedelta(days=30)

    # ----- KPI cards -------------------------------------------------------
    total_products = Product.objects.count()
    active_products = Product.objects.filter(status="active").count()
    total_categories = Category.objects.count()
    total_orders = Order.objects.count()
    total_users = User.objects.count()
    total_revenue = (
        Order.objects.filter(status__in=REVENUE_STATUSES).aggregate(
            total=Sum("total_price")
        )["total"]
        or 0
    )
    recent_activities_count = UserActivity.objects.filter(
        created_at__gte=last_30_days
    ).count()

    # ----- Panels ----------------------------------------------------------
    recent_orders = Order.objects.select_related("user").order_by("-created_at")[:5]
    recent_activities = UserActivity.objects.select_related("user", "product").order_by(
        "-created_at"
    )[:10]
    top_products = Product.objects.filter(status="active").order_by("-purchase_count")[:5]

    # Orders by status, enriched with labels and bar widths for the CSS chart.
    status_counts = {
        row["status"]: row["count"]
        for row in Order.objects.values("status").annotate(count=Count("id"))
    }
    max_status_count = max(status_counts.values(), default=0) or 1
    orders_by_status = [
        {
            "status": value,
            "label": label,
            "count": status_counts.get(value, 0),
            "percent": round(100 * status_counts.get(value, 0) / max_status_count),
        }
        for value, label in Order.STATUS_CHOICES
    ]

    context = {
        "active_section": "home",
        "total_products": total_products,
        "active_products": active_products,
        "total_categories": total_categories,
        "total_orders": total_orders,
        "total_users": total_users,
        "total_revenue": total_revenue,
        "recent_activities_count": recent_activities_count,
        "recent_orders": recent_orders,
        "recent_activities": recent_activities,
        "top_products": top_products,
        "orders_by_status": orders_by_status,
    }
    return render(request, "dashboard/index.html", context)


# ---------------------------------------------------------------------------
# Products (Phase 2)
# ---------------------------------------------------------------------------

@staff_required
def product_list(request):
    """Paginated, filterable list of every product."""
    products = Product.objects.select_related("category").order_by("-created_at")

    q = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "").strip()
    status = request.GET.get("status", "").strip()

    if q:
        products = products.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if category_slug:
        products = products.filter(category__slug=category_slug)
    if status:
        products = products.filter(status=status)

    page_obj = Paginator(products, DASHBOARD_PAGE_SIZE).get_page(request.GET.get("page"))

    context = {
        "active_section": "products",
        "products": page_obj,
        "page_obj": page_obj,
        "categories": Category.objects.order_by("name"),
        "status_choices": Product.STATUS_CHOICES,
        "q": q,
        "selected_category": category_slug,
        "selected_status": status,
    }
    return render(request, "dashboard/products/product_list.html", context)


@staff_required
def product_create(request):
    """Create a product from the dashboard."""
    if request.method == "POST":
        form = ProductAdminForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.name}" was created successfully.')
            return redirect("dashboard:product_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = ProductAdminForm()

    context = {"active_section": "products", "form": form, "form_title": "New Product"}
    return render(request, "dashboard/products/product_form.html", context)


@staff_required
def product_edit(request, pk):
    """Update an existing product."""
    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        form = ProductAdminForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.name}" was updated successfully.')
            return redirect("dashboard:product_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = ProductAdminForm(instance=product)

    context = {
        "active_section": "products",
        "form": form,
        "form_title": "Edit Product",
        "product": product,
    }
    return render(request, "dashboard/products/product_form.html", context)


@staff_required
@require_POST
def product_delete(request, pk):
    """Delete a product (POST only); products referenced by orders are kept."""
    product = get_object_or_404(Product, pk=pk)
    name = product.name
    try:
        product.delete()
    except ProtectedError:
        messages.error(
            request,
            f'Product "{name}" cannot be deleted because existing orders reference it.',
        )
        return redirect("dashboard:product_list")

    messages.success(request, f'Product "{name}" was deleted.')
    return redirect("dashboard:product_list")


# ---------------------------------------------------------------------------
# Categories (Phase 2)
# ---------------------------------------------------------------------------

@staff_required
def category_list(request):
    """Paginated, searchable list of categories with their product counts."""
    categories = Category.objects.annotate(product_count=Count("products")).order_by("name")

    q = request.GET.get("q", "").strip()
    if q:
        categories = categories.filter(Q(name__icontains=q) | Q(description__icontains=q))

    page_obj = Paginator(categories, DASHBOARD_PAGE_SIZE).get_page(request.GET.get("page"))

    context = {
        "active_section": "categories",
        "categories": page_obj,
        "page_obj": page_obj,
        "q": q,
    }
    return render(request, "dashboard/categories/category_list.html", context)


@staff_required
def category_create(request):
    """Create a category from the dashboard."""
    if request.method == "POST":
        form = CategoryAdminForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Category "{category.name}" was created successfully.')
            return redirect("dashboard:category_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = CategoryAdminForm()

    context = {"active_section": "categories", "form": form, "form_title": "New Category"}
    return render(request, "dashboard/categories/category_form.html", context)


@staff_required
def category_edit(request, pk):
    """Update an existing category."""
    category = get_object_or_404(Category, pk=pk)

    if request.method == "POST":
        form = CategoryAdminForm(request.POST, instance=category)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Category "{category.name}" was updated successfully.')
            return redirect("dashboard:category_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = CategoryAdminForm(instance=category)

    context = {
        "active_section": "categories",
        "form": form,
        "form_title": "Edit Category",
        "category": category,
    }
    return render(request, "dashboard/categories/category_form.html", context)


@staff_required
@require_POST
def category_delete(request, pk):
    """Delete a category (POST only).

    ``Product.category`` uses ``on_delete=SET_NULL``, so products that reference
    the category are detached (set to ``None``) instead of being deleted.
    """
    category = get_object_or_404(Category, pk=pk)
    name = category.name
    product_count = category.products.count()

    if product_count:
        category.products.update(category=None)
        messages.warning(
            request,
            f'Category "{name}" was deleted; {product_count} product(s) are now uncategorized.',
        )
    else:
        messages.success(request, f'Category "{name}" was deleted.')

    category.delete()
    return redirect("dashboard:category_list")


# ---------------------------------------------------------------------------
# Orders (Phase 3)
# ---------------------------------------------------------------------------

@staff_required
def order_list(request):
    """Paginated, filterable list of every order with per-status counts."""
    orders = (
        Order.objects.select_related("user")
        .prefetch_related("items__product")
        .order_by("-created_at")
    )

    q = request.GET.get("q", "").strip()
    selected_status = request.GET.get("status", "").strip()
    if selected_status not in dict(Order.STATUS_CHOICES):
        selected_status = ""

    if q:
        orders = orders.filter(
            Q(order_number__icontains=q) | Q(user__username__icontains=q)
        )
    if selected_status:
        orders = orders.filter(status=selected_status)

    page_obj = Paginator(orders, DASHBOARD_PAGE_SIZE).get_page(request.GET.get("page"))

    counts = {
        row["status"]: row["count"]
        for row in Order.objects.values("status").annotate(count=Count("id"))
    }
    status_tabs = [
        {"value": value, "label": label, "count": counts.get(value, 0)}
        for value, label in Order.STATUS_CHOICES
    ]

    context = {
        "active_section": "orders",
        "orders": page_obj,
        "page_obj": page_obj,
        "status_choices": Order.STATUS_CHOICES,
        "status_tabs": status_tabs,
        "total_orders": Order.objects.count(),
        "selected_status": selected_status,
        "q": q,
    }
    return render(request, "dashboard/orders/order_list.html", context)


@staff_required
def order_detail(request, order_number):
    """Order detail; a POST updates the status (POST → redirect → GET)."""
    order = get_object_or_404(
        Order.objects.select_related("user").prefetch_related("items__product"),
        order_number=order_number,
    )
    valid_statuses = dict(Order.STATUS_CHOICES)

    if request.method == "POST":
        new_status = request.POST.get("status", "").strip()
        if new_status not in valid_statuses:
            messages.error(request, "Invalid order status.")
            return redirect("dashboard:order_detail", order_number=order.order_number)

        if new_status == order.status:
            messages.info(request, "The order already has that status.")
            return redirect("dashboard:order_detail", order_number=order.order_number)

        order.status = new_status
        # completed_at marks delivery, so it is kept in sync with the status
        # (an order moved out of "delivered" is no longer complete).
        order.completed_at = timezone.now() if new_status == "delivered" else None
        order.save(update_fields=["status", "completed_at", "updated_at"])
        messages.success(
            request,
            f'Order {order.order_number} updated to "{order.get_status_display()}".',
        )
        return redirect("dashboard:order_detail", order_number=order.order_number)

    context = {
        "active_section": "orders",
        "order": order,
        "status_choices": Order.STATUS_CHOICES,
    }
    return render(request, "dashboard/orders/order_detail.html", context)


# ---------------------------------------------------------------------------
# Users (Phase 3)
# ---------------------------------------------------------------------------

@staff_required
def user_list(request):
    """Paginated, filterable list of accounts with order stats."""
    User = get_user_model()
    users = User.objects.annotate(
        order_count=Count("orders"),
        total_spent=Sum(
            "orders__total_price", filter=Q(orders__status__in=REVENUE_STATUSES)
        ),
    ).order_by("-date_joined")

    q = request.GET.get("q", "").strip()
    selected_is_staff = request.GET.get("is_staff", "").strip().lower()
    selected_is_active = request.GET.get("is_active", "").strip().lower()

    if q:
        users = users.filter(Q(username__icontains=q) | Q(email__icontains=q))
    if selected_is_staff in ("true", "false"):
        users = users.filter(is_staff=(selected_is_staff == "true"))
    else:
        selected_is_staff = ""
    if selected_is_active in ("true", "false"):
        users = users.filter(is_active=(selected_is_active == "true"))
    else:
        selected_is_active = ""

    page_obj = Paginator(users, DASHBOARD_PAGE_SIZE).get_page(request.GET.get("page"))

    context = {
        "active_section": "users",
        "users": page_obj,
        "page_obj": page_obj,
        "q": q,
        "selected_is_staff": selected_is_staff,
        "selected_is_active": selected_is_active,
    }
    return render(request, "dashboard/users/user_list.html", context)


@staff_required
def user_detail(request, user_id):
    """Customer profile with order stats, recent orders and recent activity."""
    User = get_user_model()
    profile_user = get_object_or_404(User, pk=user_id)

    order_count = profile_user.orders.count()
    total_spent = (
        profile_user.orders.filter(status__in=REVENUE_STATUSES).aggregate(
            total=Sum("total_price")
        )["total"]
        or 0
    )
    recent_orders = profile_user.orders.order_by("-created_at")[:5]
    recent_activities = (
        profile_user.user_activities.select_related("product", "category")
        .order_by("-created_at")[:10]
    )

    context = {
        "active_section": "users",
        "profile_user": profile_user,
        "order_count": order_count,
        "total_spent": total_spent,
        "recent_orders": recent_orders,
        "recent_activities": recent_activities,
        "is_self": profile_user.pk == request.user.pk,
    }
    return render(request, "dashboard/users/user_detail.html", context)


@staff_required
@require_POST
def user_toggle_active(request, user_id):
    """Activate or deactivate an account (POST only)."""
    User = get_user_model()
    profile_user = get_object_or_404(User, pk=user_id)

    if profile_user.pk == request.user.pk:
        raise PermissionDenied("You cannot activate or deactivate your own account.")

    profile_user.is_active = not profile_user.is_active
    profile_user.save(update_fields=["is_active"])
    state = "active" if profile_user.is_active else "inactive"
    messages.success(request, f'User "{profile_user.username}" is now {state}.')
    return redirect("dashboard:user_detail", user_id=profile_user.pk)


# ---------------------------------------------------------------------------
# Activity log (Phase 3)
# ---------------------------------------------------------------------------

@staff_required
def activity_list(request):
    """Paginated, filterable log of every recorded user activity."""
    activities = UserActivity.objects.select_related(
        "user", "product", "category"
    ).order_by("-created_at")

    q = request.GET.get("q", "").strip()
    selected_type = request.GET.get("activity_type", "").strip()
    if selected_type not in dict(UserActivity.ACTIVITY_CHOICES):
        selected_type = ""

    if q:
        activities = activities.filter(
            Q(user__username__icontains=q) | Q(product__name__icontains=q)
        )
    if selected_type:
        activities = activities.filter(activity_type=selected_type)

    page_obj = Paginator(activities, DASHBOARD_ACTIVITY_PAGE_SIZE).get_page(
        request.GET.get("page")
    )

    context = {
        "active_section": "activities",
        "activities": page_obj,
        "page_obj": page_obj,
        "activity_types": UserActivity.ACTIVITY_CHOICES,
        "selected_type": selected_type,
        "q": q,
    }
    return render(request, "dashboard/activities/activity_list.html", context)


