"""Yield prediction helpers trained from historical harvest records."""

from __future__ import annotations

import os
import pickle
from datetime import date

import numpy as np
import pandas as pd
from django.conf import settings
from django.utils import timezone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from .models import ProductionBatch


MODEL_FILENAME = 'mushroom_yield_model.pkl'
FEATURE_COLUMNS = [
    'product_id',
    'start_month',
    'growth_days',
    'cost',
    'same_product_prev_yield_1',
    'same_product_prev_avg_3',
    'farm_prev_avg_5',
]


def get_yield_model_path() -> str:
    return os.path.join(settings.BASE_DIR, MODEL_FILENAME)


def _parse_date(value):
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _parse_float(value):
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rolling_average(values, window):
    if not values:
        return np.nan
    return float(np.mean(values[-window:]))


def _build_harvest_history_frame():
    batches = list(
        ProductionBatch.objects.filter(
            status='HARVESTED',
            yield_kg__isnull=False,
            harvest_date__isnull=False,
            start_date__isnull=False,
        )
        .select_related('product')
        .order_by('harvest_date', 'start_date', 'id')
    )

    records = []
    farm_history = []
    product_history = {}

    for batch in batches:
        harvested_yield = float(batch.yield_kg)
        product_id = batch.product_id or -1
        product_values = product_history.get(product_id, [])
        start_date = batch.start_date
        harvest_date = batch.harvest_date
        growth_days = max((harvest_date - start_date).days + 1, 1)

        records.append({
            'product_id': product_id,
            'start_month': start_date.month,
            'growth_days': growth_days,
            'cost': float(batch.cost) if batch.cost is not None else np.nan,
            'same_product_prev_yield_1': float(product_values[-1]) if product_values else np.nan,
            'same_product_prev_avg_3': _rolling_average(product_values, 3),
            'farm_prev_avg_5': _rolling_average(farm_history, 5),
            'yield_kg': harvested_yield,
        })

        farm_history.append(harvested_yield)
        product_history.setdefault(product_id, []).append(harvested_yield)

    return pd.DataFrame(records)


def _build_feature_row(product_id=None, start_date=None, cost=None):
    history = _build_harvest_history_frame()
    parsed_start_date = _parse_date(start_date)
    current_date = parsed_start_date or timezone.now().date()
    parsed_cost = _parse_float(cost)

    if history.empty:
        return pd.DataFrame([{
            'product_id': product_id if product_id is not None else -1,
            'start_month': current_date.month,
            'growth_days': np.nan,
            'cost': parsed_cost if parsed_cost is not None else np.nan,
            'same_product_prev_yield_1': np.nan,
            'same_product_prev_avg_3': np.nan,
            'farm_prev_avg_5': np.nan,
        }])

    if product_id is not None:
        product_history = history.loc[history['product_id'] == int(product_id), 'yield_kg'].tolist()
    else:
        product_history = []

    farm_history = history['yield_kg'].tolist()
    growth_days = None
    if parsed_start_date:
        growth_days = max((timezone.now().date() - parsed_start_date).days + 1, 1)

    return pd.DataFrame([{
        'product_id': int(product_id) if product_id is not None else -1,
        'start_month': current_date.month,
        'growth_days': growth_days if growth_days is not None else np.nan,
        'cost': parsed_cost if parsed_cost is not None else np.nan,
        'same_product_prev_yield_1': float(product_history[-1]) if product_history else np.nan,
        'same_product_prev_avg_3': _rolling_average(product_history, 3),
        'farm_prev_avg_5': _rolling_average(farm_history, 5),
    }])


def train_yield_model():
    """Train a yield model from historical harvest records."""
    df = _build_harvest_history_frame()
    if len(df) < 8:
        raise ValueError('Need at least 8 harvested batches with yield data to train the yield model.')

    features = FEATURE_COLUMNS
    X = df[features]
    y = df['yield_kg']

    split_index = max(int(len(df) * 0.8), len(df) - 3)
    split_index = min(split_index, len(df) - 1)
    X_train, X_test = X.iloc[:split_index], X.iloc[split_index:]
    y_train, y_test = y.iloc[:split_index], y.iloc[split_index:]

    preprocessor = ColumnTransformer(
        transformers=[
            ('numeric', SimpleImputer(strategy='median'), [
                'start_month',
                'growth_days',
                'cost',
                'same_product_prev_yield_1',
                'same_product_prev_avg_3',
                'farm_prev_avg_5',
            ]),
            ('categorical', OneHotEncoder(handle_unknown='ignore'), ['product_id']),
        ]
    )

    pipeline = Pipeline([
        ('preprocessor', preprocessor),
        ('model', RandomForestRegressor(n_estimators=250, random_state=42)),
    ])

    pipeline.fit(X_train, y_train)

    metrics = {
        'mae': None,
        'rmse': None,
        'r2': None,
    }
    if len(X_test) > 0:
        predictions = pipeline.predict(X_test)
        metrics = {
            'mae': float(mean_absolute_error(y_test, predictions)),
            'rmse': float(np.sqrt(mean_squared_error(y_test, predictions))),
            'r2': float(r2_score(y_test, predictions)) if len(y_test) > 1 else None,
        }

    artifact = {
        'pipeline': pipeline,
        'features': features,
        'metrics': metrics,
        'trained_at': timezone.now().isoformat(),
        'training_rows': len(df),
        'farm_average_yield': float(df['yield_kg'].mean()),
        'product_average_yield': {
            str(product_id): float(group['yield_kg'].mean())
            for product_id, group in df.groupby('product_id')
        },
    }

    model_path = get_yield_model_path()
    with open(model_path, 'wb') as handle:
        pickle.dump(artifact, handle)

    return artifact


def load_yield_model():
    model_path = get_yield_model_path()
    if not os.path.exists(model_path):
        return None

    with open(model_path, 'rb') as handle:
        artifact = pickle.load(handle)

    if isinstance(artifact, dict):
        return artifact

    return {
        'pipeline': artifact,
        'features': FEATURE_COLUMNS,
        'metrics': {},
        'trained_at': None,
        'training_rows': None,
        'farm_average_yield': None,
        'product_average_yield': {},
    }


def calculate_predicted_yield(product_id=None, start_date=None, cost=None):
    """Predict yield using historical harvest-based training data."""
    if product_id in (None, ''):
        normalized_product_id = None
    else:
        try:
            normalized_product_id = int(product_id)
        except (TypeError, ValueError):
            normalized_product_id = None

    artifact = load_yield_model()
    feature_row = _build_feature_row(
        product_id=normalized_product_id,
        start_date=start_date,
        cost=cost,
    )

    if artifact and artifact.get('pipeline'):
        prediction = artifact['pipeline'].predict(feature_row[artifact['features']])[0]
        if np.isfinite(prediction):
            return round(float(prediction), 2)

    history = _build_harvest_history_frame()
    if history.empty:
        return 0.0

    if normalized_product_id is not None:
        product_history = history.loc[history['product_id'] == normalized_product_id, 'yield_kg']
        if len(product_history) > 0:
            return round(float(product_history.mean()), 2)

    return round(float(history['yield_kg'].mean()), 2)