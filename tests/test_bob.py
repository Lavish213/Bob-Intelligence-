from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
import copy
import pytest
from backend.call_planner.brief_generator import generate_call_brief
from backend.call_planner.checkbox_selector import select_missing_checkbox
from backend.call_planner.escalation_rules import build_escalation_rules
from backend.contracts.call_brief import CHECKBOX_PRIORITY
from backend.config import settings, validate_settings
from backend.db import client as db
from backend.worker import loop
from backend.events import bob_events


def brief(lead=None, memory=None, packet=None, **kwargs):
    return generate_call_brief('lead-1', lead or {}, {}, packet or {}, memory or {}, **kwargs)


def facts(boxes):
    return {box: {'confirmed': True, 'source': 'seller', 'verified_at': datetime.now(timezone.utc).isoformat()} for box in boxes}


@pytest.mark.parametrize('summary', ['wrong number', 'not the owner', 'voicemail', 'stop calling', 'one conversation'])
def test_previous_calls_do_not_prove_ownership(summary):
    assert select_missing_checkbox({}, {'call_summaries': [summary]}, {}, {'address': 'Known address', 'vacant': True}) == 'right_person'


@pytest.mark.parametrize('known', range(8))
def test_checklist_only_advances_with_confirmed_evidence(known):
    item = brief({'prior_boxes': facts(CHECKBOX_PRIORITY[:known])})
    assert item.missing_box == (CHECKBOX_PRIORITY[known] if known < 7 else 'none')
    assert item.confidence == round(known / 7, 3)
    assert item.ready_for_call is False


@pytest.mark.parametrize('record', [True, {'confirmed': True}, {'confirmed': True, 'source': 'crm'}, {'confirmed': True, 'source': 'seller', 'verified_at': 'bad'}, {'confirmed': True, 'source': 'seller', 'verified_at': (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()}, {'confirmed': True, 'source': 'seller', 'verified_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}])
def test_bad_or_stale_identity_evidence_is_not_confirmation(record):
    assert brief({'prior_boxes': {'right_person': record}}).missing_box == 'right_person'


def test_denied_ownership_overrides_prior_evidence():
    assert brief({'ownership_denied': True, 'prior_boxes': facts(CHECKBOX_PRIORITY)}).missing_box == 'right_person'


@pytest.mark.parametrize('flag', ['opted_out', 'dnc_blocked'])
def test_suppressed_leads_get_no_contact_objective(flag):
    item = brief({flag: True})
    assert item.phase == 'WRAP'
    assert 'Do not contact' in item.objective
    assert item.ready_for_call is False


def test_topics_do_not_prove_condition():
    item = brief({'prior_boxes': facts(CHECKBOX_PRIORITY[:3])}, {'hot_topics': ['appointment time']})
    assert item.missing_box == 'condition'


def test_cents_threshold_is_formatted_correctly():
    rules = build_escalation_rules({'compliance_context': {'requires_human_approval_above': 25000000}}, 'unknown', {})
    assert any('$250,000.00' in item for item in rules)


@pytest.mark.parametrize('threshold', [True, 1.5, '25000000', -100, 0])
def test_invalid_threshold_cannot_be_authority(threshold):
    assert any('invalid approval threshold' in item for item in build_escalation_rules({'compliance_context': {'requires_human_approval_above': threshold}}, 'unknown', {}))


def test_stop_never_waits_for_approval():
    assert any('STOP' in item and 'never wait' in item for item in brief().escalation_rules)


def test_distress_record_does_not_establish_seller_mood():
    assert brief(situation_label='preforeclosure').mood == 'unknown'


@pytest.mark.parametrize('value', ['pricing', [1], {'offer': 'pricing'}])
def test_malformed_avoidances_are_rejected(value):
    with pytest.raises(ValueError):
        brief(packet={'strategy_context': {'do_not_pitch': value}})


@pytest.mark.parametrize('ttl', [0, 169, True, '24'])
def test_lifetime_is_bounded(ttl):
    with pytest.raises(ValueError):
        brief(ttl_hours=ttl)


def test_brief_does_not_mutate_packet():
    packet = {'packet_state': 'operator_locked', 'action_permissions': {'book_appointment': {'level': 'blocked'}}}
    original = copy.deepcopy(packet)
    item = brief(packet=packet)
    assert packet == original
    assert 'action_permissions' not in item.to_dict()


def test_memory_reads_canonical_leads_table(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(db, 'get_client', lambda: client)
    db.get_seller_memory('lead')
    client.table.assert_called_once_with('leads')


def test_packet_reads_canonical_intel_table(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(db, 'get_client', lambda: client)
    db.load_intel_packet('lead')
    client.table.assert_called_once_with('intel_packets')


def test_refresh_filter_uses_current_rolling_date(monkeypatch):
    client = MagicMock()
    query = client.table.return_value
    for name in ['select', 'eq', 'neq', 'or_', 'order', 'limit']:
        getattr(query, name).return_value = query
    query.execute.return_value.data = []
    monkeypatch.setattr(db, 'get_client', lambda: client)
    db.get_leads_needing_brief()
    cutoff = query.or_.call_args.args[0].split('.lt.')[1]
    age = datetime.now(timezone.utc) - datetime.fromisoformat(cutoff)
    assert 86399 <= age.total_seconds() <= 86401


def job():
    return {'lead_id': 'lead-1', 'lease_token': 'token', 'source_fingerprint': 'fingerprint', 'snapshot': {'lead': {'id': 'lead-1'}, 'property': {}, 'packet': {}}}


def test_worker_does_not_count_rejected_commit(monkeypatch):
    monkeypatch.setattr(loop, 'claim_brief_jobs', MagicMock(side_effect=[[job()], []]))
    complete = MagicMock(side_effect=RuntimeError('lease lost'))
    fail = MagicMock(return_value=True)
    monkeypatch.setattr(loop, 'complete_brief_job', complete)
    monkeypatch.setattr(loop, 'fail_brief_job', fail)
    monkeypatch.setattr(loop, 'deliver_pending_events', lambda: {})
    result = loop.run_once()
    assert result['errors'] == 1 and result['briefs_created'] == 0
    fail.assert_called_once()


def test_worker_claims_one_job_at_a_time_and_persists_decision(monkeypatch):
    claim = MagicMock(side_effect=[[job()], []])
    complete = MagicMock()
    monkeypatch.setattr(loop, 'claim_brief_jobs', claim)
    monkeypatch.setattr(loop, 'complete_brief_job', complete)
    monkeypatch.setattr(loop, 'deliver_pending_events', lambda: {})
    assert loop.run_once()['briefs_created'] == 1
    assert all(call.kwargs == {'batch_size': 1} for call in claim.call_args_list)
    assert complete.call_args.args[2]['source_fingerprint'] == 'fingerprint'


@pytest.mark.parametrize('code', [200, 202, 301, 401, 429, 500, 503])
def test_event_delivery_executes_and_checks_http_status(monkeypatch, code):
    import httpx
    config = SimpleNamespace(event_url='https://example.test', event_token='test-token', batch_size=2)
    monkeypatch.setattr(bob_events, 'settings', lambda: config)
    monkeypatch.setattr(bob_events, 'claim_events', MagicMock(side_effect=[[{'id': 'event', 'lease_token': 'lease', 'payload': {'lead_id': 'lead'}}], []]))
    finish = MagicMock(return_value=True)
    monkeypatch.setattr(bob_events, 'finish_event', finish)
    client = MagicMock()
    response = httpx.Response(code, json={'status': 'persisted', 'event_id': 'event'}, request=httpx.Request('POST', 'https://example.test'))
    client.__enter__.return_value.post.return_value = response
    monkeypatch.setattr(bob_events.httpx, 'Client', lambda **kwargs: client)
    result = bob_events.deliver_pending_events()
    assert finish.call_args.args[-1] is (code < 300)
    assert result['accepted'] == int(code < 300)
    assert client.__enter__.return_value.post.call_args.kwargs['headers']['Idempotency-Key'] == 'event'
    assert client.__enter__.return_value.post.call_args.kwargs['headers']['X-Karpathys-Secret'] == 'test-token'
    assert client.__enter__.return_value.post.call_args.args[0] == 'https://example.test'


def test_events_disabled_does_not_claim_or_send(monkeypatch):
    claim = MagicMock()
    monkeypatch.setattr(bob_events, 'claim_events', claim)
    assert bob_events.deliver_pending_events()['disabled'] is True
    claim.assert_not_called()


@pytest.mark.parametrize('name,value', [('BOB_BATCH_SIZE', '0'), ('BOB_BATCH_SIZE', '101'), ('BOB_WORKER_INTERVAL_MINUTES', '-1'), ('BOB_LEASE_SECONDS', '10'), ('BOB_REFRESH_HOURS', '169')])
def test_bad_config_fails_closed(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        settings()


def test_tracked_placeholder_config_cannot_start_network_worker():
    with pytest.raises(ValueError, match='placeholder'):
        validate_settings(settings())


@pytest.mark.parametrize('mask', range(128))
def test_all_checklist_subsets_preserve_priority(mask):
    known = [box for index, box in enumerate(CHECKBOX_PRIORITY) if mask & (1 << index)]
    item = brief({'prior_boxes': facts(known)})
    expected = next((box for box in CHECKBOX_PRIORITY if box not in known), 'none')
    assert item.missing_box == expected
    assert item.ready_for_call is False


def test_failed_job_does_not_abandon_remaining_batch(monkeypatch):
    broken = job()
    broken['snapshot'] = None
    monkeypatch.setattr(loop, 'claim_brief_jobs', MagicMock(side_effect=[[broken], [job()], []]))
    monkeypatch.setattr(loop, 'complete_brief_job', MagicMock())
    monkeypatch.setattr(loop, 'fail_brief_job', MagicMock(side_effect=RuntimeError('offline')))
    monkeypatch.setattr(loop, 'deliver_pending_events', lambda: {})
    result = loop.run_once()
    assert result['processed'] == 2 and result['errors'] == 1 and result['briefs_created'] == 1


@pytest.mark.parametrize('code', [False, None, [], {'success': True}])
def test_unconfirmed_rpc_commit_is_not_success(monkeypatch, code):
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = code
    monkeypatch.setattr(db, 'get_client', lambda: client)
    with pytest.raises(RuntimeError):
        db.complete_brief_job(job(), {}, {})


def test_claims_use_configured_tenant_and_short_generation(monkeypatch):
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = []
    monkeypatch.setattr(db, 'get_client', lambda: client)
    db.claim_brief_jobs(batch_size=1)
    args = client.rpc.call_args.args
    assert args[0] == 'bob_claim_brief_jobs'
    assert args[1]['p_batch_size'] == 1 and args[1]['p_tenant_id'] == settings().tenant_id


def test_network_event_timeout_retains_failure_for_retry(monkeypatch):
    import httpx
    config = SimpleNamespace(event_url='https://example.test', event_token='test-token', batch_size=2)
    monkeypatch.setattr(bob_events, 'settings', lambda: config)
    monkeypatch.setattr(bob_events, 'claim_events', MagicMock(side_effect=[[{'id': 'event', 'lease_token': 'lease', 'payload': {}}], []]))
    finish = MagicMock(return_value=True)
    monkeypatch.setattr(bob_events, 'finish_event', finish)
    client = MagicMock()
    client.__enter__.return_value.post.side_effect = httpx.ReadTimeout('timeout')
    monkeypatch.setattr(bob_events.httpx, 'Client', lambda **kwargs: client)
    assert bob_events.deliver_pending_events()['failed'] == 1
    assert finish.call_args.args[-1] is False


def test_acceptance_without_ack_cannot_count_delivery(monkeypatch):
    import httpx
    monkeypatch.setattr(bob_events, 'settings', lambda: SimpleNamespace(event_url='https://example.test', event_token='token', batch_size=2))
    monkeypatch.setattr(bob_events, 'claim_events', MagicMock(side_effect=[[{'id': 'event', 'lease_token': 'lease', 'payload': {}}], []]))
    monkeypatch.setattr(bob_events, 'finish_event', MagicMock(side_effect=RuntimeError('db unavailable')))
    client = MagicMock()
    client.__enter__.return_value.post.return_value = httpx.Response(202, request=httpx.Request('POST', 'https://example.test'))
    monkeypatch.setattr(bob_events.httpx, 'Client', lambda **kwargs: client)
    result = bob_events.deliver_pending_events()
    assert result['accepted'] == 0 and result['failed'] == 1


def test_worker_loop_survives_error_and_obeys_shutdown(monkeypatch):
    stopped = MagicMock()
    stopped.is_set.side_effect = [False, True]
    monkeypatch.setattr(loop, 'validate_settings', lambda config: None)
    monkeypatch.setattr(loop, 'run_once', MagicMock(side_effect=RuntimeError('db unavailable')))
    loop.run_loop(stopped)
    stopped.wait.assert_called_once()
    assert 1 <= stopped.wait.call_args.args[0] <= settings().interval_seconds


@pytest.mark.parametrize('url,token', [('http://example.test','token'), ('https://example.test','')])
def test_event_configuration_fails_closed(monkeypatch, url, token):
    from dataclasses import replace
    config = replace(settings(), service_key='configured-test-key', event_url=url, event_token=token)
    with pytest.raises(ValueError):
        validate_settings(config)


@pytest.mark.parametrize('value', [[], 0, None, 'bad'])
def test_malformed_packet_sections_rejected(value):
    with pytest.raises(ValueError):
        brief(packet={'compliance_context': value})


def test_shutdown_does_not_claim_another_job(monkeypatch):
    stopped = MagicMock()
    stopped.is_set.return_value = True
    claim = MagicMock()
    monkeypatch.setattr(loop, 'claim_brief_jobs', claim)
    monkeypatch.setattr(loop, 'deliver_pending_events', lambda **kwargs: {})
    assert loop.run_once(stop_event=stopped)['processed'] == 0
    claim.assert_not_called()


def test_shutdown_stops_pending_event_claims(monkeypatch):
    stopped = MagicMock()
    stopped.is_set.return_value = True
    claim = MagicMock()
    monkeypatch.setattr(bob_events, 'settings', lambda: SimpleNamespace(event_url='https://example.test', event_token='token', batch_size=2))
    monkeypatch.setattr(bob_events, 'claim_events', claim)
    assert bob_events.deliver_pending_events(stop_event=stopped)['accepted'] == 0
    claim.assert_not_called()


@pytest.mark.parametrize('errors,expected', [(0, 0), (1, 1)])
def test_once_cli_reports_failure_without_starting_background_loop(monkeypatch, errors, expected):
    from backend import main
    monkeypatch.setattr('sys.argv', ['bob', '--once'])
    monkeypatch.setattr(main, 'validate_settings', lambda config: None)
    monkeypatch.setattr(main, 'run_once', lambda: {'errors': errors})
    background = MagicMock()
    monkeypatch.setattr(main, 'run_loop', background)
    assert main.main() == expected
    background.assert_not_called()


def test_once_cli_refuses_placeholder_configuration(monkeypatch):
    from backend import main
    monkeypatch.setattr('sys.argv', ['bob', '--once'])
    run = MagicMock()
    monkeypatch.setattr(main, 'run_once', run)
    with pytest.raises(ValueError):
        main.main()
    run.assert_not_called()
