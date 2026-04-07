from .models import CartItem
from django.db.models import Sum

def cart_renderer(request):
    """
    Returns the total number of items in the cart.
    Supports both DB-based (authenticated) and session-based (guest) carts.
    """
    if request.user.is_authenticated:
        # Sum quantities from CartItem model for logged-in users
        result = CartItem.objects.filter(user=request.user).aggregate(total=Sum('quantity'))
        cart_count = result.get('total') or 0
    else:
        # Sum quantities from session for guests
        cart = request.session.get('cart', {})
        cart_count = sum(item.get('quantity', 0) for item in cart.values())
    
    return {
        'cart_count': cart_count,
        'has_cart_items': cart_count > 0
    }
