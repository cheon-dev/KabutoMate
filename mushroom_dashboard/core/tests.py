import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .ai_service import ask_gemini
from .ai_context import build_ai_context
from .models import (
    Notification,
    Order,
    OrderItem,
    Product,
    ProductionBatch,
    Sale,
    SensorReading,
    StoreSettings,
    WaterRefillLog,
    WaterRefillStatus,
    YieldTrainingSample,
)
from .shipping import calculate_shipping_fee
from .yield_model import _build_harvest_history_frame
from .views import calculate_growth_days


class LoginAuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def test_login_accepts_email_as_username(self):
        User = get_user_model()
        user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='StrongPass123!'
        )
        user.profile.is_email_verified = True
        user.profile.save(update_fields=['is_email_verified'])

        login_page = self.client.get('/login/')
        csrf_token = login_page.cookies['csrftoken'].value
        response = self.client.post(
            '/login/',
            data=json.dumps({'username': 'testuser@example.com', 'password': 'StrongPass123!'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertIn('redirect_url', response.json())
        self.assertEqual(self.client.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)
        self.assertFalse(self.client.session.get_expire_at_browser_close())
        self.assertTrue(user.is_authenticated)


class NotificationApiTests(TestCase):
    def test_admin_can_load_notifications(self):
        User = get_user_model()
        admin = User.objects.create_user(
            username='notification-admin',
            password='StrongPass123!',
        )
        admin.profile.role = 'ADMIN'
        admin.profile.save()
        notification = Notification.objects.create(
            title='System alert',
            description='A system alert for the admin.',
            category='system',
            level='warning',
        )
        self.client.force_login(admin)

        response = self.client.get('/api/notifications/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['id'], notification.id)


class WaterRefillApiTests(TestCase):
    def setUp(self):
        self.payload = {
            'device_id': 'ESP32_WATER_REFILL_001',
            'container_status': 'LOW',
            'source_status': 'AVAILABLE',
            'refill_state': 'REFILLING',
            'pump_on': True,
            'sensor_valid': True,
            'last_error': '',
        }

    @override_settings(
        WATER_REFILL_API_KEY='water-test-key',
        WATER_REFILL_DEVICE_ID='ESP32_WATER_REFILL_001',
    )
    def test_report_requires_device_api_key(self):
        response = self.client.post(
            '/api/water-refill/report/',
            data=json.dumps(self.payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(WaterRefillStatus.objects.count(), 0)

    @override_settings(
        WATER_REFILL_API_KEY='water-test-key',
        WATER_REFILL_DEVICE_ID='ESP32_WATER_REFILL_001',
    )
    def test_report_records_status_and_admin_can_read_it(self):
        response = self.client.post(
            '/api/water-refill/report/',
            data=json.dumps(self.payload),
            content_type='application/json',
            HTTP_X_API_KEY='water-test-key',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['refill_state'], 'REFILLING')
        self.assertTrue(response.json()['data']['pump_on'])

        admin = get_user_model().objects.create_user(
            username='water-refill-admin',
            password='StrongPass123!',
        )
        admin.profile.role = 'ADMIN'
        admin.profile.save()
        self.client.force_login(admin)

        admin_response = self.client.get('/api/water-refill/status/')

        self.assertEqual(admin_response.status_code, 200)
        self.assertEqual(admin_response.json()['data']['connection_status'], 'ONLINE')
        self.assertEqual(admin_response.json()['data']['device_id'], 'ESP32_WATER_REFILL_001')

    @override_settings(
        WATER_REFILL_API_KEY='water-test-key',
        WATER_REFILL_DEVICE_ID='ESP32_WATER_REFILL_001',
    )
    def test_completed_refill_records_completion_and_notification(self):
        first_response = self.client.post(
            '/api/water-refill/report/',
            data=json.dumps(self.payload),
            content_type='application/json',
            HTTP_X_API_KEY='water-test-key',
        )
        self.assertEqual(first_response.status_code, 200)

        completed_payload = {
            **self.payload,
            'container_status': 'NORMAL',
            'refill_state': 'IDLE',
            'pump_on': False,
        }
        second_response = self.client.post(
            '/api/water-refill/report/',
            data=json.dumps(completed_payload),
            content_type='application/json',
            HTTP_X_API_KEY='water-test-key',
        )

        self.assertEqual(second_response.status_code, 200)
        status = WaterRefillStatus.objects.get(pk=1)
        self.assertIsNotNone(status.last_refill_started_at)
        self.assertIsNotNone(status.last_refill_completed_at)
        self.assertTrue(
            any(event['key'] == 'water_refill_completed'
                for event in second_response.json()['notification_events'])
        )
        self.assertTrue(Notification.objects.filter(title='Water Refill Completed').exists())

    def _report(self, **overrides):
        payload = {**self.payload, **overrides}
        return self.client.post(
            '/api/water-refill/report/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_API_KEY='water-test-key',
        )

    def _login_admin(self):
        admin = get_user_model().objects.create_user(
            username='water-refill-log-admin',
            password='StrongPass123!',
        )
        admin.profile.role = 'ADMIN'
        admin.profile.save()
        self.client.force_login(admin)
        return admin

    @override_settings(
        WATER_REFILL_API_KEY='water-test-key',
        WATER_REFILL_DEVICE_ID='ESP32_WATER_REFILL_001',
    )
    def test_pump_start_creates_refill_log_with_timestamp(self):
        response = self._report()

        self.assertEqual(response.status_code, 200)
        log = WaterRefillLog.objects.get()
        self.assertEqual(log.event, 'REFILL_STARTED')
        self.assertEqual(log.refill_state, 'REFILLING')
        self.assertTrue(log.pump_on)
        self.assertIsNotNone(log.timestamp)
        self.assertIn('Pump turned on', log.message)

    @override_settings(
        WATER_REFILL_API_KEY='water-test-key',
        WATER_REFILL_DEVICE_ID='ESP32_WATER_REFILL_001',
    )
    def test_completed_refill_logs_duration(self):
        self._report()
        self._report(container_status='NORMAL', refill_state='IDLE', pump_on=False)

        logs = list(WaterRefillLog.objects.order_by('timestamp', 'id'))
        self.assertEqual([log.event for log in logs], ['REFILL_STARTED', 'REFILL_COMPLETED'])
        self.assertIsNotNone(logs[1].duration_seconds)
        self.assertGreaterEqual(logs[1].duration_seconds, 0)

    @override_settings(
        WATER_REFILL_API_KEY='water-test-key',
        WATER_REFILL_DEVICE_ID='ESP32_WATER_REFILL_001',
    )
    def test_empty_source_logs_failed_refill(self):
        self._report()
        self._report(source_status='LOW', refill_state='SOURCE_EMPTY', pump_on=False)

        log = WaterRefillLog.objects.get(event='REFILL_FAILED')
        self.assertIn('source jug is empty', log.message)
        self.assertFalse(log.pump_on)

    @override_settings(
        WATER_REFILL_API_KEY='water-test-key',
        WATER_REFILL_DEVICE_ID='ESP32_WATER_REFILL_001',
    )
    def test_steady_reports_do_not_duplicate_logs(self):
        self._report()
        self._report()
        self._report()

        self.assertEqual(WaterRefillLog.objects.filter(event='REFILL_STARTED').count(), 1)

    @override_settings(
        WATER_REFILL_API_KEY='water-test-key',
        WATER_REFILL_DEVICE_ID='ESP32_WATER_REFILL_001',
    )
    def test_status_api_includes_recent_logs(self):
        self._report()
        self._login_admin()

        response = self.client.get('/api/water-refill/status/')

        self.assertEqual(response.status_code, 200)
        logs = response.json()['data']['recent_logs']
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]['event'], 'REFILL_STARTED')
        self.assertIn('timestamp', logs[0])

    @override_settings(
        WATER_REFILL_API_KEY='water-test-key',
        WATER_REFILL_DEVICE_ID='ESP32_WATER_REFILL_001',
    )
    def test_logs_endpoint_requires_admin_and_returns_newest_first(self):
        self._report()
        self._report(container_status='NORMAL', refill_state='IDLE', pump_on=False)

        anonymous_response = self.client.get('/api/water-refill/logs/')
        self.assertEqual(anonymous_response.status_code, 302)

        self._login_admin()
        response = self.client.get('/api/water-refill/logs/')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['count'], 2)
        self.assertEqual([log['event'] for log in payload['logs']], ['REFILL_COMPLETED', 'REFILL_STARTED'])

    @override_settings(
        WATER_REFILL_API_KEY='water-test-key',
        WATER_REFILL_DEVICE_ID='ESP32_WATER_REFILL_001',
    )
    def test_logs_endpoint_paginates_ten_per_page(self):
        now = timezone.now()
        for index in range(12):
            WaterRefillLog.objects.create(
                event='REFILL_STARTED',
                timestamp=now - timedelta(minutes=index),
                message=f'log {index}',
            )
        self._login_admin()

        first = self.client.get('/api/water-refill/logs/').json()
        self.assertEqual(first['count'], 10)
        self.assertEqual(first['pagination']['page'], 1)
        self.assertEqual(first['pagination']['page_size'], 10)
        self.assertEqual(first['pagination']['total'], 12)
        self.assertEqual(first['pagination']['total_pages'], 2)
        self.assertTrue(first['pagination']['has_next'])
        self.assertFalse(first['pagination']['has_previous'])

        second = self.client.get('/api/water-refill/logs/?page=2').json()
        self.assertEqual(second['count'], 2)
        self.assertEqual(second['pagination']['page'], 2)
        self.assertFalse(second['pagination']['has_next'])
        self.assertTrue(second['pagination']['has_previous'])


class ShippingDistanceTests(TestCase):
    @patch('core.shipping.requests.get')
    def test_shipping_uses_road_distance_when_routing_is_available(self, get):
        store_settings = StoreSettings.objects.create(
            store_latitude=Decimal('14.5995'),
            store_longitude=Decimal('120.9842'),
            minimum_base_distance_km=Decimal('3.00'),
            minimum_base_fee=Decimal('20.00'),
            fee_per_km=Decimal('10.00'),
        )
        response = Mock()
        response.json.return_value = {
            'routes': [{'distance': 10000}],
        }
        get.return_value = response

        _, distance, _ = calculate_shipping_fee(
            store_settings,
            Decimal('14.6500'),
            Decimal('121.0500'),
        )

        self.assertEqual(distance, 10.0)
        get.assert_called_once()


class GeminiServiceTests(TestCase):
    @override_settings(GEMINI_API_KEY='test-key', GEMINI_MODEL='test-model')
    @patch('core.ai_service.requests.post')
    def test_allows_longer_complete_answers(self, post):
        response = Mock(status_code=200)
        response.json.return_value = {
            'candidates': [
                {'content': {'parts': [{'text': 'A complete answer.'}]}}
            ]
        }
        post.return_value = response

        answer = ask_gemini('How do I grow mushrooms?')

        self.assertEqual(answer, 'A complete answer.')
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['generationConfig']['maxOutputTokens'], 2048)


class AIContextTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.customer = User.objects.create_user(
            username='ai-customer',
            email='ai-customer@example.com',
            password='StrongPass123!',
        )
        self.public_product = Product.objects.create(
            name='Oyster Mushroom',
            stock_kg=Decimal('12.0'),
            price_per_kg=Decimal('180.00'),
            description='Fresh oyster mushrooms',
            is_active=True,
        )
        self.private_product = Product.objects.create(
            name='Private Test Product',
            stock_kg=Decimal('50.0'),
            price_per_kg=Decimal('200.00'),
            is_active=False,
        )
        order = Order.objects.create(
            customer_name='AI Customer',
            customer_email=self.customer.email,
            customer_phone='09170000000',
            shipping_address='Test address',
            shipping_city='Test city',
            shipping_postal_code='1000',
            status='DELIVERED',
            total_amount=Decimal('360.00'),
        )
        OrderItem.objects.create(
            order=order,
            product=self.public_product,
            quantity_kg=Decimal('2.0'),
            price_per_kg=Decimal('180.00'),
            unit='kg',
            subtotal=Decimal('360.00'),
        )
        Sale.objects.create(
            product=self.public_product,
            order=order,
            sale_type='ECOMMERCE',
            quantity_kg=Decimal('2.0'),
            total_price=Decimal('360.00'),
        )
        Sale.objects.create(
            product=self.private_product,
            sale_type='POS',
            quantity_kg=Decimal('3.0'),
            total_price=Decimal('600.00'),
        )

    def test_customer_context_contains_live_public_and_personal_data_only(self):
        context = build_ai_context(self.customer, is_admin=False)

        self.assertIn('Oyster Mushroom', context)
        self.assertIn('ORD', context)
        self.assertIn('SIGNED-IN CUSTOMER ORDER DATA', context)
        self.assertIn('BEST-SELLING DATA', context)
        self.assertNotIn('Private Test Product', context)
        self.assertNotIn('ADMIN INVENTORY SUMMARY', context)

    def test_admin_context_contains_business_data_and_unpublished_products(self):
        context = build_ai_context(self.customer, is_admin=True)

        self.assertIn('Private Test Product', context)
        self.assertIn('ADMIN INVENTORY SUMMARY', context)
        self.assertIn('SALES SUMMARY', context)
        self.assertIn('ORDER AND PAYMENT SUMMARY', context)


class SensorProcessingControlTests(TestCase):
    def test_disabled_sensor_processing_skips_database_work(self):
        response = self.client.post(
            '/api/sensor-data/receive/',
            data=json.dumps({
                'temperature': 17.0,
                'humidity': 85.0,
                'device_id': 'ESP32_TEST',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'disabled')
        self.assertEqual(response.json()['relays']['fan'], False)
        self.assertEqual(SensorReading.objects.count(), 0)

    @override_settings(
        SENSOR_PROCESSING_ENABLED=True,
        SENSOR_MIN_INTERVAL_SECONDS=60,
        ESP32_API_KEY='',
    )
    def test_sensor_readings_are_sampled_server_side(self):
        payload = json.dumps({
            'temperature': 17.0,
            'humidity': 85.0,
            'device_id': 'ESP32_TEST',
        })

        first_response = self.client.post(
            '/api/sensor-data/receive/',
            data=payload,
            content_type='application/json',
        )
        second_response = self.client.post(
            '/api/sensor-data/receive/',
            data=payload,
            content_type='application/json',
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)
        self.assertFalse(second_response.json()['stored'])
        self.assertEqual(SensorReading.objects.count(), 1)


class YieldTrainingSampleTests(TestCase):
    def test_gram_samples_are_converted_to_kg_for_training(self):
        product = Product.objects.create(
            name='Oyster Mushroom',
            stock_kg=Decimal('12.0'),
            price_per_kg=Decimal('180.00'),
            product_type='fresh',
        )
        YieldTrainingSample.objects.create(
            sample_code='SYNTHETIC-TEST-001',
            product=product,
            start_date=date(2026, 1, 1),
            harvest_date=date(2026, 1, 16),
            yield_grams=700,
        )

        history = _build_harvest_history_frame()

        self.assertEqual(len(history), 1)
        self.assertEqual(history.iloc[0]['yield_kg'], 0.7)
        self.assertNotIn('growth_days', history.columns)


class GrowthDayTests(TestCase):
    def test_growth_days_stop_at_harvest_date(self):
        self.assertEqual(
            calculate_growth_days(date(2026, 1, 1), date(2026, 1, 16)),
            16,
        )

    def test_harvested_yield_preserves_gram_precision(self):
        product = Product.objects.create(
            name='Precision Oyster Mushroom',
            stock_kg=Decimal('12.0'),
            price_per_kg=Decimal('180.00'),
            product_type='fresh',
        )
        batch = ProductionBatch.objects.create(
            product=product,
            batch_number='TEST-PRECISION-001',
            start_date=date(2026, 1, 1),
            harvest_date=date(2026, 1, 16),
            yield_kg=Decimal('0.675'),
            status='HARVESTED',
        )

        batch.refresh_from_db()

        self.assertEqual(batch.yield_kg, Decimal('0.675'))
