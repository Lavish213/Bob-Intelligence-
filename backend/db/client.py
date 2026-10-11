from __future__ import annotations
from functools import lru_cache
from datetime import datetime, timezone, timedelta
from supabase import create_client, ClientOptions
from backend.config import settings, validate_settings


@lru_cache(maxsize=1)
def get_client():
    config = settings()
    validate_settings(config)
    return create_client(config.supabase_url, config.service_key, options=ClientOptions(postgrest_client_timeout=10, auto_refresh_token=False, persist_session=False))


def get_leads_needing_brief(batch_size=20):
    config = settings()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=config.refresh_hours)).isoformat()
    response = get_client().table('leads').select('*').eq('tenant_id', config.tenant_id).eq('opted_out', False).eq('dnc_blocked', False).neq('stage', 'dead').or_(f'call_brief.is.null,call_brief_generated_at.lt.{cutoff}').order('call_brief_generated_at', nullsfirst=True).limit(batch_size).execute()
    return response.data or []


def load_intel_packet(lead_id):
    response = get_client().table('intel_packets').select('*').eq('tenant_id', settings().tenant_id).eq('lead_id', lead_id).limit(1).execute()
    return response.data[0] if response.data else None


def get_seller_memory(lead_id):
    response = get_client().table('leads').select('*').eq('tenant_id', settings().tenant_id).eq('id', lead_id).limit(1).execute()
    return response.data[0] if response.data else {}


def claim_brief_jobs(batch_size=None):
    config = settings()
    response = get_client().rpc('bob_claim_brief_jobs', {'p_tenant_id': config.tenant_id, 'p_batch_size': batch_size or config.batch_size, 'p_lease_seconds': config.lease_seconds, 'p_refresh_hours': config.refresh_hours}).execute()
    return response.data or []


def complete_brief_job(job, brief, decision):
    response = get_client().rpc('bob_complete_brief_job', {'p_tenant_id': settings().tenant_id, 'p_lead_id': job['lead_id'], 'p_token': job['lease_token'], 'p_brief': brief, 'p_decision': decision}).execute()
    if response.data is not True:
        raise RuntimeError('Brief commit rejected: stale source, expired lease or lost ownership')


def fail_brief_job(job, reason):
    response = get_client().rpc('bob_fail_brief_job', {'p_tenant_id': settings().tenant_id, 'p_lead_id': job['lead_id'], 'p_token': job['lease_token'], 'p_reason': reason[:200]}).execute()
    return response.data is True


def claim_events(batch_size=None):
    config = settings()
    response = get_client().rpc('bob_claim_events', {'p_tenant_id': config.tenant_id, 'p_batch_size': batch_size or config.batch_size}).execute()
    return response.data or []


def finish_event(event_id, token, accepted):
    response = get_client().rpc('bob_finish_event', {'p_tenant_id': settings().tenant_id, 'p_event_id': event_id, 'p_token': token, 'p_accepted': accepted}).execute()
    return response.data is True


def integration_health():
    response = get_client().rpc('bob_integration_health', {'p_tenant_id': settings().tenant_id}).execute()
    if not isinstance(response.data, dict) or response.data.get('contract_version') != '2.1' or response.data.get('backend') != 'REI-AGENT':
        raise RuntimeError('Shared database does not satisfy Bob/Sophia contract 2.1')
    return response.data


def report_worker_run(result):
    response = get_client().rpc('bob_report_worker_run', {'p_tenant_id': settings().tenant_id, 'p_errors': result['errors'] + result.get('events', {}).get('failed', 0), 'p_processed': result['processed'], 'p_briefs_created': result['briefs_created']}).execute()
    if response.data is not True:
        raise RuntimeError('Worker heartbeat was not persisted')
