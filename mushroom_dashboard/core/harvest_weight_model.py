import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from django.conf import settings


MODEL_FILENAME = 'predictive_harvest_weight_v3_model.pkl'
FEATURES = [
    'Growing_Days',
    'Humidity_pct',
    'Temperature_C',
    'Air_Quality_CO2_ppm',
]
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

    feature_ranges = training_data.get('feature_ranges')
    if not isinstance(feature_ranges, dict):
        raise HarvestWeightModelError('Harvest weight model has no valid feature ranges.')

    for feature in FEATURES:
        try:
            bounds = feature_ranges[feature]
            if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
                raise ValueError
            minimum, maximum = (float(bound) for bound in bounds)
        except (KeyError, TypeError, ValueError) as exc:
            raise HarvestWeightModelError(
                f'Harvest weight model has no valid range for {feature}.'
            ) from exc

        if not np.isfinite([minimum, maximum]).all() or minimum > maximum:
            raise HarvestWeightModelError(
                f'Harvest weight model has an invalid range for {feature}.'
            )

    return artifact


def predict_harvest_weight_grams(
    growing_days,
    humidity_pct,
    temperature_c,
    air_quality_ppm,
):
    raw_values = [growing_days, humidity_pct, temperature_c, air_quality_ppm]
    input_values = {}
    for feature, raw_value in zip(FEATURES, raw_values):
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f'{feature} must be a valid number.') from exc
        if not np.isfinite(value):
            raise ValueError(f'{feature} must be a finite number.')
        input_values[feature] = value

    artifact = load_harvest_weight_model()
    feature_ranges = artifact['training_data']['feature_ranges']
    for feature, value in input_values.items():
        minimum, maximum = (float(bound) for bound in feature_ranges[feature])
        if value < minimum or value > maximum:
            raise ValueError(
                f'{feature} must be within the observed range '
                f'[{minimum:g}, {maximum:g}].'
            )

    prediction = artifact['model'].predict(
        pd.DataFrame([input_values], columns=FEATURES)
    )
    weight_grams = float(prediction[0])
    if not np.isfinite(weight_grams) or weight_grams <= 0:
        raise HarvestWeightModelError('The harvest weight model returned an invalid prediction.')

    return round(weight_grams, 1)
