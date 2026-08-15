"""
Custom allauth adapters for Google OAuth integration
"""
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from django.contrib.auth import get_user_model


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter to handle social account login/signup
    """
    
    def populate_user(self, request, sociallogin, data):
        """
        Auto-populate user fields from social account data
        """
        user = super().populate_user(request, sociallogin, data)
        
        # Generate username from email if not set
        if not user.username and user.email:
            # Use email prefix as username base
            username_base = user.email.split('@')[0]
            username = username_base
            
            # Ensure username is unique
            User = get_user_model()
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{username_base}{counter}"
                counter += 1
            
            user.username = username
        
        return user
    
    def save_user(self, request, sociallogin, form=None):
        """
        Called when a social user is being saved (new signup)
        """
        user = super().save_user(request, sociallogin, form)
        
        # The UserProfile is automatically created by the post_save signal
        # Just ensure the role is set to CUSTOMER for social signups
        if hasattr(user, 'profile'):
            user.profile.role = 'CUSTOMER'
            user.profile.save()
        
        return user


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter to handle redirects after login
    """
    
    def get_login_redirect_url(self, request):
        """
        Redirect based on user role after login
        """
        user = request.user
        
        # Check if user is a Django superuser or staff member
        if user.is_superuser or user.is_staff:
            return '/dashboard/'
        
        # Check if user has a profile and determine role
        try:
            if hasattr(user, 'profile'):
                if user.profile.role == 'ADMIN':
                    return '/dashboard/'
                else:
                    return '/shop/'
        except Exception:
            pass
        
        # Default redirect for customers
        return '/shop/'
