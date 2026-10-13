from __future__ import annotations
from decimal import Decimal


def build_escalation_rules(intel_packet, situation_label, seller_memory):
    rules = ['exact offer request: require verified price authority', 'legal, bankruptcy or lawsuit question: human review', 'human requested: offer an authorized transfer or callback', 'STOP or DNC: immediately suppress and end; never wait for operator approval']
    situation = situation_label.lower()
    if 'foreclosure' in situation:
        rules.append('auction or foreclosure timeline: human review; no urgency pressure')
    if 'probate' in situation or 'inherited' in situation:
        rules.append('estate authority or probate question: human review')
    if 'divorce' in situation:
        rules.append('disputed sale authority: human review')
    if intel_packet.get('conflict_flags'):
        rules.append('intel conflict: deny offers until resolved by a human')
    if seller_memory.get('competitor_mentions'):
        rules.append('other buyers: acknowledge neutrally; do not manufacture urgency')
    threshold = (intel_packet.get('compliance_context') or {}).get('requires_human_approval_above')
    if threshold is not None:
        if type(threshold) is not int or threshold <= 0:
            rules.append('invalid approval threshold: deny pricing pending human review')
        else:
            rules.append(f'offer above ${Decimal(threshold) / 100:,.2f} requires operator approval')
    return rules
