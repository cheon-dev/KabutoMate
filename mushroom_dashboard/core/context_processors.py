from .models import Cart, CustomerAdminMessage, Notification


def customer_navigation(request):
    """Expose the small set of counts used by the customer navigation shell."""
    is_customer = request.user.is_authenticated and not (
        request.user.is_staff or getattr(getattr(request.user, 'profile', None), 'is_admin', False)
    )

    cart_count = 0
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
        cart_count = cart.items.count() if cart else 0
    elif request.session.session_key:
        cart = Cart.objects.filter(session_key=request.session.session_key).first()
        cart_count = cart.items.count() if cart else 0

    unread_notification_count = 0
    unread_support_count = 0
    if is_customer:
        unread_notification_count = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
        unread_support_count = CustomerAdminMessage.objects.filter(
            customer=request.user,
            sender__profile__role='ADMIN',
            is_read=False,
        ).count()

    return {
        'customer_nav_visible': not request.user.is_authenticated or is_customer,
        'customer_cart_count': cart_count,
        'customer_unread_notification_count': unread_notification_count,
        'customer_unread_support_count': unread_support_count,
    }
