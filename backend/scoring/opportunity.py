from __future__ import annotations

from decimal import Decimal

from backend.valuation.engine import integer
from backend.valuation.finance import screening_mao


SCHEMA_VERSION = '1.0'
POLICY_VERSION = 'opportunity-screening-2026-11-08'
READINESS = ('HOT_BUY', 'WATCH_LIST', 'ARCHIVED')
EVIDENCE_LEVELS = ('verified', 'supported', 'thin', 'unusable')
GRADE_HEADROOM_BPS = (('A', 1000), ('B', 500), ('C', 200), ('D', 0))
EVIDENCE_GRADE_CEILING = {'verified': 'A', 'supported': 'B', 'thin': 'C'}
GRADE_ORDER = ('A', 'B', 'C', 'D', 'F')
MIN_HOT_BUY_GRADE = 'B'


def _money(value):
    if value is None or isinstance(value, bool) or type(value) is not int or not 0 < value <= 10**14:
        return None
    return value


def _cap(grade, ceiling):
    return grade if GRADE_ORDER.index(grade) >= GRADE_ORDER.index(ceiling) else ceiling


def evidence_confidence(valuation):
    if not isinstance(valuation, dict):
        return 'unusable', ['valuation_absent']
    status = valuation.get('status')
    if status in (None, 'invalid_input'):
        return 'unusable', ['valuation_invalid_input']
    reasons = []
    count = valuation.get('comparable_count')
    count = count if isinstance(count, int) and not isinstance(count, bool) else 0
    if status == 'needs_data' or count < 3:
        return 'thin', ['fewer_than_three_qualified_comparables']
    review = sorted(valuation.get('review_reasons') or [])
    spread = valuation.get('spread_bps')
    if status == 'needs_review' or review:
        return 'supported', review or ['valuation_needs_review']
    if valuation.get('point_cents') is None:
        return 'thin', ['no_supported_point_indication']
    if isinstance(spread, int) and not isinstance(spread, bool) and spread > 1500:
        reasons.append('wide_but_within_policy_adjusted_sale_span')
    if count >= 5 and not reasons:
        return 'verified', []
    return ('verified', reasons) if not reasons else ('supported', reasons)


def economics(valuation, repairs_cents, asking_cents, multiplier_bps=7000):
    arv = _money((valuation or {}).get('point_cents')) if isinstance(valuation, dict) else None
    repairs = repairs_cents if isinstance(repairs_cents, int) and not isinstance(repairs_cents, bool) and 0 <= repairs_cents <= 10**14 else None
    asking = _money(asking_cents)
    missing = [name for name, value in (('arv_point_indication', arv), ('repair_estimate', repairs), ('asking_price', asking)) if value is None]
    known = {'arv_point_cents': arv, 'repair_estimate_cents': repairs, 'asking_price_cents': asking}
    if missing:
        return {'state': 'unknown', 'missing_inputs': missing, **known, 'purchase_limit_cents': None, 'headroom_cents': None, 'headroom_bps': None}
    limit = screening_mao(arv, repairs, integer(multiplier_bps, 1, 10000))
    headroom = limit - asking
    return {'state': 'known', 'missing_inputs': [], **known, 'purchase_limit_cents': limit, 'headroom_cents': headroom, 'headroom_bps': int(Decimal(headroom) * 10000 / arv)}


def _grade_from_headroom(headroom_bps):
    for grade, floor in GRADE_HEADROOM_BPS:
        if headroom_bps >= floor:
            return grade
    return 'F'


def grade_opportunity(valuation, repairs_cents=None, asking_cents=None, blocked_reasons=None, multiplier_bps=7000):
    blocked = sorted(str(reason) for reason in (blocked_reasons or []) if isinstance(reason, str))
    level, evidence_reasons = evidence_confidence(valuation)
    money = economics(valuation, repairs_cents, asking_cents, multiplier_bps)
    signals, contradictions, missing = [], list(evidence_reasons), list(money['missing_inputs'])
    grade = None
    if money['state'] == 'known':
        grade = _grade_from_headroom(money['headroom_bps'])
        if money['headroom_bps'] >= GRADE_HEADROOM_BPS[1][1]:
            signals.append('asking_price_below_screening_purchase_limit')
        else:
            contradictions.append('asking_price_at_or_above_screening_purchase_limit')
    if grade is not None and level in EVIDENCE_GRADE_CEILING:
        capped = _cap(grade, EVIDENCE_GRADE_CEILING[level])
        if capped != grade:
            contradictions.append('grade_limited_by_evidence_confidence')
        grade = capped
    elif grade is not None:
        grade = 'F'
    if level == 'verified' and money['state'] == 'known':
        signals.append('valuation_supported_by_qualified_comparables')
    if blocked:
        readiness, lockout = 'ARCHIVED', 'blocked_until_suppression_or_contact_restriction_clears'
    elif level == 'unusable':
        readiness, lockout = 'ARCHIVED', 'permanent_until_valid_valuation_evidence_exists'
    elif money['state'] == 'unknown' or grade is None:
        readiness, lockout = 'WATCH_LIST', 'research_required'
    elif grade == 'F':
        readiness, lockout = 'WATCH_LIST', 'price_dependent'
    elif level == 'verified' and GRADE_ORDER.index(grade) <= GRADE_ORDER.index(MIN_HOT_BUY_GRADE):
        readiness, lockout = 'HOT_BUY', None
    else:
        readiness, lockout = 'WATCH_LIST', 'research_required' if level in ('thin', 'supported') else 'price_dependent'
    if readiness == 'ARCHIVED':
        next_action = 'resolve_contact_restriction' if blocked else 'obtain_qualified_comparable_evidence'
    elif missing:
        next_action = 'obtain_' + missing[0]
    elif level != 'verified':
        next_action = 'strengthen_comparable_evidence'
    elif readiness == 'WATCH_LIST':
        next_action = 'monitor_price_movement'
    else:
        next_action = 'prepare_offer_for_human_approval'
    return {'schema_version': SCHEMA_VERSION, 'policy_version': POLICY_VERSION, 'grade': grade, 'readiness': readiness, 'evidence_confidence': level, 'evidence_reasons': sorted(evidence_reasons), 'economics': money, 'opportunity_signals': sorted(set(signals)), 'contradictory_evidence': sorted(set(contradictions)), 'missing_facts': missing, 'lockout_class': lockout, 'blocked_reasons': blocked, 'next_action': next_action, 'grading_basis': 'internal_screening_policy_not_an_appraisal_or_investment_guarantee', 'quote_authorized': False, 'offer_authorized': False}
