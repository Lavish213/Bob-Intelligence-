from __future__ import annotations
import os
from dataclasses import dataclass
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()


def _integer(name, default, minimum, maximum):
    raw = os.getenv(name, str(default))
    value = int(raw)
    if not minimum <= value <= maximum:
        raise ValueError(f'{name} must be between {minimum} and {maximum}')
    return value


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    service_key: str
    tenant_id: str
    interval_seconds: int
    batch_size: int
    refresh_hours: int
    lease_seconds: int
    event_url: str
    event_token: str


def settings():
    from uuid import UUID
    tenant = os.getenv('BOB_TENANT_ID', '00000000-0000-0000-0000-000000000001')
    UUID(tenant)
    source = os.getenv('REI_COMMAND_URL', '')
    parsed = urlparse(source)
    if source and (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {'', '/'} or parsed.query or parsed.fragment):
        raise ValueError('REI_COMMAND_URL must be an HTTPS service origin')
    return Settings(
        os.getenv('SUPABASE_URL', ''), os.getenv('SUPABASE_SERVICE_KEY', ''), tenant,
        _integer('BOB_WORKER_INTERVAL_MINUTES', 5, 1, 60) * 60,
        _integer('BOB_BATCH_SIZE', 20, 1, 100),
        _integer('BOB_REFRESH_HOURS', 24, 1, 168),
        _integer('BOB_LEASE_SECONDS', 120, 30, 600),
        os.getenv('BOB_EVENT_URL', '') or (os.getenv('REI_COMMAND_URL', '').rstrip('/') + '/api/ingest/bob/brief-created' if os.getenv('REI_COMMAND_URL') else ''), os.getenv('KARPATHYS_WEBHOOK_SECRET', ''),
    )


def validate_settings(config):
    if urlparse(config.supabase_url).scheme != 'https' or not urlparse(config.supabase_url).hostname or not config.service_key:
        raise ValueError('HTTPS Supabase configuration is required')
    if any(marker in config.service_key.lower() for marker in ('placeholder', 'your-', 'your_', 'example')):
        raise ValueError('Supabase service key is a placeholder')
    if config.event_url and (urlparse(config.event_url).scheme != 'https' or not urlparse(config.event_url).hostname or urlparse(config.event_url).username or urlparse(config.event_url).query or urlparse(config.event_url).fragment or not config.event_token):
        raise ValueError('Configured event delivery requires HTTPS and KARPATHYS_WEBHOOK_SECRET')
