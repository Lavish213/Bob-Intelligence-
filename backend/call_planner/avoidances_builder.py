from __future__ import annotations


def build_avoidances(intel_packet, situation_label, call_count=0):
    avoid = ['unverified pricing', 'legal advice']
    situation = situation_label.lower()
    if 'foreclosure' in situation:
        avoid.extend(['foreclosure legal guidance', 'auction timeline claims'])
    if 'probate' in situation or 'inherited' in situation:
        avoid.extend(['probate advice', 'estate tax guidance'])
    if 'divorce' in situation:
        avoid.append('taking sides in a divorce')
    profile = intel_packet.get('property_profile') or {}
    distress = profile.get('distress_type') or ''
    if isinstance(distress, dict):
        distress = distress.get('value', '')
    if not isinstance(distress, str) or not any(item in distress.lower() for item in ['free_and_clear', 'absentee_owner']):
        avoid.append('creative finance pitches without verified suitability')
    items = (intel_packet.get('strategy_context') or {}).get('do_not_pitch') or []
    if not isinstance(items, list) or any(not isinstance(item, str) for item in items):
        raise ValueError('do_not_pitch must be a string list')
    avoid.extend(item[:160] for item in items[:16])
    if intel_packet.get('conflict_flags'):
        avoid.append('offer and strategy discussion until human conflict resolution')
    return list(dict.fromkeys(avoid))
