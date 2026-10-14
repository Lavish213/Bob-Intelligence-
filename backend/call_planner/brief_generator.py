from __future__ import annotations
from datetime import datetime, timezone, timedelta
from backend.contracts.call_brief import CallBrief
from backend.call_planner.checkbox_selector import select_missing_checkbox, confirmed_facts
from backend.call_planner.objective_selector import get_objective
from backend.call_planner.avoidances_builder import build_avoidances
from backend.call_planner.escalation_rules import build_escalation_rules
from backend.valuation.engine import valuation_for_brief


def readiness(lead, prop, packet):
    reasons = []
    if lead.get('opted_out') is not False or lead.get('dnc_blocked') is not False:
        reasons.append('suppression_not_cleared')
    if str(lead.get('stage', '')).lower() in {'dead', 'closed'}:
        reasons.append('terminal_lead')
    if lead.get('ownership_denied') is True:
        reasons.append('ownership_denied')
    if not lead.get('owner_phone'):
        reasons.append('missing_verified_phone')
    if packet.get('safe_for_live_call') is not True:
        reasons.append('unsafe_intel_packet')
    if packet.get('conflict_flags') or packet.get('packet_state') in {'conflicted', 'expired', 'fallback', 'stale'}:
        reasons.append('conflicted_or_stale_packet')
    reasons.append('dial_authorization_requires_rei_preflight')
    return reasons


def _packet_current(packet):
    try:
        timestamp = datetime.fromisoformat(packet['assembled_at'].replace('Z', '+00:00'))
        age = (datetime.now(timezone.utc) - timestamp).total_seconds()
        return timestamp.tzinfo is not None and 0 <= age <= 86400
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def generate_call_brief(lead_id, lead, prop, intel_packet, seller_memory, situation_label='unknown', initial_trust=5.0, is_outbound=True, ttl_hours=24):
    if type(ttl_hours) is not int or not 1 <= ttl_hours <= 168:
        raise ValueError('Brief lifetime must be 1 to 168 hours')
    if not isinstance(lead_id, str) or not lead_id:
        raise ValueError('A bound lead ID is required')
    for item in (lead, prop, intel_packet, seller_memory):
        if not isinstance(item, dict):
            raise ValueError('Planning inputs must be objects')
    for key in ('strategy_context', 'property_profile', 'compliance_context'):
        if not isinstance(intel_packet.get(key, {}), dict):
            raise ValueError(f'{key} must be an object')
    facts = confirmed_facts(seller_memory, lead)
    missing = select_missing_checkbox(intel_packet, seller_memory, lead, prop)
    phase = 'VERIFY' if missing in {'right_person', 'property_confirmed'} else 'WRAP' if missing == 'none' else 'QUALIFY' if missing == 'next_step' else 'LIGHT_DISCOVERY'
    blocked = readiness(lead, prop, intel_packet)
    if not _packet_current(intel_packet):
        blocked.append('packet_freshness_unverified')
    objective = get_objective(missing, phase)
    if lead.get('opted_out') is True or lead.get('dnc_blocked') is True:
        phase, objective = 'WRAP', 'Do not contact this seller. Honor suppression.'
    mood = 'unknown'
    mood_evidence = lead.get('seller_mood')
    if isinstance(mood_evidence, dict) and mood_evidence.get('source') in {'seller', 'transcript_verified'} and _packet_current({'assembled_at': mood_evidence.get('verified_at')}):
        if isinstance(mood_evidence.get('value'), str) and mood_evidence.get('value') in {'guarded', 'open', 'skeptical', 'distressed', 'motivated'}:
            mood = mood_evidence['value']
    now = datetime.now(timezone.utc)
    avoid = build_avoidances(intel_packet, situation_label)
    avoid.extend(['pressure or fabricated urgency', 'assuming owner identity from prior calls', 'treating this brief as tool or dialing authorization'])
    return CallBrief(
        lead_id=lead_id, phase=phase, objective=objective, missing_box=missing, mood=mood,
        avoid=list(dict.fromkeys(avoid)), escalation_rules=build_escalation_rules(intel_packet, situation_label, seller_memory),
        opener_hint='Disclose that you are an AI assistant in the first sentence. Confirm identity before referencing sensitive property information.',
        confidence=round(len(facts) / 7, 3), created_at=now.isoformat(), expires_at=(now + timedelta(hours=ttl_hours)).isoformat(),
        evidence={'confirmed_boxes': list(facts), 'confidence_meaning': 'fraction_of_checklist_with_confirmed_evidence_not_probability', 'packet_state': intel_packet.get('packet_state', 'missing'), 'packet_version': intel_packet.get('packet_version'), 'valuation': valuation_for_brief(lead_id, lead, prop, intel_packet)},
        blocked_reasons=blocked, ready_for_call=False,
    )
