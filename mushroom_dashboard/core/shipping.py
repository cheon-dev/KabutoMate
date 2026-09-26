"""Shipping calculations that prefer road distance when routing is available."""

import logging
import math

import requests


logger = logging.getLogger(__name__)
OSRM_ROUTE_URL = 'https://router.project-osrm.org/route/v1/driving/{start_lng},{start_lat};{end_lng},{end_lat}'


def get_road_distance_km(start_lat, start_lng, end_lat, end_lng):
    """Return driving distance in kilometers, or None if routing is unavailable."""
    try:
        coordinates = [float(start_lat), float(start_lng), float(end_lat), float(end_lng)]
        if not all(math.isfinite(value) for value in coordinates):
            return None
    except (TypeError, ValueError):
        return None

    url = OSRM_ROUTE_URL.format(
        start_lat=coordinates[0],
        start_lng=coordinates[1],
        end_lat=coordinates[2],
        end_lng=coordinates[3],
    )

    try:
        response = requests.get(
            url,
            params={'overview': 'false', 'alternatives': 'false', 'steps': 'false'},
            headers={'User-Agent': 'KabutoMate/1.0 delivery routing'},
            timeout=4,
        )
        response.raise_for_status()
        route = response.json().get('routes', [{}])[0]
        distance_meters = route.get('distance')
        if distance_meters is None:
            return None
        distance_km = float(distance_meters) / 1000
        return distance_km if math.isfinite(distance_km) and distance_km >= 0 else None
    except (requests.RequestException, TypeError, ValueError, KeyError, IndexError, AttributeError) as error:
        logger.warning('Road distance lookup failed; using straight-line distance: %s', error)
        return None


def calculate_shipping_fee(store_settings, customer_lat, customer_lng, order_total=0):
    """Calculate shipping using road distance with a Haversine fallback."""
    route_distance_km = None
    if (
        store_settings.store_latitude is not None
        and store_settings.store_longitude is not None
        and customer_lat is not None
        and customer_lng is not None
    ):
        route_distance_km = get_road_distance_km(
            store_settings.store_latitude,
            store_settings.store_longitude,
            customer_lat,
            customer_lng,
        )

    return store_settings.calculate_shipping_fee(
        customer_lat,
        customer_lng,
        order_total,
        route_distance_km=route_distance_km,
    )
