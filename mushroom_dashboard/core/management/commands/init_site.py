from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = 'Initialize the Site object required for django-allauth'

    def handle(self, *args, **options):
        # Get or create the site with ID=1
        site, created = Site.objects.get_or_create(
            id=1,
            defaults={
                'domain': 'localhost:8000',
                'name': 'Mushroom Dashboard',
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Site created: {site.domain} ({site.name})'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Site already exists: {site.domain} ({site.name})'
                )
            )
