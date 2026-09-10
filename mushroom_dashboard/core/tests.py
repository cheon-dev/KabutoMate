import json

from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import Client, TestCase


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
