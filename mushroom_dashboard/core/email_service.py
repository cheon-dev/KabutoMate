"""
Email Service for Mushroom Farm Dashboard
Handles all email sending functionality including:
- Email verification for registration
- Order status notifications for customers
- New order notifications for admin
"""

import logging
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from threading import Thread
from .models import NotificationLog, NotificationSettings

logger = logging.getLogger(__name__)


def _log_notification_email(notification_type, recipient, subject, status, error_message='', metadata=None):
    try:
        NotificationLog.objects.create(
            notification_type=notification_type,
            recipient=recipient or '',
            subject=subject,
            channel='email',
            status=status,
            error_message=error_message or '',
            metadata=metadata or {},
        )
    except Exception as exc:
        logger.error(f"Failed to write notification log: {exc}")


def _email_notifications_enabled():
    try:
        return NotificationSettings.load().email_enabled
    except Exception:
        return True


def send_email_async(email_function, *args, **kwargs):
    """
    Wrapper to send emails in a background thread.
    This prevents email sending from slowing down the main request.
    """
    def send():
        try:
            email_function(*args, **kwargs)
        except Exception as e:
            logger.error(f"Async email sending failed: {str(e)}")
    
    thread = Thread(target=send)
    thread.start()


def send_verification_email(user, request=None):
    """
    Send email verification link to a newly registered user.
    
    Args:
        user: User object with profile containing verification token
        request: Optional HttpRequest object to build absolute URL
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        if not _email_notifications_enabled():
            logger.info("Email notifications are disabled; skipping verification email")
            return False

        profile = user.profile
        token = profile.generate_verification_token()
        
        # Build verification URL
        if request:
            base_url = request.build_absolute_uri('/')[:-1]  # Remove trailing slash
        else:
            base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        
        verification_url = f"{base_url}/verify-email/{token}/"
        
        subject = "Verify Your Email - Mushroom Farm"
        
        # HTML email content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #2e7d32, #4caf50); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border: 1px solid #e0e0e0; }}
                .button {{ display: inline-block; background: #4caf50; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; }}
                .button:hover {{ background: #388e3c; }}
                .footer {{ background: #333; color: #aaa; padding: 20px; text-align: center; font-size: 12px; border-radius: 0 0 10px 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🍄 Welcome to Mushroom Farm!</h1>
                </div>
                <div class="content">
                    <h2>Hello, {user.first_name or user.username}!</h2>
                    <p>Thank you for registering at Mushroom Farm. To complete your registration and start shopping, please verify your email address.</p>
                    
                    <p style="text-align: center;">
                        <a href="{verification_url}" class="button">Verify My Email</a>
                    </p>
                    
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; background: #fff; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">{verification_url}</p>
                    
                    <p><strong>Note:</strong> This verification link will expire in 24 hours.</p>
                    
                    <p>If you didn't create an account with us, please ignore this email.</p>
                </div>
                <div class="footer">
                    <p>&copy; {timezone.now().year} Mushroom Farm. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text version
        plain_content = f"""
Hello {user.first_name or user.username}!

Thank you for registering at Mushroom Farm. To complete your registration, please verify your email by clicking the link below:

{verification_url}

This link will expire in 24 hours.

If you didn't create an account with us, please ignore this email.

Best regards,
Mushroom Farm Team
        """
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        _log_notification_email('email_verification', user.email, subject, 'SUCCESS', metadata={'user_id': user.id})
        
        logger.info(f"Verification email sent to {user.email}")
        return True
        
    except Exception as e:
        _log_notification_email('email_verification', user.email, 'Verify Your Email - Mushroom Farm', 'FAILED', error_message=str(e), metadata={'user_id': getattr(user, 'id', None)})
        logger.error(f"Failed to send verification email to {user.email}: {str(e)}")
        return False


def send_order_status_email(order, old_status=None):
    """
    Send order status update notification to customer.
    
    Args:
        order: Order object with updated status
        old_status: Previous status (optional, for comparison)
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        if not _email_notifications_enabled():
            logger.info("Email notifications are disabled; skipping order status email")
            return False

        # Status display names and colors
        status_info = {
            'PENDING': {'name': 'Pending', 'color': '#ff9800', 'icon': '⏳'},
            'PROCESSING': {'name': 'Processing', 'color': '#2196f3', 'icon': '📦'},
            'SHIPPED': {'name': 'Shipped', 'color': '#9c27b0', 'icon': '🚚'},
            'DELIVERED': {'name': 'Delivered', 'color': '#4caf50', 'icon': '✅'},
            'CANCELLED': {'name': 'Cancelled', 'color': '#f44336', 'icon': '❌'},
        }
        
        current_status = status_info.get(order.status, {'name': order.status, 'color': '#666', 'icon': '📋'})
        
        # Get order items
        order_items = order.items.select_related('product').all()
        items_html = ""
        items_plain = ""
        for item in order_items:
            items_html += f"<tr><td>{item.product.name}</td><td>{item.quantity_kg} {item.unit}</td><td>₱{item.subtotal:.2f}</td></tr>"
            items_plain += f"  - {item.product.name}: {item.quantity_kg} {item.unit} - ₱{item.subtotal:.2f}\n"
        
        subject = f"Order {order.order_number} Status Update: {current_status['name']}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #2e7d32, #4caf50); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border: 1px solid #e0e0e0; }}
                .status-badge {{ display: inline-block; background: {current_status['color']}; color: white; padding: 10px 20px; border-radius: 25px; font-size: 18px; font-weight: bold; margin: 15px 0; }}
                .order-details {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .order-details table {{ width: 100%; border-collapse: collapse; }}
                .order-details th, .order-details td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
                .order-details th {{ background: #f5f5f5; }}
                .total {{ font-size: 20px; font-weight: bold; color: #2e7d32; text-align: right; padding: 15px 0; }}
                .footer {{ background: #333; color: #aaa; padding: 20px; text-align: center; font-size: 12px; border-radius: 0 0 10px 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🍄 Order Status Update</h1>
                </div>
                <div class="content">
                    <h2>Hello, {order.customer_name}!</h2>
                    <p>Your order status has been updated:</p>
                    
                    <p style="text-align: center;">
                        <span class="status-badge">{current_status['icon']} {current_status['name']}</span>
                    </p>
                    
                    <div class="order-details">
                        <h3>Order Details</h3>
                        <p><strong>Order Number:</strong> {order.order_number}</p>
                        <p><strong>Order Date:</strong> {order.created_at.strftime('%B %d, %Y at %I:%M %p')}</p>
                        <p><strong>Status Updated:</strong> {timezone.now().strftime('%B %d, %Y at %I:%M %p')}</p>
                        
                        <h4>Items:</h4>
                        <table>
                            <tr><th>Product</th><th>Quantity</th><th>Price</th></tr>
                            {items_html}
                        </table>
                        
                        <p class="total">Total: ₱{order.total_amount:.2f}</p>
                    </div>
                    
                    <p><strong>Shipping Address:</strong><br>
                    {order.shipping_address}<br>
                    {order.shipping_city} {order.shipping_postal_code}</p>
                    
                    {"<p><em>Thank you for your order! It is being prepared for delivery.</em></p>" if order.status == 'PROCESSING' else ""}
                    {"<p><em>Your order is on its way! Please expect delivery soon.</em></p>" if order.status == 'SHIPPED' else ""}
                    {"<p><em>Your order has been delivered. Thank you for shopping with us!</em></p>" if order.status == 'DELIVERED' else ""}
                    {"<p><em>Your order has been cancelled. If you have questions, please contact us.</em></p>" if order.status == 'CANCELLED' else ""}
                </div>
                <div class="footer">
                    <p>&copy; {timezone.now().year} Mushroom Farm. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        plain_content = f"""
Hello {order.customer_name}!

Your order status has been updated.

ORDER STATUS: {current_status['name']}

Order Details:
- Order Number: {order.order_number}
- Order Date: {order.created_at.strftime('%B %d, %Y at %I:%M %p')}
- Status Updated: {timezone.now().strftime('%B %d, %Y at %I:%M %p')}

Items:
{items_plain}
Total: ₱{order.total_amount:.2f}

Shipping Address:
{order.shipping_address}
{order.shipping_city} {order.shipping_postal_code}

Thank you for shopping with Mushroom Farm!

Best regards,
Mushroom Farm Team
        """
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.customer_email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        _log_notification_email('order_status_update', order.customer_email, subject, 'SUCCESS', metadata={'order_number': order.order_number, 'old_status': old_status, 'new_status': order.status})
        
        logger.info(f"Order status email sent to {order.customer_email} for order {order.order_number}")
        return True
        
    except Exception as e:
        _log_notification_email('order_status_update', order.customer_email, f"Order {order.order_number} Status Update", 'FAILED', error_message=str(e), metadata={'order_number': order.order_number, 'old_status': old_status, 'new_status': getattr(order, 'status', None)})
        logger.error(f"Failed to send order status email for {order.order_number}: {str(e)}")
        return False


def send_new_order_admin_notification(order):
    """
    Send notification to admin when a new order is placed.
    
    Args:
        order: Newly created Order object
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        if not _email_notifications_enabled():
            logger.info("Email notifications are disabled; skipping admin order notification")
            return False

        admin_email = getattr(settings, 'ADMIN_EMAIL', None)
        if not admin_email:
            logger.warning("ADMIN_EMAIL not configured in settings, skipping admin notification")
            return False
        
        # Get order items
        order_items = order.items.select_related('product').all()
        items_html = ""
        items_plain = ""
        for item in order_items:
            items_html += f"<tr><td>{item.product.name}</td><td>{item.quantity_kg} {item.unit}</td><td>₱{item.subtotal:.2f}</td></tr>"
            items_plain += f"  - {item.product.name}: {item.quantity_kg} {item.unit} - ₱{item.subtotal:.2f}\n"
        
        subject = f"🛒 New Order Received: {order.order_number} - ₱{order.total_amount:.2f}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #1565c0, #42a5f5); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border: 1px solid #e0e0e0; }}
                .alert-box {{ background: #fff3e0; border-left: 4px solid #ff9800; padding: 15px; margin: 15px 0; border-radius: 4px; }}
                .customer-info {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .order-details {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .order-details table {{ width: 100%; border-collapse: collapse; }}
                .order-details th, .order-details td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
                .order-details th {{ background: #e3f2fd; }}
                .total {{ font-size: 24px; font-weight: bold; color: #1565c0; text-align: center; padding: 20px; background: #e3f2fd; border-radius: 8px; margin: 15px 0; }}
                .button {{ display: inline-block; background: #1565c0; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; margin: 10px 5px; font-weight: bold; }}
                .footer {{ background: #333; color: #aaa; padding: 20px; text-align: center; font-size: 12px; border-radius: 0 0 10px 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🛒 New Order Received!</h1>
                    <p>Order #{order.order_number}</p>
                </div>
                <div class="content">
                    <div class="alert-box">
                        <strong>⚡ Action Required:</strong> A new order has been placed and requires processing.
                    </div>
                    
                    <div class="total">
                        Total Amount: ₱{order.total_amount:.2f}
                    </div>
                    
                    <div class="customer-info">
                        <h3>👤 Customer Information</h3>
                        <p><strong>Name:</strong> {order.customer_name}</p>
                        <p><strong>Email:</strong> {order.customer_email}</p>
                        <p><strong>Phone:</strong> {order.customer_phone}</p>
                        <p><strong>Address:</strong><br>
                        {order.shipping_address}<br>
                        {order.shipping_city} {order.shipping_postal_code}</p>
                        {"<p><strong>Customer Notes:</strong> " + order.customer_notes + "</p>" if order.customer_notes else ""}
                    </div>
                    
                    <div class="order-details">
                        <h3>📦 Order Items</h3>
                        <table>
                            <tr><th>Product</th><th>Quantity</th><th>Price</th></tr>
                            {items_html}
                        </table>
                    </div>
                    
                    <p><strong>Order Time:</strong> {order.created_at.strftime('%B %d, %Y at %I:%M %p')}</p>
                    <p><strong>Payment Method:</strong> {order.payment_method}</p>
                    
                    <p style="text-align: center; margin-top: 30px;">
                        <em>Log in to the admin dashboard to process this order.</em>
                    </p>
                </div>
                <div class="footer">
                    <p>&copy; {timezone.now().year} Mushroom Farm Admin System</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        plain_content = f"""
NEW ORDER RECEIVED!

Order Number: {order.order_number}
Total Amount: ₱{order.total_amount:.2f}

Customer Information:
- Name: {order.customer_name}
- Email: {order.customer_email}
- Phone: {order.customer_phone}
- Address: {order.shipping_address}, {order.shipping_city} {order.shipping_postal_code}

Order Items:
{items_plain}

Order Time: {order.created_at.strftime('%B %d, %Y at %I:%M %p')}
Payment Method: {order.payment_method}

Please log in to the admin dashboard to process this order.

-- Mushroom Farm System
        """
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[admin_email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        _log_notification_email('new_order_admin', admin_email, subject, 'SUCCESS', metadata={'order_number': order.order_number})
        
        logger.info(f"Admin notification sent for new order {order.order_number}")
        return True
        
    except Exception as e:
        _log_notification_email('new_order_admin', admin_email if 'admin_email' in locals() else '', subject if 'subject' in locals() else f'New Order {getattr(order, "order_number", "")}', 'FAILED', error_message=str(e), metadata={'order_number': getattr(order, 'order_number', None)})
        logger.error(f"Failed to send admin notification for order {order.order_number}: {str(e)}")
        return False


def send_order_confirmation_email(order):
    """
    Send order confirmation email to customer after successful order placement.
    
    Args:
        order: Newly created Order object
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        if not _email_notifications_enabled():
            logger.info("Email notifications are disabled; skipping order confirmation email")
            return False

        # Get order items
        order_items = order.items.select_related('product').all()
        items_html = ""
        items_plain = ""
        for item in order_items:
            items_html += f"<tr><td>{item.product.name}</td><td>{item.quantity_kg} {item.unit}</td><td>₱{item.subtotal:.2f}</td></tr>"
            items_plain += f"  - {item.product.name}: {item.quantity_kg} {item.unit} - ₱{item.subtotal:.2f}\n"
        
        subject = f"Order Confirmed: {order.order_number} - Mushroom Farm"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #2e7d32, #4caf50); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border: 1px solid #e0e0e0; }}
                .success-badge {{ display: inline-block; background: #4caf50; color: white; padding: 10px 20px; border-radius: 25px; font-size: 18px; font-weight: bold; margin: 15px 0; }}
                .order-number {{ background: #e8f5e9; border: 2px solid #4caf50; padding: 15px; text-align: center; border-radius: 8px; margin: 20px 0; }}
                .order-number h2 {{ margin: 0; color: #2e7d32; }}
                .order-details {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .order-details table {{ width: 100%; border-collapse: collapse; }}
                .order-details th, .order-details td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
                .order-details th {{ background: #f5f5f5; }}
                .total {{ font-size: 20px; font-weight: bold; color: #2e7d32; text-align: right; padding: 15px 0; }}
                .footer {{ background: #333; color: #aaa; padding: 20px; text-align: center; font-size: 12px; border-radius: 0 0 10px 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🍄 Order Confirmed!</h1>
                </div>
                <div class="content">
                    <h2>Thank you for your order, {order.customer_name}!</h2>
                    
                    <p style="text-align: center;">
                        <span class="success-badge">✅ Order Received</span>
                    </p>
                    
                    <div class="order-number">
                        <p style="margin: 0; color: #666;">Your Order Number:</p>
                        <h2>{order.order_number}</h2>
                    </div>
                    
                    <div class="order-details">
                        <h3>Order Summary</h3>
                        <table>
                            <tr><th>Product</th><th>Quantity</th><th>Price</th></tr>
                            {items_html}
                        </table>
                        
                        <p class="total">Total: ₱{order.total_amount:.2f}</p>
                    </div>
                    
                    <p><strong>Shipping Address:</strong><br>
                    {order.shipping_address}<br>
                    {order.shipping_city} {order.shipping_postal_code}</p>
                    
                    <p><strong>Payment Method:</strong> {order.payment_method}</p>
                    
                    <p><em>We will send you another email when your order status is updated.</em></p>
                </div>
                <div class="footer">
                    <p>&copy; {timezone.now().year} Mushroom Farm. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        plain_content = f"""
Thank you for your order, {order.customer_name}!

Your order has been received and is being processed.

Order Number: {order.order_number}

Order Summary:
{items_plain}
Total: ₱{order.total_amount:.2f}

Shipping Address:
{order.shipping_address}
{order.shipping_city} {order.shipping_postal_code}

Payment Method: {order.payment_method}

We will send you another email when your order status is updated.

Thank you for shopping with Mushroom Farm!

Best regards,
Mushroom Farm Team
        """
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.customer_email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        _log_notification_email('order_confirmation', order.customer_email, subject, 'SUCCESS', metadata={'order_number': order.order_number})
        
        logger.info(f"Order confirmation email sent to {order.customer_email} for order {order.order_number}")
        return True
        
    except Exception as e:
        _log_notification_email('order_confirmation', order.customer_email, subject if 'subject' in locals() else f'Order Confirmed: {getattr(order, "order_number", "")}', 'FAILED', error_message=str(e), metadata={'order_number': getattr(order, 'order_number', None)})
        logger.error(f"Failed to send order confirmation email for {order.order_number}: {str(e)}")
        return False


def resend_verification_email(user, request=None):
    """
    Resend verification email to existing unverified user.
    
    Args:
        user: User object
        request: Optional HttpRequest object to build absolute URL
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    if user.profile.is_email_verified:
        logger.info(f"User {user.email} is already verified")
        return False
    
    return send_verification_email(user, request)
