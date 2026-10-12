from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import Product, YieldTrainingSample


class Command(BaseCommand):
    help = 'Seed hidden Oyster Mushroom yield samples for model training'

    SAMPLE_COUNT = 80

    def handle(self, *args, **options):
        product = Product.objects.filter(
            name__iexact='Oyster Mushroom',
            product_type='fresh',
        ).first()
        if not product:
            raise CommandError('Fresh product "Oyster Mushroom" was not found.')

        today = timezone.now().date()
        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for index in range(1, self.SAMPLE_COUNT + 1):
                growth_days = 12 + ((index * 7) % 19)
                yield_grams = 650 + min(
                    100,
                    ((growth_days - 12) * 5) + ((index * 13) % 11),
                )
                start_date = today - timedelta(
                    days=40 + (24 * (self.SAMPLE_COUNT - index))
                )
                harvest_date = start_date + timedelta(days=growth_days - 1)
                sample_code = f'SYNTHETIC-OYSTER-{index:03d}'
                _, created = YieldTrainingSample.objects.update_or_create(
                    sample_code=sample_code,
                    defaults={
                        'product': product,
                        'start_date': start_date,
                        'harvest_date': harvest_date,
                        'yield_grams': yield_grams,
                        'cost': Decimal('600.00') + Decimal(
                            (growth_days * 35) + ((index % 9) * 75)
                        ),
                    },
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Seeded Oyster Mushroom training data: {created_count} created, '
            f'{updated_count} updated, yields 650-750 g with varied growth '
            'durations and costs.'
        ))
