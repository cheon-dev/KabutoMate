"""Read-only access to the Philippine Standard Geographic Code dataset."""

from django.core.cache import cache
import requests
import re


PSGC_API = 'https://psgc.gitlab.io/api'


def get_locations(level, parent_code=None):
    """Return PSGC locations for one level, scoped to its parent."""
    paths = {
        'regions': '/regions/',
        'provinces': f'/regions/{parent_code}/provinces/' if parent_code else None,
        'cities': f'/provinces/{parent_code}/cities-municipalities/' if parent_code else None,
        'barangays': f'/cities-municipalities/{parent_code}/barangays/' if parent_code else None,
    }
    path = paths.get(level)
    if not path:
        raise ValueError('Invalid location level or parent code.')
    if parent_code and not re.fullmatch(r'\d{9,10}', parent_code):
        raise ValueError('Invalid Philippine location code.')

    cache_key = f'psgc:{level}:{parent_code or "root"}'
    locations = cache.get(cache_key)
    if locations is None:
        response = requests.get(
            f'{PSGC_API}{path}',
            headers={'User-Agent': 'KABUTOMATE/1.0 Philippine address lookup'},
            timeout=10,
        )
        response.raise_for_status()
        locations = [
            {'code': item['code'], 'name': item['name']}
            for item in response.json()
            if item.get('code') and item.get('name')
        ]
        locations.sort(key=lambda item: item['name'].casefold())
        cache.set(cache_key, locations, 60 * 60 * 24)
    return locations
