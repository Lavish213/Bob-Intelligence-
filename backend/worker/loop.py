from __future__ import annotations
import time
from loguru import logger
from backend.config import settings, validate_settings
from backend.db.client import claim_brief_jobs, complete_brief_job, fail_brief_job, report_worker_run
from backend.call_planner.brief_generator import generate_call_brief
from backend.decisions.decision_logger import decision_record
from backend.events.bob_events import deliver_pending_events


def _get_situation_label(lead, prop):
    distress = prop.get('distress_type')
    if not isinstance(distress, str):
        return 'unknown'
    normalized = distress.lower().replace('_', '').replace('-', '')
    for key, label in [('preforeclosure', 'preforeclosure'), ('foreclosure', 'preforeclosure'), ('probate', 'probate'), ('inherited', 'inherited_property'), ('vacant', 'vacant_property'), ('landlord', 'tired_landlord'), ('divorce', 'divorce'), ('tax', 'tax_delinquent'), ('code', 'code_violation')]:
        if key in normalized:
            return label
    return 'unknown'


def run_once(stop_event=None):
    result = {'processed': 0, 'briefs_created': 0, 'errors': 0}
    for _ in range(settings().batch_size):
        if stop_event is not None and stop_event.is_set():
            break
        claimed = claim_brief_jobs(batch_size=1)
        if not claimed:
            break
        job = claimed[0]
        result['processed'] += 1
        try:
            snapshot = job['snapshot']
            lead = snapshot['lead']
            prop = snapshot.get('property') or {}
            packet = snapshot.get('packet') or {}
            brief = generate_call_brief(job['lead_id'], lead, prop, packet, lead, situation_label=_get_situation_label(lead, prop), ttl_hours=settings().refresh_hours).to_dict()
            complete_brief_job(job, brief, decision_record(job['lead_id'], brief, job['source_fingerprint']))
            result['briefs_created'] += 1
        except Exception as error:
            result['errors'] += 1
            logger.error('bob_job_failed lead_id={} type={}', job.get('lead_id'), type(error).__name__)
            try:
                fail_brief_job(job, type(error).__name__)
            except Exception as fail_error:
                logger.error('bob_job_release_failed lead_id={} type={}', job.get('lead_id'), type(fail_error).__name__)
    result['events'] = deliver_pending_events() if stop_event is None else deliver_pending_events(stop_event=stop_event)
    try:
        report_worker_run(result)
    except Exception as error:
        result['errors'] += 1
        logger.error('bob_heartbeat_failed type={}', type(error).__name__)
    logger.info('bob_run_complete results={}', result)
    return result


def run_loop(stop_event=None):
    config = settings()
    validate_settings(config)
    while stop_event is None or not stop_event.is_set():
        started = time.monotonic()
        try:
            run_once(stop_event=stop_event)
        except Exception as error:
            logger.error('bob_worker_run_failed type={}', type(error).__name__)
        wait = max(1, config.interval_seconds - (time.monotonic() - started))
        if stop_event is not None:
            stop_event.wait(wait)
        else:
            time.sleep(wait)
