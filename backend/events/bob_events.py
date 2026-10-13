from __future__ import annotations
import httpx
from loguru import logger
from backend.config import settings
from backend.db.client import claim_events, finish_event


def deliver_pending_events(stop_event=None):
    config = settings()
    result = {'accepted': 0, 'failed': 0, 'disabled': not bool(config.event_url)}
    if not config.event_url:
        return result
    if not config.event_token:
        raise ValueError('Event delivery requires a configured token')
    for _ in range(config.batch_size):
        if stop_event is not None and stop_event.is_set():
            break
        claimed = claim_events(batch_size=1)
        if not claimed:
            break
        event = claimed[0]
        accepted = False
        try:
            with httpx.Client(timeout=3.0, follow_redirects=False) as client:
                response = client.post(config.event_url, json=event['payload'], headers={'X-Karpathys-Secret': config.event_token, 'Idempotency-Key': event['id']})
                response.raise_for_status()
                receipt = response.json() if 200 <= response.status_code < 300 else {}
                accepted = isinstance(receipt, dict) and receipt.get('status') == 'persisted' and receipt.get('event_id') == event['id']
        except Exception as error:
            logger.warning('bob_event_delivery_failed event_id={} type={}', event['id'], type(error).__name__)
        try:
            recorded = finish_event(event['id'], event['lease_token'], accepted)
        except Exception as error:
            logger.warning('bob_event_ack_failed event_id={} type={}', event['id'], type(error).__name__)
            recorded = False
        result['accepted' if accepted and recorded else 'failed'] += 1
    return result
