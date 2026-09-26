"""URL routes for the custom admin dashboard (FR: Administrator UI).

Mounted at /dashboard/ from config/urls.py. Django admin (/admin/) is kept as
a fallback tool and is intentionally untouched.
"""

from django.urls import path

from . import admin_views

app_name = "dashboard"

urlpatterns = [
    path("", admin_views.dashboard_home, name="home"),

    # Products
    path("products/", admin_views.product_list, name="product_list"),
    path("products/new/", admin_views.product_create, name="product_create"),
    path("products/<int:pk>/edit/", admin_views.product_edit, name="product_edit"),
    path("products/<int:pk>/delete/", admin_views.product_delete, name="product_delete"),

    # Categories
    path("categories/", admin_views.category_list, name="category_list"),
    path("categories/new/", admin_views.category_create, name="category_create"),
    path("categories/<int:pk>/edit/", admin_views.category_edit, name="category_edit"),
    path("categories/<int:pk>/delete/", admin_views.category_delete, name="category_delete"),

    # Orders
    path("orders/", admin_views.order_list, name="order_list"),
    path("orders/<str:order_number>/", admin_views.order_detail, name="order_detail"),

    # Users
    path("users/", admin_views.user_list, name="user_list"),
    path("users/<int:user_id>/", admin_views.user_detail, name="user_detail"),
    path("users/<int:user_id>/toggle/", admin_views.user_toggle_active, name="user_toggle_active"),

    # Activity log
    path("activities/", admin_views.activity_list, name="activity_list"),
]
