"""
E-commerce and POS Views
Handles customer-facing shop and staff POS system
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Q, Sum
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from decimal import Decimal, InvalidOperation
import os
import logging
from .models import Product, Sale, Order, OrderItem, Cart, CartItem, Notification
from .views import admin_required  # Import the admin_required decorator
from .email_service import (
    send_new_order_admin_notification, 
    send_order_confirmation_email, 
    send_order_status_email,
    send_email_async
)
import json

logger = logging.getLogger(__name__)


# ==================== E-COMMERCE VIEWS ====================

def product_detail(request, product_id):
    """Product detail page"""
    product = get_object_or_404(Product.objects.prefetch_related('images'), id=product_id, is_active=True)
    
    context = {
        'product': product,
    }
    
    return render(request, 'product_detail.html', context)

def shop(request):
    """Customer-facing shop page"""
    products = Product.objects.filter(is_active=True, stock_kg__gt=0).prefetch_related('images').order_by('name')
    best_sellers = (
        Product.objects.filter(is_active=True)
        .prefetch_related('images')
        .annotate(total_sold=Sum('sale__quantity_kg', filter=Q(sale__sale_type='ECOMMERCE')))
        .filter(total_sold__gt=0)
        .order_by('-total_sold', 'name')[:4]
    )
    
    # Get product type filter from query params (optional server-side filter)
    product_type_filter = request.GET.get('type')
    if product_type_filter and product_type_filter in ['fresh', 'cooked', 'fruit_bags']:
        products = products.filter(product_type=product_type_filter)
    
    # Get cart count - check both user and session carts
    cart_count = 0
    if request.user.is_authenticated:
        # For logged-in users, use user-based cart
        try:
            cart = Cart.objects.get(user=request.user)
            cart_count = cart.items.count()
        except Cart.DoesNotExist:
            pass
    elif request.session.session_key:
        # For anonymous users, use session-based cart
        try:
            cart = Cart.objects.get(session_key=request.session.session_key)
            cart_count = cart.items.count()
        except Cart.DoesNotExist:
            pass
    
    context = {
        'products': products,
        'best_sellers': best_sellers,
        'cart_count': cart_count,
    }
    return render(request, 'shop.html', context)


def add_to_cart(request, product_id):
    """Add product to cart"""
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id, is_active=True)
        quantity_kg = Decimal(request.POST.get('quantity_kg', 1))
        
        # Validate quantity
        if quantity_kg <= 0:
            messages.error(request, 'Invalid quantity')
            return redirect('shop')
        
        if quantity_kg > product.stock_kg:
            messages.error(request, f'Only {product.stock_kg}{" kg" if product.unit == "kg" else ""} available in stock')
            return redirect('shop')
        
        # Get or create cart based on user authentication
        if request.user.is_authenticated:
            # For logged-in users, use user-based cart
            cart, created = Cart.objects.get_or_create(
                user=request.user,
                defaults={'session_key': f'user_{request.user.id}_{request.user.username}'}
            )
        else:
            # For anonymous users, use session-based cart
            if not request.session.session_key:
                request.session.create()
            cart, created = Cart.objects.get_or_create(
                session_key=request.session.session_key,
                defaults={'user': None}
            )
        
        # Add or update cart item
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity_kg': quantity_kg}
        )
        
        if not created:
            # Update existing cart item
            new_quantity = cart_item.quantity_kg + quantity_kg
            if new_quantity > product.stock_kg:
                messages.error(request, f'Only {product.stock_kg}{" kg" if product.unit == "kg" else ""} available in stock')
                return redirect('shop')
            cart_item.quantity_kg = new_quantity
            cart_item.save()
        
        messages.success(request, f'Added {quantity_kg} {product.unit} of {product.name} to cart')
        return redirect('shop')
    
    return redirect('shop')


@csrf_exempt
def add_to_cart_api(request):
    """AJAX API endpoint for adding products to cart"""
    if request.method == 'POST':
        try:
            # Parse JSON body
            data = json.loads(request.body)
            product_id = data.get('product_id')
            quantity = Decimal(str(data.get('quantity', 1)))
            
            product = get_object_or_404(Product, id=product_id, is_active=True)
            
            # Validate quantity
            if quantity <= 0:
                return JsonResponse({'success': False, 'message': 'Invalid quantity'}, status=400)
            
            if quantity > product.stock_kg:
                return JsonResponse({
                    'success': False, 
                    'message': f'Only {product.stock_kg}{" kg" if product.unit == "kg" else ""} available in stock'
                }, status=400)
            
            # Get or create cart based on user authentication
            if request.user.is_authenticated:
                cart, created = Cart.objects.get_or_create(
                    user=request.user,
                    defaults={'session_key': f'user_{request.user.id}_{request.user.username}'}
                )
            else:
                if not request.session.session_key:
                    request.session.create()
                cart, created = Cart.objects.get_or_create(
                    session_key=request.session.session_key,
                    defaults={'user': None}
                )
            
            # Add or update cart item
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                defaults={'quantity_kg': quantity}
            )
            
            if not created:
                new_quantity = cart_item.quantity_kg + quantity
                if new_quantity > product.stock_kg:
                    return JsonResponse({
                        'success': False,
                        'message': f'Only {product.stock_kg}{" kg" if product.unit == "kg" else ""} available in stock'
                    }, status=400)
                cart_item.quantity_kg = new_quantity
                cart_item.save()
            
            # Get updated cart count
            cart_count = cart.items.count()
            
            return JsonResponse({
                'success': True,
                'message': f'Added {quantity} {product.unit} of {product.name} to cart',
                'cart_count': cart_count
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)


def view_cart(request):
    """View shopping cart"""
    from .models import StoreSettings
    
    cart_items = []
    cart = None
    total = Decimal('0.00')
    
    # Get cart based on user authentication
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
            cart_items = cart.items.select_related('product').prefetch_related('product__images').all()
            total = sum(item.subtotal for item in cart_items)
        except Cart.DoesNotExist:
            pass
    elif request.session.session_key:
        try:
            cart = Cart.objects.get(session_key=request.session.session_key)
            cart_items = cart.items.select_related('product').prefetch_related('product__images').all()
            total = sum(item.subtotal for item in cart_items)
        except Cart.DoesNotExist:
            pass
    
    # Get store settings for minimum order and shipping threshold display
    store_settings = StoreSettings.load()
    
    # Check if order meets minimum amount
    below_minimum = total < store_settings.minimum_order_amount if total > 0 else False
    amount_needed = store_settings.minimum_order_amount - total if below_minimum else Decimal('0.00')
    
    # Check if eligible for free shipping
    free_shipping_eligible = total >= store_settings.free_shipping_threshold
    amount_for_free_shipping = store_settings.free_shipping_threshold - total if not free_shipping_eligible else Decimal('0.00')
    
    context = {
        'cart_items': cart_items,
        'total': total,
        'cart': cart,
        'store_settings': store_settings,
        'below_minimum': below_minimum,
        'amount_needed': amount_needed,
        'free_shipping_eligible': free_shipping_eligible,
        'amount_for_free_shipping': amount_for_free_shipping,
    }
    return render(request, 'cart.html', context)


def update_cart_item(request, item_id):
    """Update cart item quantity"""
    if request.method == 'POST':
        cart_item = get_object_or_404(CartItem, id=item_id)
        quantity_kg = Decimal(request.POST.get('quantity_kg', 0))
        
        if quantity_kg <= 0:
            cart_item.delete()
            messages.success(request, 'Item removed from cart')
        elif quantity_kg > cart_item.product.stock_kg:
            messages.error(request, f'Only {cart_item.product.stock_kg}{" kg" if cart_item.product.unit == "kg" else ""} available')
        else:
            cart_item.quantity_kg = quantity_kg
            cart_item.save()
            messages.success(request, 'Cart updated')
    
    return redirect('view_cart')


def remove_from_cart(request, item_id):
    """Remove item from cart"""
    cart_item = get_object_or_404(CartItem, id=item_id)
    cart_item.delete()
    messages.success(request, 'Item removed from cart')
    return redirect('view_cart')


def checkout(request):
    """Checkout page"""
    from .models import StoreSettings
    
    cart = None
    cart_items = []
    total = Decimal('0.00')
    
    # Get cart based on user authentication
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
            cart_items = cart.items.select_related('product').all()
            total = sum(item.subtotal for item in cart_items)
        except Cart.DoesNotExist:
            messages.error(request, 'Your cart is empty')
            return redirect('shop')
    elif request.session.session_key:
        try:
            cart = Cart.objects.get(session_key=request.session.session_key)
            cart_items = cart.items.select_related('product').all()
            total = sum(item.subtotal for item in cart_items)
        except Cart.DoesNotExist:
            messages.error(request, 'Your cart is empty')
            return redirect('shop')
    
    if not cart_items:
        messages.error(request, 'Your cart is empty')
        return redirect('shop')
    
    # Get store settings for shipping calculation and minimum order
    store_settings = StoreSettings.load()
    
    # Check minimum order amount
    if total < store_settings.minimum_order_amount:
        messages.error(request, f'Minimum order amount is ₱{store_settings.minimum_order_amount:,.2f}. Your current total is ₱{total:,.2f}.')
        return redirect('view_cart')
    
    if request.method == 'POST':
        return process_checkout(request, cart, cart_items, total)
    
    # Prepare user data for pre-filling form
    user_data = {}
    customer_lat = None
    customer_lng = None
    if request.user.is_authenticated:
        user_data = {
            'customer_name': request.user.get_full_name() or request.user.username,
            'customer_email': request.user.email,
            'customer_phone': request.user.profile.phone if hasattr(request.user, 'profile') else '',
            'shipping_address': request.user.profile.address if hasattr(request.user, 'profile') else '',
            'shipping_city': request.user.profile.city if hasattr(request.user, 'profile') else '',
            'shipping_postal_code': request.user.profile.postal_code if hasattr(request.user, 'profile') else '',
        }
        if hasattr(request.user, 'profile'):
            customer_lat = request.user.profile.latitude
            customer_lng = request.user.profile.longitude
    
    context = {
        'cart_items': cart_items,
        'total': total,
        'user_data': user_data,
        'store_settings': store_settings,
        'customer_lat': float(customer_lat) if customer_lat else None,
        'customer_lng': float(customer_lng) if customer_lng else None,
        'store_lat': float(store_settings.store_latitude) if store_settings.store_latitude else None,
        'store_lng': float(store_settings.store_longitude) if store_settings.store_longitude else None,
    }
    return render(request, 'checkout.html', context)


@transaction.atomic
def process_checkout(request, cart, cart_items, total):
    """Process checkout with atomic inventory deduction"""
    from .models import StoreSettings
    
    # Get customer info
    customer_name = request.POST.get('customer_name')
    customer_email = request.POST.get('customer_email')
    customer_phone = request.POST.get('customer_phone')
    shipping_address = request.POST.get('shipping_address')
    shipping_city = request.POST.get('shipping_city')
    shipping_postal_code = request.POST.get('shipping_postal_code')
    customer_notes = request.POST.get('customer_notes', '')
    payment_method = request.POST.get('payment_method', 'COD')
    payment_proof_image = request.FILES.get('payment_proof_image')

    def validate_uploaded_payment_image(uploaded_file):
        if not uploaded_file:
            return False, 'Please upload your payment confirmation screenshot for GCash orders.'

        extension = os.path.splitext(uploaded_file.name)[1].lower().lstrip('.')
        allowed_extensions = {'jpg', 'jpeg', 'png', 'webp', 'gif'}
        if extension not in allowed_extensions:
            return False, 'Payment proof must be an image file (JPG, PNG, WEBP, or GIF).'

        content_type = (uploaded_file.content_type or '').lower()
        if not content_type.startswith('image/'):
            return False, 'Payment proof must be an image file.'

        if uploaded_file.size > 5 * 1024 * 1024:
            return False, 'Payment proof image must be 5MB or smaller.'

        return True, None
    
    # Get customer GPS coordinates from map picker
    customer_latitude = request.POST.get('customer_latitude')
    customer_longitude = request.POST.get('customer_longitude')
    
    # Convert to decimal or None
    try:
        customer_latitude = float(customer_latitude) if customer_latitude else None
    except (ValueError, TypeError):
        customer_latitude = None
    
    try:
        customer_longitude = float(customer_longitude) if customer_longitude else None
    except (ValueError, TypeError):
        customer_longitude = None
    
    # Validate
    if not all([customer_name, customer_email, customer_phone, shipping_address, shipping_city]):
        messages.error(request, 'Please fill in all required fields')
        return redirect('checkout')

    if payment_method == 'GCASH':
        store_settings = StoreSettings.load()

        if not store_settings.gcash_qr_code:
            messages.error(request, 'GCash payment is temporarily unavailable. Please choose another payment method.')
            return redirect('checkout')

        is_valid_image, image_error = validate_uploaded_payment_image(payment_proof_image)
        if not is_valid_image:
            messages.error(request, image_error)
            return redirect('checkout')
    
    # Check stock availability and deduct atomically
    for cart_item in cart_items:
        product = Product.objects.select_for_update().get(id=cart_item.product.id)
        
        if cart_item.quantity_kg > product.stock_kg:
            messages.error(request, f'Sorry, only {product.stock_kg}{" kg" if product.unit == "kg" else ""} of {product.name} available')
            return redirect('view_cart')
        
        # Atomic stock deduction using F() expression
        updated = Product.objects.filter(
            id=product.id,
            stock_kg__gte=cart_item.quantity_kg
        ).update(stock_kg=F('stock_kg') - cart_item.quantity_kg)
        
        if updated == 0:
            messages.error(request, f'Sorry, {product.name} is no longer available')
            return redirect('view_cart')
    
    # Create Order
    order = Order.objects.create(
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        shipping_address=shipping_address,
        shipping_city=shipping_city,
        shipping_postal_code=shipping_postal_code,
        customer_latitude=customer_latitude,
        customer_longitude=customer_longitude,
        total_amount=total,
        customer_notes=customer_notes,
        payment_method=payment_method,
        payment_status='UNPAID' if payment_method == 'COD' else 'PENDING',
        payment_proof_image=payment_proof_image if payment_method == 'GCASH' else None,
        status='PENDING_VERIFICATION' if payment_method == 'GCASH' else 'PENDING'
    )
    
    # Create OrderItems and Sales
    for cart_item in cart_items:
        # Create order item
        OrderItem.objects.create(
            order=order,
            product=cart_item.product,
            quantity_kg=cart_item.quantity_kg,
            price_per_kg=cart_item.product.price_per_kg,
            unit=cart_item.product.unit,
            subtotal=cart_item.subtotal
        )
        
        # Create sale record
        Sale.objects.create(
            product=cart_item.product,
            order=order,
            sale_type='ECOMMERCE',
            quantity_kg=cart_item.quantity_kg,
            total_price=cart_item.subtotal
        )
        
        # Check for low stock and create notification
        product = Product.objects.get(id=cart_item.product.id)
        if product.is_low_stock:
            Notification.objects.create(
                title=f'Low Stock Alert: {product.name}',
                description=f'{product.name} stock is now {product.stock_kg} {product.unit} (below 10 unit threshold)',
                category='production',
                level='warning'
            )
    
    # Clear cart
    cart.delete()

    # Send email notifications asynchronously (don't slow down checkout)
    # 1. Send order confirmation to customer
    send_email_async(send_order_confirmation_email, order)

    # 2. Send new order notification to admin
    send_email_async(send_new_order_admin_notification, order)

    if payment_method == 'GCASH':
        messages.success(
            request,
            f'Order placed successfully! Your payment proof is pending verification. Order number: {order.order_number}'
        )
    else:
        messages.success(request, f'Order placed successfully! Order number: {order.order_number}')

    return redirect('order_confirmation', order_number=order.order_number)


def order_confirmation(request, order_number):
    """Order confirmation page"""
    order = get_object_or_404(Order, order_number=order_number)
    order_items = order.items.select_related('product').all()
    
    context = {
        'order': order,
        'order_items': order_items,
    }
    return render(request, 'order_confirmation.html', context)


# ==================== POS VIEWS ====================

@admin_required
def pos_system(request):
    """Staff-facing POS system"""
    products = Product.objects.filter(is_active=True, stock_kg__gt=0).prefetch_related('images').order_by('name')

    # Reuse the same product image source used by e-commerce listing.
    for product in products:
        primary_image = product.images.filter(is_primary=True).first()
        first_image = product.images.first()
        selected = primary_image or first_image
        product.image_url = selected.image.url if selected else None
    
    context = {
        'products': products,
    }
    return render(request, 'pos.html', context)


@admin_required
@transaction.atomic
def pos_complete_sale(request):
    """Complete a POS sale with atomic inventory deduction"""
    if request.method == 'POST':
        cart_data_raw = request.POST.get('cart_data')

        # Preferred checkout flow: process the full cart in one transaction.
        if cart_data_raw:
            try:
                cart_items = json.loads(cart_data_raw)
            except json.JSONDecodeError:
                messages.error(request, 'Invalid cart payload')
                return redirect('pos_system')

            if not isinstance(cart_items, list) or not cart_items:
                messages.error(request, 'Cart is empty')
                return redirect('pos_system')

            try:
                requested_ids = [int(item.get('id')) for item in cart_items]
            except (TypeError, ValueError):
                messages.error(request, 'Invalid product in cart')
                return redirect('pos_system')

            products = Product.objects.select_for_update().filter(id__in=requested_ids, is_active=True)
            product_map = {product.id: product for product in products}

            created_sales = []

            for item in cart_items:
                try:
                    product_id = int(item.get('id'))
                    quantity_kg = Decimal(str(item.get('quantity', 0)))
                except (TypeError, ValueError, InvalidOperation):
                    messages.error(request, 'Invalid quantity in cart')
                    return redirect('pos_system')

                if quantity_kg <= 0:
                    messages.error(request, 'Invalid quantity in cart')
                    return redirect('pos_system')

                product = product_map.get(product_id)
                if not product:
                    messages.error(request, 'One or more products are no longer available')
                    return redirect('pos_system')

                if quantity_kg > product.stock_kg:
                    messages.error(request, f'Only {product.stock_kg}{" kg" if product.unit == "kg" else ""} available for {product.name}')
                    return redirect('pos_system')

                total_price = quantity_kg * product.price_per_kg

                # Deduct stock from in-memory locked row and persist.
                product.stock_kg = product.stock_kg - quantity_kg
                product.save(update_fields=['stock_kg'])

                sale = Sale.objects.create(
                    product=product,
                    sold_by=request.user,
                    sale_type='POS',
                    quantity_kg=quantity_kg,
                    total_price=total_price
                )
                created_sales.append(sale)

                if product.is_low_stock:
                    Notification.objects.create(
                        user=request.user,
                        title=f'Low Stock Alert: {product.name}',
                        description=f'{product.name} stock is now {product.stock_kg} {product.unit} (below 10 unit threshold)',
                        category='production',
                        level='warning'
                    )

            grand_total = sum((sale.total_price for sale in created_sales), Decimal('0.00'))
            messages.success(request, f'Sale completed: {len(created_sales)} item(s), total ₱{grand_total}')
            return redirect('pos_system')

        # Backward-compatible single-item flow.
        product_id = request.POST.get('product_id')
        quantity_kg = Decimal(request.POST.get('quantity_kg', 0))
        
        if quantity_kg <= 0:
            messages.error(request, 'Invalid quantity')
            return redirect('pos_system')
        
        product = get_object_or_404(Product, id=product_id, is_active=True)
        
        # Check stock
        if quantity_kg > product.stock_kg:
            messages.error(request, f'Only {product.stock_kg}{" kg" if product.unit == "kg" else ""} available in stock')
            return redirect('pos_system')
        
        # Atomic stock deduction using F() expression
        updated = Product.objects.filter(
            id=product.id,
            stock_kg__gte=quantity_kg
        ).update(stock_kg=F('stock_kg') - quantity_kg)
        
        if updated == 0:
            messages.error(request, 'Product is no longer available')
            return redirect('pos_system')
        
        # Calculate total
        total_price = quantity_kg * product.price_per_kg
        
        # Create sale record
        Sale.objects.create(
            product=product,
            sold_by=request.user,
            sale_type='POS',
            quantity_kg=quantity_kg,
            total_price=total_price
        )
        
        # Check for low stock and create notification
        product.refresh_from_db()
        if product.is_low_stock:
            Notification.objects.create(
                user=request.user,
                title=f'Low Stock Alert: {product.name}',
                description=f'{product.name} stock is now {product.stock_kg} {product.unit} (below 10 unit threshold)',
                category='production',
                level='warning'
            )
        
        messages.success(request, f'Sale completed: {quantity_kg} {product.unit} of {product.name} for ₱{total_price}')
        return redirect('pos_system')
    
    return redirect('pos_system')


@admin_required
def pos_get_product_price(request, product_id):
    """AJAX endpoint to get product price for POS"""
    product = get_object_or_404(Product, id=product_id)
    return JsonResponse({
        'price_per_kg': float(product.price_per_kg),
        'stock_kg': float(product.stock_kg),
        'name': product.name,
        'unit': product.unit,
        'unit_label': product.get_unit_display(),
    })


# ==================== ADMIN VIEWS ====================

@admin_required
def manage_orders(request):
    """View and manage e-commerce orders"""
    orders = Order.objects.all().order_by('-created_at')
    
    # Apply filters
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    if search_query:
        orders = orders.filter(
            Q(customer_name__icontains=search_query) |
            Q(order_number__icontains=search_query)
        )
    
    # Pagination - 10 orders per page
    paginator = Paginator(orders, 10)
    page = request.GET.get('page', 1)
    
    try:
        orders_page = paginator.page(page)
    except PageNotAnInteger:
        orders_page = paginator.page(1)
    except EmptyPage:
        orders_page = paginator.page(paginator.num_pages)
    
    # Calculate statistics
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status__in=['PENDING', 'PENDING_VERIFICATION']).count()
    processing_orders = Order.objects.filter(status='PROCESSING').count()
    total_revenue = Order.objects.filter(
        is_paid=True
    ).aggregate(
        total=Sum('total_amount')
    )['total'] or Decimal('0.00')
    
    context = {
        'orders': orders_page,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'processing_orders': processing_orders,
        'total_revenue': total_revenue,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    return render(request, 'manage_orders.html', context)


@admin_required
def order_detail(request, order_id):
    """Get order details as JSON"""
    order = get_object_or_404(Order, id=order_id)
    items = order.items.all()
    
    # Get store settings for delivery map
    from .models import StoreSettings
    store_settings = StoreSettings.load()
    
    order_data = {
        'id': order.id,
        'order_number': order.order_number,
        'customer_name': order.customer_name,
        'customer_email': order.customer_email,
        'customer_phone': order.customer_phone,
        'shipping_address': order.shipping_address,
        'shipping_city': order.shipping_city,
        'shipping_postal_code': order.shipping_postal_code,
        'customer_latitude': float(order.customer_latitude) if order.customer_latitude else None,
        'customer_longitude': float(order.customer_longitude) if order.customer_longitude else None,
        'total_amount': str(order.total_amount),
        'status': order.status,
        'payment_method': order.payment_method,
        'payment_status': order.payment_status,
        'payment_proof_url': order.payment_proof_image.url if order.payment_proof_image else None,
        'is_paid': order.is_paid,
        'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'current_location_status': order.current_location_status or '',
        'current_location_address': order.current_location_address or '',
        'current_latitude': float(order.current_latitude) if order.current_latitude is not None else None,
        'current_longitude': float(order.current_longitude) if order.current_longitude is not None else None,
        'location_updated_at': order.location_updated_at.strftime('%Y-%m-%d %H:%M:%S') if order.location_updated_at else None,
    }
    
    items_data = [{
        'product_name': item.product.name,
        'quantity_kg': str(item.quantity_kg),
        'price_per_kg': str(item.price_per_kg),
        'unit': item.unit,
        'unit_label': item.get_unit_display(),
        'subtotal': str(item.subtotal),
    } for item in items]
    
    # Store location data for delivery map
    store_data = {
        'name': store_settings.store_name,
        'address': store_settings.store_address,
        'latitude': float(store_settings.store_latitude) if store_settings.store_latitude else None,
        'longitude': float(store_settings.store_longitude) if store_settings.store_longitude else None,
    }
    
    return JsonResponse({
        'order': order_data,
        'items': items_data,
        'store': store_data,
    })


@admin_required
def update_order_status(request, order_id):
    """Update order status and payment status"""
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)
        
        # Prevent changes to cancelled or delivered orders
        if order.status in ['CANCELLED', 'DELIVERED']:
            messages.error(request, f'Cannot modify order {order.order_number} - order is already {order.status.lower()}')
            return redirect('manage_orders')
        
        old_status = order.status  # Store old status for comparison
        new_status = request.POST.get('status')
        is_paid = request.POST.get('is_paid')
        location_status = (request.POST.get('current_location_status') or '').strip()
        location_address = (request.POST.get('current_location_address') or '').strip()
        raw_latitude = (request.POST.get('current_latitude') or '').strip()
        raw_longitude = (request.POST.get('current_longitude') or '').strip()

        def parse_decimal_or_none(raw_value):
            if raw_value == '':
                return None
            try:
                return Decimal(raw_value)
            except (InvalidOperation, TypeError):
                return None

        parsed_latitude = parse_decimal_or_none(raw_latitude)
        parsed_longitude = parse_decimal_or_none(raw_longitude)
        
        status_changed = False
        if new_status and new_status in dict(Order.STATUS_CHOICES):
            if new_status != old_status:
                order.status = new_status
                status_changed = True
        
        if is_paid is not None:
            order.is_paid = (is_paid == 'true' or is_paid == 'True' or is_paid == '1')

        location_changed = (
            (order.current_location_status or '') != location_status or
            (order.current_location_address or '') != location_address or
            order.current_latitude != parsed_latitude or
            order.current_longitude != parsed_longitude
        )

        order.current_location_status = location_status
        order.current_location_address = location_address
        order.current_latitude = parsed_latitude
        order.current_longitude = parsed_longitude
        if location_changed:
            order.location_updated_at = timezone.now()
        
        order.save()
        
        # Send email notification to customer if status changed
        if status_changed:
            send_email_async(send_order_status_email, order, old_status)
        
        messages.success(request, f'Order {order.order_number} updated successfully')
        
    return redirect('manage_orders')


@admin_required
@transaction.atomic
def verify_manual_gcash_payment(request, order_id):
    """Approve or reject customer-uploaded GCash payment proof."""
    if request.method != 'POST':
        messages.error(request, 'Invalid request method')
        return redirect('manage_orders')

    order = get_object_or_404(Order, id=order_id)

    if order.payment_method != 'GCASH':
        messages.error(request, 'This order is not using manual GCash payment')
        return redirect('manage_orders')

    if not order.payment_proof_image:
        messages.error(request, f'No payment proof uploaded for order {order.order_number}')
        return redirect('manage_orders')

    if order.status in ['CANCELLED', 'DELIVERED']:
        messages.error(request, f'Cannot verify payment for order {order.order_number} in status {order.get_status_display()}')
        return redirect('manage_orders')

    action = (request.POST.get('action') or '').strip().lower()
    admin_note = (request.POST.get('admin_note') or '').strip()
    old_status = order.status

    if action == 'approve':
        order.status = 'PROCESSING'
        order.payment_status = 'PAID'
        order.is_paid = True
        order.paid_at = timezone.now()
        note_prefix = 'PAYMENT APPROVED'
        success_message = f'Payment approved. Order {order.order_number} moved to Processing.'
    elif action == 'reject':
        # Restore stock and remove sales record when payment is rejected.
        for item in order.items.select_related('product').all():
            Product.objects.filter(id=item.product.id).update(stock_kg=F('stock_kg') + item.quantity_kg)

        Sale.objects.filter(order=order).delete()

        order.status = 'CANCELLED'
        order.payment_status = 'FAILED'
        order.is_paid = False
        order.paid_at = None
        note_prefix = 'PAYMENT REJECTED'
        success_message = f'Payment rejected. Order {order.order_number} has been cancelled.'
    else:
        messages.error(request, 'Unknown verification action')
        return redirect('manage_orders')

    note_text = f"\n[{note_prefix}] {timezone.now().strftime('%Y-%m-%d %H:%M')}"
    if admin_note:
        note_text += f" - {admin_note}"
    order.admin_notes = (order.admin_notes or '') + note_text
    order.save()

    if old_status != order.status:
        send_email_async(send_order_status_email, order, old_status)

    messages.success(request, success_message)
    return redirect('manage_orders')


@login_required
def toggle_wishlist(request, product_id):
    """Add or remove product from wishlist"""
    if request.method == 'POST':
        from .models import Wishlist
        
        product = get_object_or_404(Product, id=product_id)
        wishlist_item = Wishlist.objects.filter(user=request.user, product=product).first()
        
        if wishlist_item:
            # Remove from wishlist
            wishlist_item.delete()
            return JsonResponse({'success': True, 'action': 'removed'})
        else:
            # Add to wishlist
            Wishlist.objects.create(user=request.user, product=product)
            return JsonResponse({'success': True, 'action': 'added'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def wishlist_view(request):
    """View user's wishlist"""
    from .models import Wishlist
    
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product').prefetch_related('product__images')
    
    context = {
        'wishlist_items': wishlist_items,
    }
    return render(request, 'wishlist.html', context)


@login_required
def submit_review(request, product_id):
    """Submit a product review - linked to a specific order"""
    if request.method == 'POST':
        from .models import ProductReview
        import json
        
        product = get_object_or_404(Product, id=product_id)
        
        # Parse JSON data
        try:
            data = json.loads(request.body)
            rating = data.get('rating')
            comment = data.get('comment', '')
            order_id = data.get('order_id')  # Get order ID from request
            
            # Convert order_id to int if provided as string
            if order_id:
                try:
                    order_id = int(order_id)
                except (ValueError, TypeError):
                    return JsonResponse({'success': False, 'message': 'Invalid order ID format'})
                    
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
        
        # Get the specific order if provided
        order = None
        if order_id:
            # Check order exists for user with this product  
            order = Order.objects.filter(
                id=order_id,
                customer_email=request.user.email,
                status='DELIVERED'
            ).first()
            
            if not order:
                return JsonResponse({
                    'success': False, 
                    'message': 'Invalid order or order not delivered yet'
                })
            
            # Verify this product is in the order
            if not order.items.filter(product=product).exists():
                return JsonResponse({
                    'success': False, 
                    'message': 'This product is not in the specified order'
                })
            
            # Check if already reviewed this product for this order
            existing_review = ProductReview.objects.filter(
                user=request.user,
                product=product,
                order=order
            ).exists()
            
            if existing_review:
                return JsonResponse({
                    'success': False, 
                    'message': 'You have already reviewed this product for this order'
                })
        else:
            # Fallback: Check if user has any delivered order with this product
            has_purchased = Order.objects.filter(
                customer_email=request.user.email,
                items__product=product,
                status='DELIVERED'
            ).exists()
            
            if not has_purchased:
                return JsonResponse({
                    'success': False, 
                    'message': 'You can only review products you have purchased and received'
                })
        
        if rating and 1 <= int(rating) <= 5:
            # Create review linked to specific order
            review = ProductReview.objects.create(
                user=request.user,
                product=product,
                order=order,
                rating=int(rating),
                comment=comment
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Review submitted successfully',
                'review_id': review.id,
                'average_rating': product.average_rating,
                'review_count': product.review_count
            })
        else:
            return JsonResponse({'success': False, 'message': 'Invalid rating'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})


@login_required
def upload_review_media(request, review_id):
    """Upload media files (images/videos) for a review"""
    from .models import ProductReview, ReviewMedia
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    # Get the review and verify ownership
    review = get_object_or_404(ProductReview, id=review_id)
    
    if review.user != request.user:
        return JsonResponse({'success': False, 'message': 'You can only upload media to your own reviews'})
    
    # Get uploaded files - support both single file and multiple files
    files = request.FILES.getlist('media')
    
    # If no files from getlist, try getting single file
    if not files:
        single_file = request.FILES.get('media')
        if single_file:
            files = [single_file]
    
    if not files:
        return JsonResponse({'success': False, 'message': 'No files provided'})
    
    # Limit number of files per review
    existing_count = review.media.count()
    max_files = 5
    
    if existing_count + len(files) > max_files:
        return JsonResponse({
            'success': False, 
            'message': f'Maximum {max_files} media files allowed per review. You have {existing_count} already.'
        })
    
    uploaded = []
    errors = []
    
    for file in files:
        # Validate file
        is_valid, media_type, error = ReviewMedia.validate_file(file)
        
        if not is_valid:
            errors.append(f"{file.name}: {error}")
            continue
        
        # Create media record
        try:
            media = ReviewMedia.objects.create(
                review=review,
                media_type=media_type,
                file=file,
                file_size=file.size
            )
            uploaded.append({
                'id': media.id,
                'url': media.file.url,
                'type': media_type,
                'filename': file.name
            })
        except Exception as e:
            errors.append(f"{file.name}: Upload failed - {str(e)}")
    
    return JsonResponse({
        'success': len(uploaded) > 0,
        'uploaded': uploaded,
        'errors': errors,
        'message': f'{len(uploaded)} file(s) uploaded successfully' if uploaded else 'No files uploaded'
    })


@login_required
def delete_review_media(request, media_id):
    """Delete a media file from a review"""
    from .models import ReviewMedia
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    media = get_object_or_404(ReviewMedia, id=media_id)
    
    # Verify ownership
    if media.review.user != request.user:
        return JsonResponse({'success': False, 'message': 'You can only delete your own media'})
    
    # Delete file and record
    try:
        if media.file:
            media.file.delete(save=False)
        if media.thumbnail:
            media.thumbnail.delete(save=False)
        media.delete()
        return JsonResponse({'success': True, 'message': 'Media deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Failed to delete: {str(e)}'})


@login_required
def get_product_reviews(request, product_id):
    """Get all reviews for a product, optionally filtered by order_id"""
    from .models import ProductReview
    
    product = get_object_or_404(Product, id=product_id)
    reviews = ProductReview.objects.filter(product=product).select_related('user', 'order').prefetch_related('media').order_by('-created_at')
    
    # Optionally filter by order_id to get specific review
    order_id = request.GET.get('order_id')
    if order_id:
        reviews = reviews.filter(order_id=order_id)
    
    reviews_data = []
    for review in reviews:
        # Get approved media for this review
        media_items = [{
            'id': m.id,
            'url': m.file.url,
            'type': m.media_type,
            'is_video': m.is_video
        } for m in review.media.filter(is_approved=True)]
        
        reviews_data.append({
            'id': review.id,
            'user': review.user.get_full_name() or review.user.username,
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at.strftime('%B %d, %Y'),
            'is_own_review': review.user == request.user,
            'order_id': review.order_id if review.order else None,
            'media': media_items
        })
    
    return JsonResponse({
        'success': True,
        'reviews': reviews_data,
        'average_rating': product.average_rating,
        'review_count': product.review_count
    })


def track_product_view(request, product_id):
    """Track a product view for recently viewed"""
    from .models import RecentlyViewed
    from django.utils import timezone
    
    product = get_object_or_404(Product, id=product_id, is_active=True)
    
    if request.user.is_authenticated:
        RecentlyViewed.objects.update_or_create(
            user=request.user,
            product=product,
            defaults={'viewed_at': timezone.now()}
        )
        
        # Keep only last 10
        recent_items = RecentlyViewed.objects.filter(user=request.user).order_by('-viewed_at')
        if recent_items.count() > 10:
            items_to_delete = recent_items[10:]
            RecentlyViewed.objects.filter(id__in=[item.id for item in items_to_delete]).delete()
    else:
        if not request.session.session_key:
            request.session.create()
        
        RecentlyViewed.objects.update_or_create(
            session_key=request.session.session_key,
            product=product,
            defaults={'viewed_at': timezone.now()}
        )
        
        # Keep only last 10
        recent_items = RecentlyViewed.objects.filter(session_key=request.session.session_key).order_by('-viewed_at')
        if recent_items.count() > 10:
            items_to_delete = recent_items[10:]
            RecentlyViewed.objects.filter(id__in=[item.id for item in items_to_delete]).delete()
    
    return JsonResponse({'success': True})


def calculate_shipping_api(request):
    """Calculate shipping fee based on customer coordinates"""
    from .models import StoreSettings
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer_lat = data.get('latitude')
            customer_lng = data.get('longitude')
            order_total = float(data.get('order_total', 0))
            
            store_settings = StoreSettings.load()
            shipping_fee, distance, message = store_settings.calculate_shipping_fee(
                customer_lat, customer_lng, order_total
            )
            
            if shipping_fee is None:
                return JsonResponse({
                    'success': False,
                    'error': message,
                    'distance_km': distance
                })
            
            return JsonResponse({
                'success': True,
                'shipping_fee': float(shipping_fee),
                'distance_km': distance,
                'message': message
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)


# ==================== GCASH PAYMENT VIEWS ====================

def gcash_payment(request, order_number):
    """
    GCash payment page - simulates GCash payment interface in sandbox mode.
    In production, this would redirect to actual GCash payment gateway.
    """
    order = get_object_or_404(Order, order_number=order_number)
    
    # Prevent accessing payment page for non-GCash orders
    if order.payment_method != 'GCASH':
        messages.error(request, 'Invalid payment method for this order')
        return redirect('order_confirmation', order_number=order_number)
    
    # Prevent re-payment for already paid orders
    if order.payment_status == 'PAID':
        messages.info(request, 'This order has already been paid')
        return redirect('order_confirmation', order_number=order_number)
    
    context = {
        'order': order,
        'sandbox_mode': True,
    }
    return render(request, 'gcash_payment.html', context)


def gcash_callback(request, order_number, action):
    """
    Handle GCash payment callback (sandbox simulation).
    
    Actions:
    - success: Payment completed successfully
    - failed: Payment failed
    - pending: Payment is pending verification
    """
    from .gcash_service import verify_gcash_payment
    
    order = get_object_or_404(Order, order_number=order_number)
    
    # Verify the payment
    result = verify_gcash_payment(order, action)
    
    if action == 'success' and result['success']:
        # Send email notifications after successful payment
        send_email_async(send_order_confirmation_email, order)
        send_email_async(send_new_order_admin_notification, order)
        messages.success(request, result['message'])
    elif action == 'failed':
        messages.error(request, result['message'])
    elif action == 'pending':
        messages.warning(request, result['message'])
    else:
        messages.info(request, result.get('message', 'Payment status updated'))
    
    return redirect('order_confirmation', order_number=order_number)


@csrf_exempt
def gcash_webhook(request):
    """
    Webhook endpoint for GCash/PayMongo payment notifications.
    In production, this receives real payment status updates from the gateway.
    """
    from .gcash_service import gcash_service
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        # Verify webhook signature (in production)
        signature = request.headers.get('X-Signature', '')
        if not gcash_service.verify_webhook_signature(request.body.decode(), signature):
            return JsonResponse({'error': 'Invalid signature'}, status=401)
        
        data = json.loads(request.body)
        
        # Extract payment info
        transaction_id = data.get('transaction_id')
        status = data.get('status')  # 'success', 'failed', 'pending'
        
        # Find the order
        order = Order.objects.filter(transaction_id=transaction_id).first()
        if not order:
            return JsonResponse({'error': 'Order not found'}, status=404)
        
        # Update payment status
        result = gcash_service.verify_payment(order, status)
        
        # Send notifications if successful
        if status == 'success' and result['success']:
            send_email_async(send_order_confirmation_email, order)
            send_email_async(send_new_order_admin_notification, order)
        
        return JsonResponse({'success': True, 'status': result['payment_status']})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def retry_payment(request, order_number):
    """Allow customer to retry a failed GCash payment"""
    from .gcash_service import create_gcash_payment
    
    order = get_object_or_404(Order, order_number=order_number)
    
    # Only allow retry for GCash orders with failed or pending payment
    if order.payment_method != 'GCASH':
        messages.error(request, 'This order does not use GCash payment')
        return redirect('order_confirmation', order_number=order_number)
    
    if order.payment_status == 'PAID':
        messages.info(request, 'This order has already been paid')
        return redirect('order_confirmation', order_number=order_number)
    
    # Create new payment session
    result = create_gcash_payment(order, request)
    
    if result['success']:
        return redirect('gcash_payment', order_number=order_number)
    else:
        messages.error(request, f'Failed to initialize payment: {result.get("error", "Unknown error")}')
        return redirect('order_confirmation', order_number=order_number)


@transaction.atomic
def cancel_order(request, order_number):
    """
    Allow customer to cancel their order.
    
    Rules:
    - Only orders with status 'PENDING' or 'PENDING_VERIFICATION' can be cancelled
    - If order was paid via GCash, mark refund as manual follow-up
    - Restore stock to inventory
    - Send cancellation confirmation email
    """
    order = get_object_or_404(Order, order_number=order_number)
    
    # Check if order can be cancelled
    if order.status not in ['PENDING', 'PENDING_VERIFICATION']:
        messages.error(request, f'Cannot cancel order. Order status is already "{order.get_status_display()}".')
        return redirect('order_confirmation', order_number=order_number)
    
    # Manual refund marker for already-paid GCash orders.
    refund_result = None
    if order.payment_method == 'GCASH' and order.payment_status == 'PAID':
        refund_result = {
            'success': True,
            'refund_amount': order.total_amount,
            'refund_id': f"MANUAL-{timezone.now().strftime('%Y%m%d%H%M%S')}"
        }
    
    # Restore stock for each item in the order
    order_items = order.items.select_related('product').all()
    for item in order_items:
        Product.objects.filter(id=item.product.id).update(
            stock_kg=F('stock_kg') + item.quantity_kg
        )
    
    # Update order status to cancelled
    order.status = 'CANCELLED'
    
    # Keep payment status aligned with cancellation outcome.
    if order.payment_method == 'COD':
        order.payment_status = 'UNPAID'
    elif refund_result and refund_result.get('success'):
        order.payment_status = 'REFUNDED'
    elif order.payment_status == 'PENDING':
        order.payment_status = 'FAILED'
    
    order.admin_notes = (order.admin_notes or '') + f"\n[CANCELLED] {timezone.now().strftime('%Y-%m-%d %H:%M')} - Order cancelled by customer"
    order.save()
    
    # Delete associated sales records
    Sale.objects.filter(order=order).delete()
    
    # Send cancellation confirmation email
    send_email_async(send_order_cancellation_email, order, refund_result)
    
    if refund_result and refund_result['success']:
        messages.success(request, f'Order cancelled successfully. Refund of ₱{refund_result["refund_amount"]} is being processed.')
    else:
        messages.success(request, 'Order cancelled successfully.')
    
    return redirect('order_confirmation', order_number=order_number)


def send_order_cancellation_email(order, refund_result=None):
    """Send order cancellation confirmation email to customer"""
    from django.core.mail import send_mail
    from django.conf import settings
    
    subject = f'Order Cancelled - {order.order_number}'
    
    # Build email message
    if refund_result and refund_result.get('success'):
        refund_info = f"""
REFUND INFORMATION
------------------
Refund Amount: ₱{refund_result['refund_amount']}
Refund ID: {refund_result['refund_id']}
Status: Processing

Your refund will be credited to your GCash account within 3-5 business days.
"""
    else:
        refund_info = ""
    
    message = f"""
Dear {order.customer_name},

Your order has been cancelled successfully.

ORDER DETAILS
-------------
Order Number: {order.order_number}
Order Date: {order.created_at.strftime('%B %d, %Y %I:%M %p')}
Total Amount: ₱{order.total_amount}
Payment Method: {order.get_payment_method_display()}
{refund_info}
CANCELLED ITEMS
---------------
"""
    
    # Add order items
    for item in order.items.all():
        message += f"• {item.product.name} - {item.quantity_kg} {item.unit} × ₱{item.price_per_kg} = ₱{item.subtotal}\n"
    
    message += f"""
If you have any questions about your cancellation, please contact us.

Thank you for shopping with Mushroom Farm!

Best regards,
The Mushroom Farm Team
"""
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.customer_email],
            fail_silently=False,
        )
        logger.info(f"Cancellation email sent to {order.customer_email} for order {order.order_number}")
    except Exception as e:
        logger.error(f"Failed to send cancellation email for order {order.order_number}: {str(e)}")

