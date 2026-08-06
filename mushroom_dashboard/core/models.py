from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import date
import os
import uuid


# User Profile for role-based access control
class UserProfile(models.Model):
    """Extends User model to add role-based access"""
    ROLE_CHOICES = [
        ('ADMIN', 'Administrator'),
        ('CUSTOMER', 'Customer'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='CUSTOMER')
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Email verification fields
    is_email_verified = models.BooleanField(default=False, help_text="Whether the user's email is verified")
    email_verification_token = models.CharField(max_length=100, blank=True, null=True)
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"
    
    @property
    def is_admin(self):
        return self.role == 'ADMIN'
    
    @property
    def is_customer(self):
        return self.role == 'CUSTOMER'
    
    def generate_verification_token(self):
        """Generate a unique email verification token"""
        import secrets
        self.email_verification_token = secrets.token_urlsafe(32)
        self.email_verification_sent_at = timezone.now()
        self.save()
        return self.email_verification_token


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create UserProfile when User is created"""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save UserProfile when User is saved"""
    if hasattr(instance, 'profile'):
        instance.profile.save()


# This will create a table for your inventory
class Product(models.Model):
    PRODUCT_TYPE_CHOICES = [
        ('fresh', 'Fresh Mushrooms'),
        ('cooked', 'Cooked / Ready-to-Eat'),
        ('fruit_bags', 'Fruit Bags'),
    ]

    UNIT_CHOICES = [
        ('kg', 'per kg'),
        ('pack', 'per pack'),
        ('bag', 'per bag'),
        ('piece', 'per piece'),
    ]
    
    name = models.CharField(max_length=100)
    batch_id = models.CharField(max_length=50, blank=True, default='')
    stock_kg = models.DecimalField(max_digits=5, decimal_places=1)
    price_per_kg = models.DecimalField(max_digits=6, decimal_places=2, default=0.00, help_text="Unit price based on the selected unit")
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='kg', help_text="Unit of measurement for pricing and quantity")
    description = models.TextField(blank=True, help_text="Product description for e-commerce")
    is_active = models.BooleanField(default=True, help_text="Published - visible for sale in e-commerce")
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPE_CHOICES, default='fresh', help_text="Type of product")
    
    # Nutrition Facts fields
    serving_size = models.CharField(max_length=50, blank=True, default='100g', help_text="Serving size (e.g., 100g, 1 cup)")
    calories = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, help_text="Calories per serving")
    protein = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, help_text="Protein in grams")
    carbohydrates = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, help_text="Carbohydrates in grams")
    fat = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, help_text="Fat in grams")
    fiber = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, help_text="Fiber in grams")
    sodium = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, help_text="Sodium in milligrams")

    def __str__(self):
        return self.name
    
    @property
    def is_low_stock(self):
        """Check if stock is below 10kg threshold"""
        return self.stock_kg < 10
    
    @property
    def average_rating(self):
        """Calculate average rating from reviews"""
        from django.db.models import Avg
        result = self.reviews.aggregate(Avg('rating'))
        return round(result['rating__avg'], 1) if result['rating__avg'] else 0
    
    @property
    def review_count(self):
        """Get total number of reviews"""
        return self.reviews.count()
    
    @property
    def has_nutrition_info(self):
        """Check if any nutrition information is available"""
        return any([
            self.calories is not None,
            self.protein is not None,
            self.carbohydrates is not None,
            self.fat is not None,
            self.fiber is not None,
            self.sodium is not None
        ])
    
    def get_stock_urgency_message(self):
        """Get urgency message based on stock level"""
        if self.stock_kg <= 0:
            return "Out of Stock"
        elif self.stock_kg <= 5:
            return f"Only {self.stock_kg} {self.unit} left!"
        elif self.stock_kg <= 10:
            return f"Low stock: {self.stock_kg} {self.unit} remaining"
        return None

# This is the table for your sensor simulator and DHT22 + MQ-135 sensor data!
class SensorReading(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    temperature = models.DecimalField(max_digits=4, decimal_places=1, help_text="Temperature in Celsius")
    humidity = models.DecimalField(max_digits=4, decimal_places=1, help_text="Relative humidity percentage")
    co2_ppm = models.IntegerField(null=True, blank=True, help_text="CO2 level in PPM (optional)")
    air_quality_ppm = models.IntegerField(null=True, blank=True, help_text="Air quality from MQ-135 in PPM")
    device_id = models.CharField(max_length=50, default='DHT22_ESP32', help_text="Sensor device identifier")
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
        ]

    def __str__(self):
        return f"Reading at {self.timestamp}: {self.temperature}°C, {self.humidity}%, AQ:{self.air_quality_ppm or 'N/A'}"
    
    @property
    def is_temperature_optimal(self):
        """Check if temperature is within optimal mushroom growing range (13-18°C)"""
        return 13 <= self.temperature <= 18
    
    @property
    def is_humidity_optimal(self):
        """Check if humidity is within optimal mushroom growing range (80-95%)"""
        return 80 <= self.humidity <= 95
    
    @property
    def is_air_quality_good(self):
        """Check if air quality is good (< 400 PPM)"""
        if self.air_quality_ppm is None:
            return None
        return self.air_quality_ppm < 400
    
    @property
    def air_quality_status(self):
        """Get air quality status"""
        if self.air_quality_ppm is None:
            return "UNKNOWN"
        if self.air_quality_ppm < 400:
            return "GOOD"
        elif self.air_quality_ppm < 800:
            return "ACCEPTABLE"
        else:
            return "POOR"
    
    @property
    def condition_status(self):
        """Get overall growing condition status"""
        if self.is_temperature_optimal and self.is_humidity_optimal:
            return "OPTIMAL"
        elif (10 <= self.temperature <= 21) and (70 <= self.humidity <= 98):
            return "ACCEPTABLE"
        else:
            return "CRITICAL"

class Sale(models.Model):
    SALE_TYPE_CHOICES = [
        ('POS', 'Point of Sale'),
        ('ECOMMERCE', 'E-commerce'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    batch = models.ForeignKey('ProductionBatch', on_delete=models.SET_NULL, null=True, blank=True, related_name='sales', help_text="Which production batch was sold")
    sold_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='sales', help_text="E-commerce order if applicable")
    sale_type = models.CharField(max_length=10, choices=SALE_TYPE_CHOICES, default='POS')
    quantity_kg = models.DecimalField(max_digits=5, decimal_places=1)
    total_price = models.DecimalField(max_digits=7, decimal_places=2)
    sale_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Sale of {self.quantity_kg} {self.product.unit} of {self.product.name}"

# --- UPDATED MODEL ---
class ProductionBatch(models.Model):
    STATUS_CHOICES = [
        ('GROWING', 'Growing'),
        ('READY', 'Ready'),
        ('HARVESTED', 'Harvested'),
    ]
    
    # --- NEW FIELD ---
    # This links a batch to a product (e.g., "Oyster Mushroom")
    # We use SET_NULL so if you delete a product, the batch history isn't deleted.
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Link to user who created this batch
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='production_batches')
    
    batch_number = models.CharField(max_length=50, unique=True)
    start_date = models.DateField(default=timezone.now)
    harvest_date = models.DateField(null=True, blank=True)
    yield_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    predicted_yield_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="ML predicted yield")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='GROWING')
    
    # --- NEW FIELD ---
    # This will store the cost for the financial chart
    cost = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, help_text="Total cost for this batch")

    @classmethod
    def generate_batch_number(cls, start_date=None):
        """Generate the next batch number in BATCH-YYYYMMDD-XXX format."""
        date_value = start_date or timezone.now().date()
        if isinstance(date_value, str):
            try:
                date_value = date.fromisoformat(date_value)
            except ValueError:
                date_value = timezone.now().date()
        date_part = date_value.strftime('%Y%m%d')
        prefix = f"BATCH-{date_part}-"

        latest_batch = cls.objects.filter(batch_number__startswith=prefix).order_by('-batch_number').first()
        next_sequence = 1

        if latest_batch:
            try:
                next_sequence = int(latest_batch.batch_number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                next_sequence = 1

        return f"{prefix}{next_sequence:03d}"

    def save(self, *args, **kwargs):
        if not self.batch_number:
            self.batch_number = self.generate_batch_number(self.start_date)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.batch_number

class Notification(models.Model):
    CATEGORY_CHOICES = [
        ('environmental', 'Environmental'),
        ('equipment', 'Equipment'),
        ('production', 'Production'),
        ('system', 'System'),
    ]
    LEVEL_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('success', 'Success'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications', help_text="User who receives this notification")
    title = models.CharField(max_length=100)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='system')
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='info')
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    def __str__(self):
        return self.title


class NotificationSettings(models.Model):
    """Singleton notification configuration for email alerts."""

    id = models.AutoField(primary_key=True)
    email_enabled = models.BooleanField(default=True, help_text="Enable or disable email notifications")
    recipient_emails = models.TextField(blank=True, default='', help_text="Comma-separated recipient email addresses")
    alert_cooldown_minutes = models.PositiveIntegerField(default=60, help_text="Cooldown in minutes for repeated environmental alerts")
    recovery_email_enabled = models.BooleanField(default=True, help_text="Send recovery emails when conditions return to normal")
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def get_recipient_list(self):
        import re

        raw_emails = re.split(r'[;,\n]+', self.recipient_emails or '')
        return [email.strip() for email in raw_emails if email.strip()]


class NotificationLog(models.Model):
    """Audit log for outbound notification attempts."""

    STATUS_CHOICES = [
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]

    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push'),
    ]

    notification_type = models.CharField(max_length=80, help_text="Notification type, such as environmental_alert or order_confirmation")
    recipient = models.EmailField(blank=True, default='', help_text="Primary recipient for the notification")
    subject = models.CharField(max_length=255)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='email')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='SUCCESS')
    sent_at = models.DateTimeField(auto_now_add=True)
    error_message = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.notification_type} -> {self.recipient or 'n/a'} ({self.status})"


class EnvironmentalAlertState(models.Model):
    """Tracks alert state so repeated sensor readings do not spam notifications."""

    alert_key = models.CharField(max_length=80, unique=True)
    alert_name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=False)
    last_alert_sent_at = models.DateTimeField(null=True, blank=True)
    last_recovery_sent_at = models.DateTimeField(null=True, blank=True)
    last_observed_value = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.alert_name

    @classmethod
    def get_or_create_state(cls, alert_key, alert_name):
        obj, _ = cls.objects.get_or_create(alert_key=alert_key, defaults={'alert_name': alert_name})
        if obj.alert_name != alert_name:
            obj.alert_name = alert_name
            obj.save(update_fields=['alert_name'])
        return obj

class EnvironmentSettings(models.Model):
    """
    Singleton model for environment control settings.
    Supports both Manual and Automatic control modes.
    
    Manual Mode: User controls via dashboard switch override automation
    Automatic Mode: System controls based on sensor readings vs thresholds
    """
    id = models.AutoField(primary_key=True)
    
    # Fan/Ventilation Control
    fan_on = models.BooleanField(default=False, help_text="Current fan state (ON/OFF)")
    fan_auto = models.BooleanField(default=True, help_text="Enable automatic control based on sensors")
    fan_value = models.IntegerField(default=25, help_text="Target temperature °C - fan turns ON above this, OFF below")
    
    # Fan automation thresholds
    fan_temp_threshold = models.DecimalField(
        max_digits=4, decimal_places=1, default=30.0,
        help_text="Temperature threshold in °C - fan turns ON if exceeded"
    )
    fan_humidity_threshold = models.DecimalField(
        max_digits=4, decimal_places=1, default=95.0,
        help_text="Humidity threshold % - fan turns ON if exceeded"
    )
    fan_air_quality_threshold = models.IntegerField(
        default=600,
        help_text="Air quality threshold PPM - fan turns ON if exceeded"
    )
    
    # Humidifier Control
    humidifier_on = models.BooleanField(default=False, help_text="Current humidifier state")
    humidifier_auto = models.BooleanField(default=True, help_text="Enable automatic control")
    humidifier_value = models.IntegerField(default=85, help_text="Target humidity % - humidifier runs until this is reached")
    
    # Humidifier automation thresholds
    humidifier_low_threshold = models.DecimalField(
        max_digits=4, decimal_places=1, default=75.0,
        help_text="Humidity threshold % - humidifier turns ON if below"
    )
    humidifier_high_threshold = models.DecimalField(
        max_digits=4, decimal_places=1, default=90.0,
        help_text="Humidity threshold % - humidifier turns OFF if above"
    )
    
    # Heater Control
    heater_on = models.BooleanField(default=False, help_text="Current heater state")
    heater_auto = models.BooleanField(default=True, help_text="Enable automatic control")
    heater_value = models.IntegerField(default=22, help_text="Target temperature °C - heater runs until this is reached")
    
    # Heater automation thresholds
    heater_low_threshold = models.DecimalField(
        max_digits=4, decimal_places=1, default=15.0,
        help_text="Temperature threshold °C - heater turns ON if below"
    )
    heater_high_threshold = models.DecimalField(
        max_digits=4, decimal_places=1, default=20.0,
        help_text="Temperature threshold °C - heater turns OFF if above"
    )
    
    # CO2 Control
    co2_on = models.BooleanField(default=False, help_text="Current CO2 injector state")
    co2_auto = models.BooleanField(default=True, help_text="Enable automatic control")
    co2_value = models.IntegerField(default=900, help_text="Target CO2 PPM")
    
    # Grow Lights Control
    lights_on = models.BooleanField(default=False, help_text="Current lights state")
    lights_auto = models.BooleanField(default=True, help_text="Enable automatic control")
    lights_value = models.IntegerField(default=50, help_text="Light intensity percentage")
    
    # Hysteresis settings to prevent rapid switching
    hysteresis_margin = models.DecimalField(
        max_digits=3, decimal_places=1, default=2.0,
        help_text="Margin to prevent rapid ON/OFF cycling"
    )
    
    # Timestamp for last automation action
    last_automation_update = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1 
        super(EnvironmentSettings, self).save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        pass 
    
    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
    
    def get_automation_decision(self, temperature, humidity, air_quality_ppm=None):
        """
        Determines what actions should be taken based on sensor readings and target values.
        Only returns decisions for devices in automatic mode.
        
        Target values are actively used:
        - humidifier_value: Target humidity % - humidifier runs until this is reached
        - heater_value: Target temperature °C - heater runs until this is reached
        - fan_value: Fan speed % when ON (for PWM control)
        
        Returns dict with:
        - fan_should_be_on: bool or None (None = no change / not in auto mode)
        - humidifier_should_be_on: bool or None
        - heater_should_be_on: bool or None
        - target_values: dict with target settings for hardware
        - reasons: list of explanations
        """
        decisions = {
            'fan_should_be_on': None,
            'humidifier_should_be_on': None,
            'heater_should_be_on': None,
            'target_values': {
                'fan_target_temp': self.fan_value,
                'target_humidity': self.humidifier_value,
                'target_temperature': self.heater_value,
                'target_co2': self.co2_value,
                'light_intensity': self.lights_value
            },
            'reasons': []
        }
        
        hysteresis = float(self.hysteresis_margin)
        target_humidity = float(self.humidifier_value)
        target_temperature = float(self.heater_value)
        fan_target_temp = float(self.fan_value)
        
        # Fan Automation Logic - Uses target temperature (fan_value)
        # Fan turns ON when temp exceeds target, OFF when below target
        if self.fan_auto:
            reasons = []
            fan_on_needed = False
            
            # Check temperature against target
            if temperature > fan_target_temp:
                fan_on_needed = True
                reasons.append(f"Temperature {temperature}°C exceeds target {fan_target_temp}°C (activating fan)")
            elif temperature <= fan_target_temp - hysteresis:
                fan_on_needed = False
                reasons.append(f"Temperature {temperature}°C below target {fan_target_temp}°C (deactivating fan)")
            elif self.fan_on and temperature < fan_target_temp:
                # Keep running until we drop below target minus hysteresis
                fan_on_needed = True
                reasons.append(f"Temperature {temperature}°C approaching target {fan_target_temp}°C (maintaining)")
            
            # Also check humidity - fan helps reduce excess humidity
            if humidity > float(self.fan_humidity_threshold):
                fan_on_needed = True
                reasons.append(f"Humidity {humidity}% exceeds threshold {self.fan_humidity_threshold}%")
            
            # Check air quality if available
            if air_quality_ppm is not None and air_quality_ppm > self.fan_air_quality_threshold:
                fan_on_needed = True
                reasons.append(f"Air quality {air_quality_ppm}PPM exceeds threshold {self.fan_air_quality_threshold}PPM")
            
            decisions['fan_should_be_on'] = fan_on_needed
            if reasons:
                decisions['reasons'].extend(reasons)
        
        # Humidifier Automation Logic - Uses target value (humidifier_value)
        if self.humidifier_auto:
            # Turn ON if humidity is below target minus hysteresis
            if humidity < target_humidity - hysteresis:
                decisions['humidifier_should_be_on'] = True
                decisions['reasons'].append(f"Humidity {humidity}% below target {target_humidity}% (activating)")
            # Turn OFF if humidity reaches or exceeds target
            elif humidity >= target_humidity:
                decisions['humidifier_should_be_on'] = False
                decisions['reasons'].append(f"Humidity {humidity}% reached target {target_humidity}% (deactivating)")
            # Keep running if already ON and still below target
            elif self.humidifier_on and humidity < target_humidity:
                decisions['humidifier_should_be_on'] = True
                decisions['reasons'].append(f"Humidity {humidity}% approaching target {target_humidity}% (maintaining)")
            # Otherwise keep current state
            else:
                decisions['humidifier_should_be_on'] = self.humidifier_on
        
        # Heater Automation Logic - Uses target value (heater_value)
        if self.heater_auto:
            # Turn ON if temperature is below target minus hysteresis
            if temperature < target_temperature - hysteresis:
                decisions['heater_should_be_on'] = True
                decisions['reasons'].append(f"Temperature {temperature}°C below target {target_temperature}°C (activating)")
            # Turn OFF if temperature reaches or exceeds target
            elif temperature >= target_temperature:
                decisions['heater_should_be_on'] = False
                decisions['reasons'].append(f"Temperature {temperature}°C reached target {target_temperature}°C (deactivating)")
            # Keep running if already ON and still below target
            elif self.heater_on and temperature < target_temperature:
                decisions['heater_should_be_on'] = True
                decisions['reasons'].append(f"Temperature {temperature}°C approaching target {target_temperature}°C (maintaining)")
            # Otherwise keep current state
            else:
                decisions['heater_should_be_on'] = self.heater_on
        
        return decisions


# --- NEW: AutomationLog Model ---
class AutomationLog(models.Model):
    """
    Tracks automated actions taken by the predictive maintenance system.
    This allows the system to learn from its own actions over time.
    """
    ACTION_CHOICES = [
        ('HUMIDIFIER_ON', 'Humidifier Activated'),
        ('HUMIDIFIER_OFF', 'Humidifier Deactivated'),
        ('VENTILATION_ON', 'Ventilation Activated'),
        ('VENTILATION_OFF', 'Ventilation Deactivated'),
        ('HEATER_ON', 'Heater Activated'),
        ('HEATER_OFF', 'Heater Deactivated'),
    ]
    
    triggered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='automation_logs', help_text="User who triggered or system if automatic")
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    reason = models.TextField(help_text="Why this action was taken")
    
    # Sensor readings at time of action
    temperature_before = models.DecimalField(max_digits=4, decimal_places=1)
    humidity_before = models.DecimalField(max_digits=4, decimal_places=1)
    co2_before = models.IntegerField()
    
    # ML prediction confidence (0-100%)
    confidence = models.DecimalField(max_digits=5, decimal_places=2, help_text="Model confidence percentage")
    
    # Was this action effective? (can be updated later)
    was_effective = models.BooleanField(null=True, blank=True, help_text="Did this prevent a warning?")
    
    def __str__(self):
        return f"{self.get_action_display()} at {self.timestamp}"


# --- NEW: Disease Detection Model ---
class DiseaseDetection(models.Model):
    """
    Stores mushroom disease detection results from image analysis.
    """
    DISEASE_CHOICES = [
        ('healthy', 'Healthy'),
        ('green_mold', 'Green Mold (Trichoderma)'),
        ('bacterial_blotch', 'Bacterial Blotch'),
        ('cobweb', 'Cobweb Disease'),
        ('dry_bubble', 'Dry Bubble'),
    ]
    
    SEVERITY_CHOICES = [
        ('none', 'None'),
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    
    timestamp = models.DateTimeField(auto_now_add=True)
    batch = models.ForeignKey(ProductionBatch, on_delete=models.SET_NULL, null=True, blank=True, help_text="Associated production batch")
    image = models.ImageField(upload_to='disease_images/', help_text="Uploaded mushroom image")
    
    # Detection results
    detected_disease = models.CharField(max_length=50, choices=DISEASE_CHOICES)
    confidence = models.DecimalField(max_digits=5, decimal_places=2, help_text="Model confidence percentage")
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='none')
    
    # Disease information
    description = models.TextField(blank=True)
    treatment_recommendation = models.TextField(blank=True)
    prevention_tips = models.TextField(blank=True)
    
    # Action taken
    action_taken = models.TextField(blank=True, help_text="What action was taken to address the issue")
    resolved = models.BooleanField(default=False, help_text="Has the issue been resolved?")
    resolved_date = models.DateTimeField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Disease Detection'
        verbose_name_plural = 'Disease Detections'
    
    def __str__(self):
        return f"{self.get_detected_disease_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


# --- E-COMMERCE MODELS ---

class CustomerAdminMessage(models.Model):
    """Simple customer-admin chat messages grouped by customer."""
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customer_chats')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_chats')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Chat from {self.sender.username} to {self.customer.username}"


def payment_proof_upload_path(instance, filename):
    """Store customer payment proofs in per-order folders with randomized names."""
    extension = os.path.splitext(filename)[1].lower() or '.jpg'
    order_token = (instance.order_number or f"order_{instance.pk or 'new'}").replace('/', '_')
    return os.path.join('payment_proofs', order_token, f"{uuid.uuid4().hex}{extension}")


def gcash_qr_upload_path(instance, filename):
    """Store the admin-managed GCash QR image with a randomized filename."""
    extension = os.path.splitext(filename)[1].lower() or '.png'
    return os.path.join('gcash_qr_codes', f"gcash_qr_{uuid.uuid4().hex}{extension}")

class Order(models.Model):
    """E-commerce orders from customers"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PENDING_VERIFICATION', 'Pending Verification'),
        ('PROCESSING', 'Processing'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    order_number = models.CharField(max_length=50, unique=True, editable=False)
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20)
    
    # Shipping details
    shipping_address = models.TextField()
    shipping_city = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=20)
    
    # Customer GPS coordinates for accurate delivery
    customer_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Customer delivery location latitude"
    )
    customer_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Customer delivery location longitude"
    )
    
    # Order details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Payment information
    PAYMENT_METHOD_CHOICES = [
        ('COD', 'Cash on Delivery'),
        ('GCASH', 'GCash (Manual)'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('UNPAID', 'Unpaid'),
        ('PENDING', 'Payment Pending'),
        ('PAID', 'Paid'),
        ('FAILED', 'Payment Failed'),
        ('REFUNDED', 'Refunded'),
    ]
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, default='COD')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='UNPAID')
    is_paid = models.BooleanField(default=False)
    
    # GCash transaction details
    transaction_id = models.CharField(max_length=100, blank=True, null=True, help_text="Payment gateway transaction ID")
    payment_reference = models.CharField(max_length=100, blank=True, null=True, help_text="Payment reference number")
    payment_proof_image = models.ImageField(
        upload_to=payment_proof_upload_path,
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'gif'])],
        help_text="Customer-uploaded screenshot proof for manual GCash payment"
    )
    paid_at = models.DateTimeField(null=True, blank=True, help_text="When payment was confirmed")
    
    # Notes
    customer_notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)

    # Live order location tracking (updated by admin)
    current_location_status = models.CharField(max_length=120, blank=True, help_text="Current delivery status/location note")
    current_location_address = models.TextField(blank=True, help_text="Current delivery address/area update")
    current_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            # Generate unique order number
            import random
            import string
            prefix = 'ORD'
            random_str = ''.join(random.choices(string.digits, k=8))
            self.order_number = f"{prefix}{random_str}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Order {self.order_number} - {self.customer_name}"


class OrderItem(models.Model):
    """Individual items in an e-commerce order"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_kg = models.DecimalField(max_digits=5, decimal_places=1)
    price_per_kg = models.DecimalField(max_digits=6, decimal_places=2)
    unit = models.CharField(max_length=10, choices=Product.UNIT_CHOICES, default='kg')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"{self.quantity_kg} {self.unit} of {self.product.name}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate subtotal
        self.subtotal = self.quantity_kg * self.price_per_kg
        super().save(*args, **kwargs)


class Cart(models.Model):
    """Shopping cart for e-commerce (session-based or user-based)"""
    session_key = models.CharField(max_length=40, unique=True, help_text="Browser session identifier")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='carts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # Ensure session_key is set for user-based carts
        if self.user and not self.session_key:
            self.session_key = f'user_{self.user.id}_{self.user.username}'
        super().save(*args, **kwargs)
    
    def __str__(self):
        if self.user:
            return f"Cart {self.id} - User: {self.user.username}"
        return f"Cart {self.id} - Session: {self.session_key[:10]}"
    
    @property
    def total(self):
        return sum(item.subtotal for item in self.items.all())


class CartItem(models.Model):
    """Items in a shopping cart"""
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity_kg = models.DecimalField(max_digits=5, decimal_places=1)
    
    class Meta:
        unique_together = ('cart', 'product')
    
    def __str__(self):
        return f"{self.quantity_kg} {self.product.unit} of {self.product.name}"
    
    @property
    def subtotal(self):
        return self.quantity_kg * self.product.price_per_kg


class ProductReview(models.Model):
    """Customer reviews and ratings for products - linked to specific orders"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviews', help_text="Order this review is linked to")
    rating = models.IntegerField(
        choices=[(1, '1 Star'), (2, '2 Stars'), (3, '3 Stars'), (4, '4 Stars'), (5, '5 Stars')],
        help_text="Rating from 1 to 5 stars"
    )
    comment = models.TextField(blank=True, help_text="Optional review comment")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        # Allow one review per product per order (user can review same product multiple times from different orders)
        unique_together = ('product', 'user', 'order')
        ordering = ['-created_at']
    
    def __str__(self):
        order_info = f" (Order: {self.order.order_number})" if self.order else ""
        return f"{self.user.username} - {self.product.name} ({self.rating}★){order_info}"


def review_media_upload_path(instance, filename):
    """Generate upload path for review media files"""
    import os
    from django.utils import timezone
    ext = filename.split('.')[-1].lower()
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    new_filename = f"review_{instance.review.id}_{timestamp}.{ext}"
    return os.path.join('review_media', str(instance.review.product.id), new_filename)


class ReviewMedia(models.Model):
    """Media attachments (photos/videos) for product reviews"""
    MEDIA_TYPE_CHOICES = [
        ('IMAGE', 'Image'),
        ('VIDEO', 'Video'),
    ]
    
    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name='media')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default='IMAGE')
    file = models.FileField(upload_to='review_media/')
    thumbnail = models.ImageField(upload_to='review_media/thumbnails/', null=True, blank=True, help_text="Thumbnail for videos")
    file_size = models.IntegerField(default=0, help_text="File size in bytes")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=True, help_text="Admin can hide inappropriate media")
    
    # Allowed file types and size limits
    ALLOWED_IMAGE_TYPES = ['jpg', 'jpeg', 'png', 'webp', 'gif']
    ALLOWED_VIDEO_TYPES = ['mp4', 'webm', 'mov']
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
    MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB
    
    class Meta:
        ordering = ['uploaded_at']
        verbose_name = 'Review Media'
        verbose_name_plural = 'Review Media'
    
    def __str__(self):
        return f"{self.media_type} for review {self.review.id}"
    
    @property
    def is_image(self):
        return self.media_type == 'IMAGE'
    
    @property
    def is_video(self):
        return self.media_type == 'VIDEO'
    
    @property
    def file_extension(self):
        if self.file:
            return self.file.name.split('.')[-1].lower()
        return ''
    
    @classmethod
    def validate_file(cls, file):
        """
        Validate uploaded file type and size.
        Returns tuple: (is_valid, media_type, error_message)
        """
        if not file:
            return False, None, "No file provided"
        
        # Get file extension
        filename = file.name.lower()
        ext = filename.split('.')[-1] if '.' in filename else ''
        
        # Check file type
        if ext in cls.ALLOWED_IMAGE_TYPES:
            media_type = 'IMAGE'
            max_size = cls.MAX_IMAGE_SIZE
            max_size_label = "5 MB"
        elif ext in cls.ALLOWED_VIDEO_TYPES:
            media_type = 'VIDEO'
            max_size = cls.MAX_VIDEO_SIZE
            max_size_label = "50 MB"
        else:
            allowed = cls.ALLOWED_IMAGE_TYPES + cls.ALLOWED_VIDEO_TYPES
            return False, None, f"File type '.{ext}' not allowed. Allowed types: {', '.join(allowed)}"
        
        # Check file size
        if file.size > max_size:
            return False, None, f"File too large. Maximum size for {media_type.lower()}s is {max_size_label}"
        
        return True, media_type, None


class Wishlist(models.Model):
    """User's wishlist/favorites"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-added_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.product.name}"


class ProductImage(models.Model):
    """Multiple images for products"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='product_images/')
    is_primary = models.BooleanField(default=False, help_text="Primary/featured image")
    display_order = models.IntegerField(default=0, help_text="Order in gallery")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-is_primary', 'display_order']
    
    def __str__(self):
        primary = " (Primary)" if self.is_primary else ""
        return f"{self.product.name} - Image {self.id}{primary}"


class RecentlyViewed(models.Model):
    """Track recently viewed products for personalization"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='recently_viewed')
    session_key = models.CharField(max_length=40, null=True, blank=True, help_text="For anonymous users")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='viewed_by')
    viewed_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['user', '-viewed_at']),
            models.Index(fields=['session_key', '-viewed_at']),
        ]
    
    def __str__(self):
        viewer = self.user.username if self.user else f"Session {self.session_key[:10]}"
        return f"{viewer} viewed {self.product.name}"


class StoreSettings(models.Model):
    """Singleton model for store settings including location for shipping calculation"""
    id = models.AutoField(primary_key=True)
    
    # Store Location
    store_name = models.CharField(max_length=200, default='KABUTOMATE Farm')
    store_address = models.TextField(blank=True, help_text="Store physical address")
    store_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Store latitude coordinate"
    )
    store_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Store longitude coordinate"
    )
    
    # Shipping Fee Settings
    minimum_base_fee = models.DecimalField(
        max_digits=6, decimal_places=2, default=20.00,
        help_text="Minimum delivery fee for the first X km"
    )
    minimum_base_distance_km = models.DecimalField(
        max_digits=6, decimal_places=2, default=3.00,
        help_text="Distance in km covered by the minimum base fee"
    )
    fee_per_km = models.DecimalField(
        max_digits=6, decimal_places=2, default=10.00,
        help_text="Additional fee per kilometer beyond base distance"
    )
    free_shipping_threshold = models.DecimalField(
        max_digits=8, decimal_places=2, default=1000.00,
        help_text="Order total above this amount gets free shipping"
    )
    max_delivery_distance_km = models.DecimalField(
        max_digits=6, decimal_places=2, default=50.00,
        help_text="Maximum delivery distance in kilometers"
    )
    
    # Order Settings
    minimum_order_amount = models.DecimalField(
        max_digits=8, decimal_places=2, default=300.00,
        help_text="Minimum order amount required to place an order"
    )

    # Manual GCash checkout settings
    gcash_qr_code = models.ImageField(
        upload_to=gcash_qr_upload_path,
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
        help_text="Admin-uploaded GCash QR code used for manual checkout payments"
    )
    
    # Timestamps
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        self.pk = 1
        super(StoreSettings, self).save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        pass
    
    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
    
    def calculate_shipping_fee(self, customer_lat, customer_lng, order_total=0):
        """
        Calculate shipping fee based on distance from store to customer.
        - First X km (minimum_base_distance_km): minimum_base_fee (e.g., ₱20 for first 3km)
        - Beyond that: minimum_base_fee + (extra km × fee_per_km)
        - Free shipping for orders above threshold
        """
        import math
        from decimal import Decimal
        
        # Free shipping for orders above threshold
        if order_total >= float(self.free_shipping_threshold):
            return Decimal('0.00'), 0, 'Free shipping on orders ₱{:,.0f}+'.format(float(self.free_shipping_threshold))
        
        # If store coordinates not set, return minimum base fee
        if not self.store_latitude or not self.store_longitude:
            return self.minimum_base_fee, None, 'Standard delivery fee'
        
        # If customer coordinates not provided, return minimum base fee
        if not customer_lat or not customer_lng:
            return self.minimum_base_fee, None, 'Standard delivery fee'
        
        # Haversine formula to calculate distance
        R = 6371  # Earth's radius in kilometers
        
        lat1 = math.radians(float(self.store_latitude))
        lat2 = math.radians(float(customer_lat))
        dlat = math.radians(float(customer_lat) - float(self.store_latitude))
        dlng = math.radians(float(customer_lng) - float(self.store_longitude))
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance_km = R * c
        
        # Check if within delivery range
        if distance_km > float(self.max_delivery_distance_km):
            return None, distance_km, 'Delivery not available for this location (beyond {} km)'.format(self.max_delivery_distance_km)
        
        # Calculate fee based on distance
        base_distance = float(self.minimum_base_distance_km)
        
        if distance_km <= base_distance:
            # Within base distance - just minimum fee
            shipping_fee = float(self.minimum_base_fee)
        else:
            # Beyond base distance - minimum fee + extra distance × fee per km
            extra_distance = distance_km - base_distance
            shipping_fee = float(self.minimum_base_fee) + (extra_distance * float(self.fee_per_km))
        
        shipping_fee = Decimal(str(round(shipping_fee, 2)))
        
        return shipping_fee, round(distance_km, 1), '₱{:,.2f} ({:.1f} km)'.format(float(shipping_fee), distance_km)
    
    def __str__(self):
        return f"Store Settings - {self.store_name}"
    
    class Meta:
        verbose_name = 'Store Settings'
        verbose_name_plural = 'Store Settings'