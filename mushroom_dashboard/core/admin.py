from django.contrib import admin
from .models import (
    Product, SensorReading, Sale, ProductionBatch, Notification, 
    EnvironmentSettings, DiseaseDetection, ProductReview, Wishlist,
    ProductImage, RecentlyViewed, ReviewMedia, NotificationSettings,
    NotificationLog, EnvironmentalAlertState
)


# Inline for ProductImage in Product admin
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'is_primary', 'display_order')


# Enhanced Product Admin with image upload inline
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'product_type', 'unit', 'stock_kg', 'price_per_kg', 'is_active', 'has_image')
    list_filter = ('product_type', 'is_active')
    search_fields = ('name', 'description')
    list_editable = ('is_active',)
    inlines = [ProductImageInline]
    
    fieldsets = (
        ('Product Information', {
            'fields': ('name', 'product_type', 'description')
        }),
        ('Inventory', {
            'fields': ('batch_id', 'stock_kg', 'unit', 'price_per_kg')
        }),
        ('Publishing', {
            'fields': ('is_active',)
        }),
    )
    
    def has_image(self, obj):
        """Display if product has an image"""
        from django.utils.html import format_html
        if obj.images.exists():
            return format_html('<span style="color: green;">✓ Yes</span>')
        return format_html('<span style="color: red;">✗ No</span>')
    has_image.short_description = 'Has Image'


# Enhanced admin for Sensor Readings
@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'temperature', 'humidity', 'air_quality_ppm', 'air_quality_status_colored', 'device_id', 'condition_status_colored')
    list_filter = ('device_id', 'timestamp')
    search_fields = ('device_id',)
    readonly_fields = ('timestamp', 'is_temperature_optimal', 'is_humidity_optimal', 'is_air_quality_good', 'air_quality_status', 'condition_status')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
    
    def condition_status_colored(self, obj):
        """Display condition status with color coding"""
        from django.utils.html import format_html
        status = obj.condition_status
        colors = {
            'OPTIMAL': 'green',
            'ACCEPTABLE': 'orange',
            'CRITICAL': 'red'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(status, 'black'),
            status
        )
    condition_status_colored.short_description = 'Overall Status'
    
    def air_quality_status_colored(self, obj):
        """Display air quality status with color coding"""
        from django.utils.html import format_html
        status = obj.air_quality_status
        colors = {
            'GOOD': 'green',
            'ACCEPTABLE': 'orange',
            'POOR': 'red',
            'UNKNOWN': 'gray'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(status, 'black'),
            status
        )
    air_quality_status_colored.short_description = 'Air Quality'
    
    fieldsets = (
        ('Reading Data', {
            'fields': ('timestamp', 'temperature', 'humidity', 'air_quality_ppm', 'co2_ppm', 'device_id')
        }),
        ('Condition Analysis', {
            'fields': ('is_temperature_optimal', 'is_humidity_optimal', 'is_air_quality_good', 'air_quality_status', 'condition_status'),
            'classes': ('collapse',)
        }),
    )

# Register other models
# SensorReading now registered with custom admin above
# Product now registered with custom admin above
admin.site.register(Sale)
admin.site.register(ProductionBatch)
admin.site.register(Notification)
admin.site.register(EnvironmentSettings)
admin.site.register(DiseaseDetection)
admin.site.register(ProductReview)
admin.site.register(Wishlist)
# ProductImage is now an inline in ProductAdmin
admin.site.register(RecentlyViewed)


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ('email_enabled', 'alert_cooldown_minutes', 'updated_at')
    fieldsets = (
        ('Email Notifications', {
            'fields': ('email_enabled', 'recipient_emails', 'alert_cooldown_minutes', 'recovery_email_enabled')
        }),
    )


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('sent_at', 'notification_type', 'recipient', 'channel', 'status', 'subject')
    list_filter = ('channel', 'status', 'notification_type', 'sent_at')
    search_fields = ('recipient', 'subject', 'notification_type', 'error_message')
    readonly_fields = ('notification_type', 'recipient', 'subject', 'channel', 'status', 'sent_at', 'error_message', 'metadata')


@admin.register(EnvironmentalAlertState)
class EnvironmentalAlertStateAdmin(admin.ModelAdmin):
    list_display = ('alert_key', 'alert_name', 'is_active', 'last_alert_sent_at', 'last_recovery_sent_at', 'updated_at')
    list_filter = ('is_active', 'updated_at')
    search_fields = ('alert_key', 'alert_name')


# Review Media Admin for moderation
@admin.register(ReviewMedia)
class ReviewMediaAdmin(admin.ModelAdmin):
    list_display = ('id', 'review_link', 'media_type', 'file_size_display', 'is_approved', 'uploaded_at')
    list_filter = ('media_type', 'is_approved', 'uploaded_at')
    list_editable = ('is_approved',)
    search_fields = ('review__product__name', 'review__user__username')
    actions = ['approve_selected', 'reject_selected']
    readonly_fields = ('review', 'media_type', 'file', 'file_size', 'uploaded_at', 'preview_media')
    
    def review_link(self, obj):
        from django.utils.html import format_html
        return format_html(
            '<a href="/admin/core/productreview/{}/change/">{} - {}</a>',
            obj.review.id,
            obj.review.product.name,
            obj.review.user.username
        )
    review_link.short_description = 'Review'
    
    def file_size_display(self, obj):
        if obj.file_size < 1024:
            return f"{obj.file_size} B"
        elif obj.file_size < 1024 * 1024:
            return f"{obj.file_size / 1024:.1f} KB"
        else:
            return f"{obj.file_size / (1024 * 1024):.1f} MB"
    file_size_display.short_description = 'Size'
    
    def preview_media(self, obj):
        from django.utils.html import format_html
        if obj.media_type == 'IMAGE':
            return format_html('<img src="{}" style="max-width:300px;max-height:200px;">', obj.file.url)
        else:
            return format_html('<video src="{}" controls style="max-width:300px;max-height:200px;"></video>', obj.file.url)
    preview_media.short_description = 'Preview'
    
    @admin.action(description='Approve selected media')
    def approve_selected(self, request, queryset):
        count = queryset.update(is_approved=True)
        self.message_user(request, f'{count} media items approved.')
    
    @admin.action(description='Reject selected media')
    def reject_selected(self, request, queryset):
        count = queryset.update(is_approved=False)
        self.message_user(request, f'{count} media items rejected.')