import json

from django.contrib.auth import get_user_model
from django.test import TestCase


class LoginAuthenticationTests(TestCase):
    def test_login_accepts_email_as_username(self):
        User = get_user_model()
        user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='StrongPass123!'
        )

        response = self.client.post(
            '/login/',
            data=json.dumps({'username': 'testuser@example.com', 'password': 'StrongPass123!'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertIn('redirect_url', response.json())
        self.assertTrue(user.is_authenticated)
