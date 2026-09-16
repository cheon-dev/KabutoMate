import json
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import Client, TestCase, override_settings

from .ai_service import ask_gemini
from .ai_context import build_ai_context
from .models import EnvironmentSettings, Order, OrderItem, Product, Sale


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


class ESP32WiFiProvisioningTests(TestCase):
    def test_only_an_admin_can_update_wifi_credentials(self):
        User = get_user_model()
        admin = User.objects.create_user(
            username='wifi-admin',
            email='wifi-admin@example.com',
            password='StrongPass123!',
        )
        admin.profile.role = 'ADMIN'
        admin.profile.save(update_fields=['role'])
        self.client.force_login(admin)

        response = self.client.post(
            '/api/environment/',
            data=json.dumps({
                'wifi_ssid': 'AdminNetwork',
                'wifi_password': 'admin-password',
                'wifi_password_changed': True,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        wifi_settings = EnvironmentSettings.load()
        self.assertEqual(wifi_settings.wifi_ssid, 'AdminNetwork')
        self.assertEqual(wifi_settings.get_wifi_password(), 'admin-password')

    @override_settings(ESP32_API_KEY='test-device-key')
    def test_device_receives_new_credentials_only_with_device_key(self):
        wifi_settings = EnvironmentSettings.load()
        wifi_settings.set_wifi_credentials('FarmNetwork', 'correct-password')
        wifi_settings.save()

        unauthorized = self.client.get('/api/device/wifi-config/?version=0')
        self.assertEqual(unauthorized.status_code, 401)

        response = self.client.get(
            f'/api/device/wifi-config/?version=0',
            HTTP_X_API_KEY='test-device-key',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['ssid'], 'FarmNetwork')
        self.assertEqual(response.json()['password'], 'correct-password')

        unchanged = self.client.get(
            f'/api/device/wifi-config/?version={wifi_settings.wifi_credentials_version}',
            HTTP_X_API_KEY='test-device-key',
        )
        self.assertFalse(unchanged.json()['credentials_changed'])
        self.assertNotIn('password', unchanged.json())
        self.assertNotIn('correct-password', wifi_settings.wifi_password_encrypted)
