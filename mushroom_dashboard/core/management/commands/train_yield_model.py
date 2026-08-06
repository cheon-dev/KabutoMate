"""Train the yield prediction model from harvested batch history."""

from django.core.management.base import BaseCommand

from core.yield_model import get_yield_model_path, train_yield_model


class Command(BaseCommand):
    help = 'Train the yield model using harvested batch history'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🍄 YIELD MODEL TRAINING'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

        try:
            artifact = train_yield_model()
        except ValueError as exc:
            self.stdout.write(self.style.ERROR(f'❌ {exc}'))
            return

        self.stdout.write(self.style.SUCCESS(f"✅ Trained on {artifact['training_rows']} harvested batches"))
        self.stdout.write(self.style.SUCCESS(f"✅ Model saved to: {get_yield_model_path()}"))
        self.stdout.write('\nMetrics:')
        metrics = artifact.get('metrics', {})
        self.stdout.write(f"  MAE: {metrics.get('mae')}")
        self.stdout.write(f"  RMSE: {metrics.get('rmse')}")
        self.stdout.write(f"  R²: {metrics.get('r2')}")
        self.stdout.write('\nThis model is now based on the farmer\'s previous harvested batches.')