from django.urls import path
from . import views
from . import ecommerce_views
from . import sensor_api

urlpatterns = [
    # Page URLs
    path('', views.dashboard_view, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    # Email verification URLs
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification, name='resend_verification'),
    
    path('environment/', views.environment_view, name='environment'),
    path('production/', views.production_view, name='production'),
    path('inventory/', views.inventory_view, name='inventory'),
    path('cooked-products/', views.cooked_products_view, name='cooked_products'),
    path('analytics/', views.analytics_view, name='analytics'),
    path('sales-report/', views.sales_report_view, name='sales_report'),
    path('sales-report/export/', views.sales_report_export, name='sales_report_export'),
    path('weather/', views.weather_view, name='weather'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('profile/', views.profile_view, name='profile'),
    path('store-settings/', views.store_settings_view, name='store_settings'),
    
    # E-commerce URLs
    path('shop/', ecommerce_views.shop, name='shop'),
    path('product/<int:product_id>/', ecommerce_views.product_detail, name='product_detail'),
    path('cart/', ecommerce_views.view_cart, name='view_cart'),
    path('cart/add/<int:product_id>/', ecommerce_views.add_to_cart, name='add_to_cart'),
    path('api/cart/add/', ecommerce_views.add_to_cart_api, name='add_to_cart_api'),
    path('cart/update/<int:item_id>/', ecommerce_views.update_cart_item, name='update_cart_item'),
    path('cart/remove/<int:item_id>/', ecommerce_views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', ecommerce_views.checkout, name='checkout'),
    path('api/addresses/', ecommerce_views.customer_addresses_api, name='customer-addresses-api'),
    path('api/addresses/<int:address_id>/', ecommerce_views.customer_addresses_api, name='customer-address-api'),
    path('api/addresses/<int:address_id>/default/', ecommerce_views.set_default_customer_address, name='set-default-address'),
    path('order/<str:order_number>/', ecommerce_views.order_confirmation, name='order_confirmation'),
    
    # Order Cancellation
    path('order/<str:order_number>/cancel/', ecommerce_views.cancel_order, name='cancel_order'),
    
    # POS URLs
    path('pos/', ecommerce_views.pos_system, name='pos_system'),
    path('pos/sale/', ecommerce_views.pos_complete_sale, name='pos_complete_sale'),
    path('pos/product/<int:product_id>/', ecommerce_views.pos_get_product_price, name='pos_get_product_price'),
    
    # Order Management URLs
    path('orders/', ecommerce_views.manage_orders, name='manage_orders'),
    path('order-detail/<int:order_id>/', ecommerce_views.order_detail, name='order_detail'),
    path('update-order-status/<int:order_id>/', ecommerce_views.update_order_status, name='update_order_status'),
    path('orders/<int:order_id>/verify-payment/', ecommerce_views.verify_manual_gcash_payment, name='verify_manual_gcash_payment'),
    
    # Wishlist URLs
    path('toggle-wishlist/<int:product_id>/', ecommerce_views.toggle_wishlist, name='toggle_wishlist'),
    path('wishlist/', ecommerce_views.wishlist_view, name='wishlist'),
    
    # Review URLs
    path('submit-review/<int:product_id>/', ecommerce_views.submit_review, name='submit_review'),
    path('get-reviews/<int:product_id>/', ecommerce_views.get_product_reviews, name='get_product_reviews'),
    path('review/<int:review_id>/upload-media/', ecommerce_views.upload_review_media, name='upload_review_media'),
    path('review/media/<int:media_id>/delete/', ecommerce_views.delete_review_media, name='delete_review_media'),
    
    # Recently Viewed
    path('track-view/<int:product_id>/', ecommerce_views.track_product_view, name='track_product_view'),
    
    # Shipping Calculation
    path('api/calculate-shipping/', ecommerce_views.calculate_shipping_api, name='calculate_shipping'),
    
    # API URLs
    # DHT22 Sensor API Endpoints (for ESP32)
    path('api/sensor-data/receive/', sensor_api.receive_sensor_data, name='receive-sensor-data'),
    path('api/sensor-data/latest/', sensor_api.get_latest_sensor_data, name='latest-sensor-data'),
    path('api/sensor-data/stats/', sensor_api.get_sensor_statistics, name='sensor-statistics'),
    
    # ESP32 Control State Endpoints (for relay control)
    path('api/control-states/', sensor_api.get_control_states, name='control-states'),
    path('api/control-confirm/', sensor_api.confirm_control_action, name='control-confirm'),
    
    # Automation Decision Endpoints (core automation logic)
    path('api/automation-decision/', sensor_api.get_automation_decision, name='automation-decision'),
    path('api/relay-command/', sensor_api.get_relay_command, name='relay-command'),
    
    # Sensor data for dashboard charts (GET)
    path('api/sensor-data/', views.sensor_data_api, name='sensor-api'),
    
    path('api/inventory/', views.inventory_api, name='inventory-api'),
    path('api/inventory/<int:pk>/', views.inventory_api_detail, name='inventory-api-detail'),
    path('api/product/<int:pk>/toggle-publish/', views.toggle_product_publish, name='toggle-product-publish'),
    
    path('api/sales/', views.sales_api, name='sales-api'),
    path('api/summary/', views.summary_api, name='summary-api'),

    path('api/production/', views.production_api, name='production-api'),
    path('api/production/predict/', views.production_predict_api, name='production-predict-api'),
    path('api/production/next-batch-number/', views.production_next_batch_number_api, name='production-next-batch-number-api'),
    path('api/production/<int:pk>/', views.production_api_detail, name='production-api-detail'),
    path('api/production-summary/', views.production_summary_api, name='production-summary-api'),
    
    path('api/analytics/', views.analytics_api, name='analytics-api'),
    
    path('api/profile/', views.profile_api, name='profile-api'),
    path('api/change-password/', views.change_password_api, name='change-password-api'),
    path('api/update-profile/', views.update_customer_profile, name='update-customer-profile'),
    path('api/store-settings/', views.store_settings_api, name='store-settings-api'),
    path('api/chat/customer/', views.customer_chat_api, name='customer-chat-api'),
    path('api/chat/admin/', views.admin_chat_api, name='admin-chat-api'),
    path('api/customer/order-tracking/', views.customer_order_tracking_api, name='customer-order-tracking-api'),
    
    path('api/notifications/', views.notifications_api, name='notifications-api'),
    path('api/notifications/<int:pk>/', views.notifications_api, name='notifications-api-detail'),
    path('api/notifications/mark-all-read/', views.mark_all_notifications_read, name='notifications-mark-all-read'),
    
    # --- NEW URL ---
    path('api/environment/', views.environment_api, name='environment-api'),
    path('api/dashboard-summary/', views.dashboard_summary_api, name='dashboard-summary-api'),
    path('api/start-watering/', views.watering_api, name='watering-api'),
]
