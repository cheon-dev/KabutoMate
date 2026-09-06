import logging
from urllib.parse import quote

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


class GeminiConfigurationError(Exception):
    pass


class GeminiRequestError(Exception):
    pass


def ask_gemini(message, history=None, audience='customer', context=''):
    """Send a bounded conversation to Gemini without exposing the API key."""
    api_key = getattr(settings, 'GEMINI_API_KEY', '').strip()
    if not api_key:
        raise GeminiConfigurationError('Gemini is not configured yet.')

    system_prompt = (
        'You are KabutoMate AI, a helpful assistant inside a mushroom farm and '
        'e-commerce dashboard. Be concise, practical, and honest. Do not claim '
        'to have performed an action or know live data unless it is provided in '
        'the conversation. '
    )
    if audience == 'admin':
        system_prompt += (
            'The user is an administrator. Focus on farm operations, sensors, '
            'production, inventory, orders, sales, and dashboard guidance.'
        )
    else:
        system_prompt += (
            'The user is a customer. Focus on products, shopping, orders, '
            'payments, delivery, account help, and support guidance.'
        )
    if context:
        system_prompt += (
            '\n\nHere is live application data from the dashboard. Use it to answer '
            'catalog and product questions. Do not say that you lack access to '
            'this data, and do not invent values that are not listed below. '
            f'\n{context}'
        )

    contents = []
    for item in (history or [])[-10:]:
        if not isinstance(item, dict):
            continue
        role = item.get('role')
        text = str(item.get('text') or '').strip()
        if role in ('user', 'model') and text:
            contents.append({'role': role, 'parts': [{'text': text[:2000]}]})
    contents.append({'role': 'user', 'parts': [{'text': message[:4000]}]})

    model = quote(getattr(settings, 'GEMINI_MODEL', 'gemini-3.6-flash'), safe='')
    endpoint = (
        f'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{model}:generateContent?key={quote(api_key, safe="")}'
    )
    payload = {
        'system_instruction': {'parts': [{'text': system_prompt}]},
        'contents': contents,
        'generationConfig': {
            'temperature': 0.4,
            'maxOutputTokens': 700,
        },
    }

    try:
        response = requests.post(endpoint, json=payload, timeout=30)
    except requests.RequestException as exc:
        logger.warning('Gemini request failed: %s', exc)
        raise GeminiRequestError('The AI assistant is temporarily unavailable.') from exc

    if response.status_code >= 400:
        logger.warning('Gemini API returned status %s', response.status_code)
        raise GeminiRequestError('The AI assistant could not process that request.')

    try:
        data = response.json()
        parts = data['candidates'][0]['content']['parts']
        answer = ''.join(str(part.get('text', '')) for part in parts).strip()
    except (KeyError, IndexError, TypeError, ValueError):
        logger.warning('Gemini response did not contain a usable answer')
        raise GeminiRequestError('The AI assistant returned an invalid response.')

    if not answer:
        raise GeminiRequestError('The AI assistant returned an empty response.')
    return answer
