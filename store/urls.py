from django.urls import path

from . import views

urlpatterns = [
    # Catalog
    path("", views.home, name="home"),
    path("products/", views.product_list, name="product_list"),
    path("categories/<slug:slug>/", views.category_products, name="category_products"),
    path("products/<slug:slug>/", views.product_detail, name="product_detail"),

    # Cart
    path("cart/", views.cart_detail, name="cart_detail"),
    path("cart/api/", views.cart_api, name="cart_api"),
    path("cart/api/add/", views.cart_api_add, name="cart_api_add"),
    path("cart/api/update/", views.cart_api_update, name="cart_api_update"),
    path("cart/api/remove/", views.cart_api_remove, name="cart_api_remove"),

    # Orders
    path("orders/checkout/", views.checkout, name="checkout"),
    path("orders/", views.order_history, name="order_history"),
    path("orders/<str:order_number>/", views.order_detail, name="order_detail"),

    # Accounts
    path("accounts/register/", views.register, name="register"),
    path("accounts/login/", views.login_view, name="login"),
    path("accounts/logout/", views.logout_view, name="logout"),

    # Recommendations (FR-6)
    path("recommendations/", views.recommendations, name="recommendations"),
    path("recommendations/click/", views.recommendation_click, name="recommendation_click"),
]
