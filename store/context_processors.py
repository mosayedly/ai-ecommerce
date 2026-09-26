from .models import Cart


def cart_context(request):
    """Expose the current user's cart item count to every template."""
    cart_count = 0
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
        if cart:
            cart_count = sum(item.quantity for item in cart.items.all())
    return {"cart_count": cart_count}
