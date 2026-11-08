from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from backend.rehab.costbook import (CALIBRATION_STATUS, CONCEALED_AREAS, COSTBOOK, COSTBOOK_VERSION,
                                    PERMIT_TRIGGERING, PRICE_INDEX_AT_PRICING_MILLI, PRICE_INDEX_DESCRIPTION,
                                    PRICE_INDEX_SERIES, PRICEABLE_FROM, PRICED_ON, SEVERITIES, SOURCE_CLASSES,
                                    STALE_AFTER_DAYS, TIMELINE_WEEKS, reprice_cents)
from backend.valuation.engine import integer, token

SCHEMA_VERSION = '1.0'
EVIDENCE_CLASSES = ('directly_visible', 'plausibly_inferred', 'not_assessable_from_source')
INFERRED_WIDENING_BPS = 3000
MAX_OBSERVATIONS = 200


def _round(value):
    return int(Decimal(value).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _band(area, severity, living_area_sqft):
    entry = COSTBOOK[area]
    low, expected, high = entry[severity]
    if entry['unit'] == 'per_living_sqft':
        return tuple(_round(Decimal(amount) * living_area_sqft) for amount in (low, expected, high))
    return (low, expected, high)


def validate_observation(observation):
    if not isinstance(observation, dict) or set(observation) != {'area', 'finding', 'severity', 'evidence_class', 'source_class', 'source_ref', 'observed_by', 'quantity'}:
        raise ValueError('Observation requires area, finding, severity, evidence class, source class, source reference, observer and quantity')
    area = observation['area']
    if area not in COSTBOOK:
        raise ValueError('Unknown scope area')
    if observation['severity'] not in SEVERITIES:
        raise ValueError('Unknown severity')
    if observation['evidence_class'] not in EVIDENCE_CLASSES:
        raise ValueError('Unknown evidence class')
    if observation['source_class'] not in SOURCE_CLASSES:
        raise ValueError('Unknown source class')
    token(observation['source_ref'])
    token(observation['observed_by'])
    if not isinstance(observation['finding'], str) or not 0 < len(observation['finding']) <= 500:
        raise ValueError('Finding text is required')
    integer(observation['quantity'], 1, 500)
    return observation


def _priceable(observation):
    if observation['evidence_class'] == 'not_assessable_from_source':
        return False, 'observer_marked_it_not_assessable_from_this_source'
    allowed = PRICEABLE_FROM[observation['source_class']]
    if allowed is not None and observation['area'] not in allowed:
        if observation['area'] in CONCEALED_AREAS:
            return False, 'concealed_system_cannot_be_priced_from_' + observation['source_class']
        return False, 'area_not_assessable_from_' + observation['source_class']
    return True, None


def _index_state(current_index_milli, today):
    age = (today - date.fromisoformat(PRICED_ON)).days
    state = {'series': PRICE_INDEX_SERIES, 'series_description': PRICE_INDEX_DESCRIPTION,
             'priced_on': PRICED_ON, 'age_days': age, 'stale': age > STALE_AFTER_DAYS,
             'index_at_pricing_milli': PRICE_INDEX_AT_PRICING_MILLI,
             'index_supplied_milli': current_index_milli, 'repriced': False, 'factor_bps': None}
    if current_index_milli is None or PRICE_INDEX_AT_PRICING_MILLI is None:
        state['reason'] = 'costbook_was_never_tied_to_an_index_reading_so_it_cannot_be_repriced'
        return state, None
    state['repriced'] = True
    state['factor_bps'] = reprice_cents(10000, PRICE_INDEX_AT_PRICING_MILLI, current_index_milli)
    state['reason'] = None
    return state, current_index_milli


def estimate_rehab(observations, living_area_sqft, contingency_bps=1500, current_index_milli=None, today=None):
    area_sqft = integer(living_area_sqft, 1, 100000)
    contingency = integer(contingency_bps, 0, 10000)
    if not isinstance(observations, list) or len(observations) > MAX_OBSERVATIONS:
        raise ValueError('A bounded observation list is required')
    priced, inspections, seen = [], [], set()
    low = expected = high = 0
    for observation in observations:
        validate_observation(observation)
        key = (observation['area'], observation['source_ref'])
        if key in seen:
            raise ValueError('Duplicate observation for the same area and source')
        seen.add(key)
        ok, refusal = _priceable(observation)
        if not ok:
            inspections.append({'area': observation['area'], 'finding': observation['finding'],
                                'severity': observation['severity'], 'reason': refusal,
                                'source_ref': observation['source_ref'],
                                'required_before_pricing': 'licensed_inspection_or_contractor_bid'})
            continue
        band_low, band_expected, band_high = _band(observation['area'], observation['severity'], area_sqft)
        quantity = observation['quantity']
        band_low, band_expected, band_high = band_low * quantity, band_expected * quantity, band_high * quantity
        widened = observation['evidence_class'] == 'plausibly_inferred'
        if widened:
            band_low = _round(Decimal(band_low) * (10000 - INFERRED_WIDENING_BPS) / 10000)
            band_high = _round(Decimal(band_high) * (10000 + INFERRED_WIDENING_BPS) / 10000)
        low, expected, high = low + band_low, expected + band_expected, high + band_high
        priced.append({'area': observation['area'], 'severity': observation['severity'], 'quantity': quantity,
                       'evidence_class': observation['evidence_class'], 'source_class': observation['source_class'],
                       'source_ref': observation['source_ref'], 'band_widened_for_inference': widened,
                       'low_cents': band_low, 'expected_cents': band_expected, 'high_cents': band_high,
                       'permit_likely': observation['area'] in PERMIT_TRIGGERING})
    index_state, factor_target = _index_state(current_index_milli, today or date.today())
    if factor_target is not None:
        for item in priced:
            for key in ('low_cents', 'expected_cents', 'high_cents'):
                item[key] = reprice_cents(item[key], PRICE_INDEX_AT_PRICING_MILLI, factor_target)
        low = reprice_cents(low, PRICE_INDEX_AT_PRICING_MILLI, factor_target)
        expected = reprice_cents(expected, PRICE_INDEX_AT_PRICING_MILLI, factor_target)
        high = reprice_cents(high, PRICE_INDEX_AT_PRICING_MILLI, factor_target)
    priced_areas = {item['area'] for item in priced}
    satisfied = [entry for entry in inspections if entry['area'] in priced_areas]
    inspections = [entry for entry in inspections if entry['area'] not in priced_areas]
    contingency_cents = _round(Decimal(expected) * contingency / 10000)
    weeks = max([0] + [TIMELINE_WEEKS[item['severity']] for item in priced])
    sequential = sum(TIMELINE_WEEKS[item['severity']] for item in priced)
    return {
        'schema_version': SCHEMA_VERSION,
        'costbook_version': COSTBOOK_VERSION,
        'calibration_status': CALIBRATION_STATUS,
        'price_index': index_state,
        'living_area_sqft': area_sqft,
        'priced_items': sorted(priced, key=lambda item: (-item['expected_cents'], item['area'])),
        'inspection_required': sorted(inspections, key=lambda item: item['area']),
        'inspection_satisfied_by_a_stronger_source': sorted({entry['area'] for entry in satisfied}),
        'low_cents': low,
        'expected_cents': expected,
        'high_cents': high,
        'contingency_bps': contingency,
        'contingency_cents': contingency_cents,
        'expected_with_contingency_cents': expected + contingency_cents,
        'permits_likely': sorted({item['area'] for item in priced if item['permit_likely']}),
        'timeline_weeks_if_parallel': weeks,
        'timeline_weeks_if_sequential': sequential,
        'unpriced_scope_items': len(inspections),
        'estimate_is_complete': not inspections,
        'basis': 'uncalibrated_costbook_screening_estimate_not_an_inspection_or_contractor_bid',
        'quote_authorized': False,
        'offer_authorized': False,
    }
