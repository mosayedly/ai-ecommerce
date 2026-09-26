from django.contrib import admin

from .models import (
    Cart,
    CartItem,
    Category,
    Order,
    OrderItem,
    Product,
    Recommendation,
    UserActivity,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "product_count", "created_at", "updated_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("name", "slug", "description")
    readonly_fields = ("created_at", "updated_at")
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Products")
    def product_count(self, obj):
        return obj.products.count()


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "price",
        "stock",
        "status",
        "is_featured",
        "views_count",
        "purchase_count",
        "created_at",
    )
    list_filter = ("status", "is_featured", "category", "created_at")
    search_fields = ("name", "slug", "description")
    readonly_fields = ("created_at", "updated_at", "views_count", "purchase_count")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("user", "item_count", "total", "updated_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Items")
    def item_count(self, obj):
        return obj.items.count()


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("cart", "product", "quantity", "subtotal", "created_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("cart__user__username", "product__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "user", "status", "total_price", "created_at", "completed_at")
    list_filter = ("status", "created_at", "completed_at")
    search_fields = ("order_number", "user__username", "user__email", "shipping_address")
    readonly_fields = ("order_number", "created_at", "updated_at", "completed_at")
    list_editable = ("status",)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product", "quantity", "price", "subtotal", "created_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("order__order_number", "product__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ("user", "activity_type", "product", "category", "created_at")
    list_filter = ("activity_type", "created_at")
    search_fields = ("user__username", "product__name", "category__name")
    readonly_fields = ("created_at",)


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "source", "score", "reason", "created_at")
    list_filter = ("source", "created_at")
    search_fields = ("user__username", "product__name", "reason")
    readonly_fields = ("created_at",)

