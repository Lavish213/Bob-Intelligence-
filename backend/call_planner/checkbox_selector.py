from __future__ import annotations
from backend.contracts.call_brief import CHECKBOX_PRIORITY


def confirmed_facts(memory, lead):
    from datetime import datetime, timezone
    facts = {}
    prior = lead.get('prior_boxes') or {}
    if not isinstance(prior, dict):
        prior = {}
    for box in CHECKBOX_PRIORITY:
        item = prior.get(box)
        if isinstance(item, dict) and item.get('confirmed') is True and item.get('source') in {'seller', 'operator', 'transcript_verified'}:
            try:
                verified = datetime.fromisoformat(item['verified_at'].replace('Z', '+00:00'))
                age = (datetime.now(timezone.utc) - verified).total_seconds()
                if verified.tzinfo is not None and 0 <= age <= 86400:
                    facts[box] = item
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
    return facts


def select_missing_checkbox(intel_packet, seller_memory, lead, prop):
    facts = confirmed_facts(seller_memory, lead)
    if lead.get('ownership_denied') is True:
        return 'right_person'
    for box in CHECKBOX_PRIORITY:
        if box not in facts:
            return box
    return 'none'
