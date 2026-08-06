"""Reusable notification helpers for email alerts and environmental monitoring."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from threading import Thread

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from .models import (
    EnvironmentalAlertState,
    EnvironmentSettings,
    Notification,
    NotificationLog,
    NotificationSettings,
)


logger = logging.getLogger(__name__)


def send_notification_async(sender, *args, **kwargs):
    """Run notification work in a background thread."""

    def run():
        try:
            sender(*args, **kwargs)
        except Exception as exc:
            logger.error("Notification worker failed: %s", exc)

    thread = Thread(target=run, daemon=True)
    thread.start()


def _normalize_recipient_list(recipient_emails):
    if isinstance(recipient_emails, str):
        raw_list = recipient_emails.replace(';', ',').replace('\n', ',').split(',')
    else:
        raw_list = list(recipient_emails or [])
    return [email.strip() for email in raw_list if email and str(email).strip()]


def _log_notification(notification_type, recipient, subject, status, channel='email', error_message='', metadata=None):
    NotificationLog.objects.create(
        notification_type=notification_type,
        recipient=recipient or '',
        subject=subject,
        channel=channel,
        status=status,
        error_message=error_message or '',
        metadata=metadata or {},
    )


def send_logged_email(notification_type, subject, plain_body, html_body=None, recipient_emails=None, metadata=None):
    """Send an email and persist a log entry for each recipient."""

    settings_obj = NotificationSettings.load()
    if not settings_obj.email_enabled:
        logger.info("Email notifications are disabled; skipping %s", notification_type)
        return False

    recipients = _normalize_recipient_list(recipient_emails or settings_obj.get_recipient_list())
    if not recipients:
        fallback_email = getattr(settings, 'ADMIN_EMAIL', '')
        recipients = _normalize_recipient_list([fallback_email])

    if not recipients:
        logger.warning("No recipients configured for %s", notification_type)
        return False

    overall_success = True
    for recipient in recipients:
        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=plain_body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                to=[recipient],
            )
            if html_body:
                email.attach_alternative(html_body, 'text/html')
            email.send(fail_silently=False)
            _log_notification(notification_type, recipient, subject, 'SUCCESS', metadata=metadata)
        except Exception as exc:
            overall_success = False
            logger.error("Failed to send %s email to %s: %s", notification_type, recipient, exc)
            _log_notification(notification_type, recipient, subject, 'FAILED', error_message=str(exc), metadata=metadata)

    return overall_success


def send_logged_email_async(notification_type, subject, plain_body, html_body=None, recipient_emails=None, metadata=None):
    send_notification_async(
        send_logged_email,
        notification_type,
        subject,
        plain_body,
        html_body,
        recipient_emails,
        metadata,
    )


def _create_in_app_notification(title, description, level='warning'):
    Notification.objects.create(
        title=title,
        description=description,
        category='environmental',
        level=level,
        is_read=False,
    )


def _build_environment_email_subject(alert_label, is_recovery=False):
    prefix = 'Recovered' if is_recovery else 'Alert'
    return f"{alert_label} {prefix} - Mushroom Farm"


def _build_environment_email_body(alert_label, description, current_value, threshold_text, is_recovery=False):
    header = 'Condition Restored' if is_recovery else 'Environmental Alert'
    subject_line = f"{alert_label} {'restored' if is_recovery else 'detected'}"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #2e7d32, #4caf50); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border: 1px solid #e0e0e0; }}
            .badge {{ display: inline-block; background: {'#4caf50' if is_recovery else '#f59e0b'}; color: white; padding: 10px 18px; border-radius: 999px; font-weight: bold; }}
            .box {{ background: white; padding: 18px; border-radius: 8px; margin: 18px 0; border: 1px solid #e5e7eb; }}
            .footer {{ background: #333; color: #aaa; padding: 20px; text-align: center; font-size: 12px; border-radius: 0 0 10px 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🍄 {header}</h1>
            </div>
            <div class="content">
                <p style="text-align:center;"><span class="badge">{alert_label}</span></p>
                <div class="box">
                    <p><strong>Status:</strong> {description}</p>
                    <p><strong>Current Value:</strong> {current_value}</p>
                    <p><strong>Configured Threshold:</strong> {threshold_text}</p>
                    <p><strong>Time:</strong> {timezone.now().strftime('%B %d, %Y at %I:%M %p')}</p>
                </div>
            </div>
            <div class="footer">&copy; {timezone.now().year} Mushroom Farm</div>
        </div>
    </body>
    </html>
    """
    plain = f"{subject_line.upper()}\n\n{description}\nCurrent Value: {current_value}\nThreshold: {threshold_text}\nTime: {timezone.now().strftime('%B %d, %Y at %I:%M %p')}"
    return plain, html


def _record_environment_notification(notification_type, title, description, level='warning'):
    _create_in_app_notification(title=title, description=description, level=level)
    logger.info("Created in-app notification: %s", notification_type)


def _evaluate_alert(alert_key, alert_label, current_value, is_abnormal, threshold_text, notification_type, settings_obj, notification_settings, cooldown_minutes, subject_title, description_builder, recovery_description_builder, metadata=None):
    state = EnvironmentalAlertState.get_or_create_state(alert_key, alert_label)
    now = timezone.now()
    cooldown = timedelta(minutes=cooldown_minutes)
    events = []

    if is_abnormal:
        should_send = (
            not state.is_active
            or state.last_alert_sent_at is None
            or (now - state.last_alert_sent_at) >= cooldown
        )

        state.is_active = True
        state.last_observed_value = {'value': current_value, 'observed_at': now.isoformat()}
        if should_send:
            description = description_builder(current_value, threshold_text)
            state.last_alert_sent_at = now
            state.save()

            _record_environment_notification(notification_type, subject_title, description, level='warning')
            plain_body, html_body = _build_environment_email_body(alert_label, description, current_value, threshold_text, is_recovery=False)
            send_logged_email_async(
                notification_type,
                _build_environment_email_subject(alert_label, is_recovery=False),
                plain_body,
                html_body,
                recipient_emails=notification_settings.get_recipient_list(),
                metadata=metadata or {'alert_key': alert_key, 'state': 'alert', 'value': current_value},
            )
            events.append({'type': 'alert', 'key': alert_key, 'description': description})
        else:
            state.save(update_fields=['is_active', 'last_observed_value', 'updated_at'])
    else:
        if state.is_active:
            state.is_active = False
            state.last_observed_value = {'value': current_value, 'observed_at': now.isoformat()}
            state.last_recovery_sent_at = now
            state.save()

            if notification_settings.recovery_email_enabled:
                description = recovery_description_builder(current_value, threshold_text)
                recovery_type = f"{notification_type}_recovery"
                _record_environment_notification(recovery_type, f"{alert_label} Restored", description, level='success')
                plain_body, html_body = _build_environment_email_body(alert_label, description, current_value, threshold_text, is_recovery=True)
                send_logged_email_async(
                    recovery_type,
                    _build_environment_email_subject(alert_label, is_recovery=True),
                    plain_body,
                    html_body,
                    recipient_emails=notification_settings.get_recipient_list(),
                    metadata=metadata or {'alert_key': alert_key, 'state': 'recovery', 'value': current_value},
                )
                events.append({'type': 'recovery', 'key': alert_key, 'description': description})

    return events


def evaluate_environment_notifications(reading, settings_obj=None):
    """Evaluate sensor readings and create alert/recovery notifications."""

    if reading is None:
        return []

    settings_obj = settings_obj or EnvironmentSettings.load()
    notification_settings = NotificationSettings.load()
    cooldown_minutes = notification_settings.alert_cooldown_minutes or 60

    temperature = float(reading.temperature)
    humidity = float(reading.humidity)
    co2_ppm = reading.co2_ppm

    events = []
    events.extend(_evaluate_alert(
        alert_key='temperature_high',
        alert_label='Temperature Too High',
        current_value=f'{temperature:.1f}°C',
        is_abnormal=temperature > float(settings_obj.fan_temp_threshold),
        threshold_text=f'Above {float(settings_obj.fan_temp_threshold):.1f}°C',
        notification_type='environmental_temperature_high',
        settings_obj=settings_obj,
        notification_settings=notification_settings,
        cooldown_minutes=cooldown_minutes,
        subject_title='High Temperature Alert',
        description_builder=lambda value, threshold: f'Temperature is too high at {float(reading.temperature):.1f}°C, exceeding {threshold}.',
        recovery_description_builder=lambda value, threshold: f'Temperature has returned to normal at {float(reading.temperature):.1f}°C.',
        metadata={'metric': 'temperature', 'direction': 'high'},
    ))
    events.extend(_evaluate_alert(
        alert_key='temperature_low',
        alert_label='Temperature Too Low',
        current_value=f'{temperature:.1f}°C',
        is_abnormal=temperature < float(settings_obj.heater_low_threshold),
        threshold_text=f'Below {float(settings_obj.heater_low_threshold):.1f}°C',
        notification_type='environmental_temperature_low',
        settings_obj=settings_obj,
        notification_settings=notification_settings,
        cooldown_minutes=cooldown_minutes,
        subject_title='Low Temperature Alert',
        description_builder=lambda value, threshold: f'Temperature is too low at {float(reading.temperature):.1f}°C, below {threshold}.',
        recovery_description_builder=lambda value, threshold: f'Temperature has returned to normal at {float(reading.temperature):.1f}°C.',
        metadata={'metric': 'temperature', 'direction': 'low'},
    ))
    events.extend(_evaluate_alert(
        alert_key='humidity_high',
        alert_label='Humidity Too High',
        current_value=f'{humidity:.1f}%',
        is_abnormal=humidity > float(settings_obj.humidifier_high_threshold),
        threshold_text=f'Above {float(settings_obj.humidifier_high_threshold):.1f}%',
        notification_type='environmental_humidity_high',
        settings_obj=settings_obj,
        notification_settings=notification_settings,
        cooldown_minutes=cooldown_minutes,
        subject_title='High Humidity Alert',
        description_builder=lambda value, threshold: f'Humidity is too high at {float(reading.humidity):.1f}%, exceeding {threshold}.',
        recovery_description_builder=lambda value, threshold: f'Humidity has returned to normal at {float(reading.humidity):.1f}%.' ,
        metadata={'metric': 'humidity', 'direction': 'high'},
    ))
    events.extend(_evaluate_alert(
        alert_key='humidity_low',
        alert_label='Humidity Too Low',
        current_value=f'{humidity:.1f}%',
        is_abnormal=humidity < float(settings_obj.humidifier_low_threshold),
        threshold_text=f'Below {float(settings_obj.humidifier_low_threshold):.1f}%',
        notification_type='environmental_humidity_low',
        settings_obj=settings_obj,
        notification_settings=notification_settings,
        cooldown_minutes=cooldown_minutes,
        subject_title='Low Humidity Alert',
        description_builder=lambda value, threshold: f'Humidity is too low at {float(reading.humidity):.1f}%, below {threshold}.',
        recovery_description_builder=lambda value, threshold: f'Humidity has returned to normal at {float(reading.humidity):.1f}%.' ,
        metadata={'metric': 'humidity', 'direction': 'low'},
    ))

    if co2_ppm is not None:
        co2_value = float(co2_ppm)
        events.extend(_evaluate_alert(
            alert_key='co2_high',
            alert_label='CO2 Too High',
            current_value=f'{co2_value:.0f} ppm',
            is_abnormal=co2_value > float(settings_obj.co2_value),
            threshold_text=f'Above {int(settings_obj.co2_value)} ppm',
            notification_type='environmental_co2_high',
            settings_obj=settings_obj,
            notification_settings=notification_settings,
            cooldown_minutes=cooldown_minutes,
            subject_title='High CO2 Alert',
            description_builder=lambda value, threshold: f'CO2 is too high at {co2_value:.0f} ppm, exceeding {threshold}.',
            recovery_description_builder=lambda value, threshold: f'CO2 has returned to normal at {co2_value:.0f} ppm.',
            metadata={'metric': 'co2', 'direction': 'high'},
        ))

    return events