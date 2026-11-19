import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from django.conf import settings


MODEL_FILENAME = 'predictive_harvest_weight_model.pkl'
FEATURES = ['Growing_Days']
TARGET = 'Weight_g'


class HarvestWeightModelError(RuntimeError):
    pass


def get_harvest_weight_model_path():
    return Path(settings.BASE_DIR) / MODEL_FILENAME


def load_harvest_weight_model():
    model_path = get_harvest_weight_model_path()
    if not model_path.is_file():
        raise FileNotFoundError(
            f'Harvest weight model not found at {model_path}. '
            'Run all cells in predictive_maintenance_training.ipynb to create it.'
        )

    try:
        with model_path.open('rb') as model_file:
            artifact = pickle.load(model_file)
    except (pickle.UnpicklingError, EOFError, AttributeError, ImportError, ModuleNotFoundError) as exc:
        raise HarvestWeightModelError(
            f'Could not load the harvest weight model at {model_path}.'
        ) from exc

    if not isinstance(artifact, dict) or artifact.get('features') != FEATURES or artifact.get('target') != TARGET:
        raise HarvestWeightModelError(
            'Harvest weight model artifact has an unexpected feature or target schema.'
        )

    training_data = artifact.get('training_data')
    if not isinstance(training_data, dict) or not callable(getattr(artifact.get('model'), 'predict', None)):
        raise HarvestWeightModelError('Harvest weight model artifact is incomplete.')

    try:
        minimum_days = float(training_data['growing_days_min'])
        maximum_days = float(training_data['growing_days_max'])
    except (KeyError, TypeError, ValueError) as exc:
        raise HarvestWeightModelError('Harvest weight model has no valid growing-day range.') from exc

    if not np.isfinite([minimum_days, maximum_days]).all() or minimum_days > maximum_days:
        raise HarvestWeightModelError('Harvest weight model has an invalid growing-day range.')

    return artifact


def predict_harvest_weight_grams(growing_days):
    try:
        days = float(growing_days)
    except (TypeError, ValueError) as exc:
        raise ValueError('Enter a valid number of growing days.') from exc

    if not np.isfinite(days):
        raise ValueError('Growing days must be a finite number.')

    artifact = load_harvest_weight_model()
    training_data = artifact['training_data']
    minimum_days = float(training_data['growing_days_min'])
    maximum_days = float(training_data['growing_days_max'])
    if days < minimum_days or days > maximum_days:
        raise ValueError(
            f'Growing days must be within the model range '
            f'[{minimum_days:g}, {maximum_days:g}].'
        )

    prediction = artifact['model'].predict(pd.DataFrame({FEATURES[0]: [days]}))
    weight_grams = float(prediction[0])
    if not np.isfinite(weight_grams) or weight_grams <= 0:
        raise HarvestWeightModelError('The harvest weight model returned an invalid prediction.')

    return round(weight_grams, 1)
