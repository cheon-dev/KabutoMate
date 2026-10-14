"""Authenticated status API for the dedicated water-refill ESP32."""

import hmac
import json
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import WaterRefillStatus
from .notification_service import (
    evaluate_water_refill_notifications,
    evaluate_water_refill_offline_notification,
)
from .views import admin_required


CONTAINER_STATUSES = {'NORMAL', 'LOW', 'UNKNOWN'}
SOURCE_STATUSES = {'AVAILABLE', 'LOW', 'UNKNOWN'}
REFILL_STATES = {'IDLE', 'REFILLING', 'SOURCE_EMPTY', 'TIMEOUT', 'SENSOR_ERROR'}


def _api_key_error(request):
    expected = getattr(settings, 'WATER_REFILL_API_KEY', '').strip()
    provided = request.headers.get('X-API-Key', '')
    if not expected:
        return JsonResponse({
            'status': 'error',
            'message': 'Water-refill device authentication is not configured.',
        }, status=503)
    if not hmac.compare_digest(provided, expected):
        return JsonResponse({'status': 'error', 'message': 'Invalid device API key.'}, status=401)
    return None


def _serialize_status(status, now=None):
    now = now or timezone.now()
    offline_after = getattr(settings, 'WATER_REFILL_OFFLINE_SECONDS', 300)
    is_online = bool(
        status.last_reported_at
        and status.last_reported_at >= now - timedelta(seconds=offline_after)
    )
    return {
        'device_id': status.device_id,
        'connection_status': 'ONLINE' if is_online else 'OFFLINE',
        'container_status': status.container_status,
        'source_status': status.source_status,
        'refill_state': status.refill_state,
        'pump_on': status.pump_on,
        'sensor_valid': status.sensor_valid,
        'last_error': status.last_error,
        'last_reported_at': status.last_reported_at.isoformat() if status.last_reported_at else None,
        'last_refill_started_at': status.last_refill_started_at.isoformat() if status.last_refill_started_at else None,
        'last_refill_completed_at': status.last_refill_completed_at.isoformat() if status.last_refill_completed_at else None,
        'last_refill_failed_at': status.last_refill_failed_at.isoformat() if status.last_refill_failed_at else None,
    }


@csrf_exempt
@require_http_methods(['POST'])
def receive_water_refill_status(request):
    """Accept the latest local water-refill state from ESP32 #2."""
    auth_error = _api_key_error(request)
    if auth_error:
        return auth_error

    try:
        data = json.loads(request.body)
        device_id = str(data.get('device_id', '')).strip()
        if device_id != getattr(settings, 'WATER_REFILL_DEVICE_ID', '').strip():
            return JsonResponse({'status': 'error', 'message': 'Unknown water-refill device.'}, status=403)

        container_status = str(data.get('container_status', '')).upper()
        source_status = str(data.get('source_status', '')).upper()
        refill_state = str(data.get('refill_state', '')).upper()
        pump_on = data.get('pump_on')
        sensor_valid = data.get('sensor_valid', True)
        last_error = str(data.get('last_error', '')).strip()[:2000]

        if container_status not in CONTAINER_STATUSES:
            raise ValueError('Invalid container_status.')
        if source_status not in SOURCE_STATUSES:
            raise ValueError('Invalid source_status.')
        if refill_state not in REFILL_STATES:
            raise ValueError('Invalid refill_state.')
        if not isinstance(pump_on, bool) or not isinstance(sensor_valid, bool):
            raise ValueError('pump_on and sensor_valid must be boolean values.')

        now = timezone.now()
        with transaction.atomic():
            status = WaterRefillStatus.objects.select_for_update().first()
            if status is None:
                status = WaterRefillStatus(pk=1)

            previous_source_status = status.source_status
            previous_refill_state = status.refill_state
            previous_pump_on = status.pump_on

            status.device_id = device_id
            status.container_status = container_status
            status.source_status = source_status
            status.refill_state = refill_state
            status.pump_on = pump_on
            status.sensor_valid = sensor_valid
            status.last_error = last_error
            status.last_reported_at = now

            if pump_on and not previous_pump_on:
                status.last_refill_started_at = now
            elif (
                previous_pump_on
                and not pump_on
                and container_status == 'NORMAL'
                and source_status == 'AVAILABLE'
                and refill_state == 'IDLE'
            ):
                status.last_refill_completed_at = now

            if refill_state in {'TIMEOUT', 'SENSOR_ERROR'}:
                status.last_refill_failed_at = now

            status.save()
            events = evaluate_water_refill_notifications(
                status,
                previous_source_status=previous_source_status,
                previous_refill_state=previous_refill_state,
            )

        return JsonResponse({
            'status': 'success',
            'message': 'Water-refill status recorded.',
            'data': _serialize_status(status, now=now),
            'notification_events': events,
        })
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON format.'}, status=400)
    except (TypeError, ValueError) as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=500)


@admin_required
@require_http_methods(['GET'])
def water_refill_status_api(request):
    """Return water-refill status for the admin environment dashboard."""
    status = WaterRefillStatus.objects.first()
    if status is None:
        status = WaterRefillStatus(
            device_id=getattr(settings, 'WATER_REFILL_DEVICE_ID', 'ESP32_WATER_REFILL_001'),
        )
        payload = _serialize_status(status)
    else:
        payload = _serialize_status(status)
        evaluate_water_refill_offline_notification(
            status,
            payload['connection_status'] == 'ONLINE',
        )

    return JsonResponse({'success': True, 'data': payload})
