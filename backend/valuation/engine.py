from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import re


FEATURES = {'living_area_sqft': 'living_area', 'bedrooms': 'bedrooms', 'bathrooms_half_units': 'bathrooms', 'lot_sqft': 'lot', 'garage_spaces': 'garage', 'pool': 'pool', 'condition': 'condition', 'quality': 'quality'}
CATEGORIES = set(FEATURES.values()) | {'location', 'market_time', 'concessions', 'other'}
PROPERTY_TYPES = {'single_family', 'condo', 'townhouse', 'manufactured', 'two_to_four_units'}


def integer(value, minimum=0, maximum=10**14):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Expected bounded integer')
    return value


def token(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9:/_.?=&%#-]{0,299}', value):
        raise ValueError('Expected bounded source or record identifier')
    return value


def day(value):
    if not isinstance(value, str):
        raise ValueError('Expected ISO date')
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError('Expected canonical ISO date')
    return parsed


def cents(value):
    return int(value.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def validate_features(features):
    if not isinstance(features, dict) or set(features) != set(FEATURES):
        raise ValueError('All comparable feature fields are required')
    integer(features['living_area_sqft'], 1, 100000)
    for key in ('bedrooms', 'bathrooms_half_units', 'lot_sqft', 'garage_spaces'):
        integer(features[key], 0, 10000000)
    if type(features['pool']) is not bool:
        raise ValueError('Pool must be a known boolean')
    for key in ('condition', 'quality'):
        token(features[key])


def compare_sales(request, today=None):
    if not isinstance(request, dict):
        raise ValueError('Valuation request must be an object')
    as_of = day(request['as_of'])
    if as_of > (today or date.today()):
        raise ValueError('Future valuation dates are not supported')
    purpose = request['purpose']
    if purpose not in {'as_is', 'after_repair'}:
        raise ValueError('Separate as-is and after-repair purposes are required')
    if purpose == 'after_repair':
        token(request['renovation_plan_ref'])
    subject = request['subject']
    if not isinstance(subject, dict):
        raise ValueError('Subject must be an object')
    subject_id = token(subject['property_id'])
    market = token(subject['market_area'])
    if subject['property_type'] not in PROPERTY_TYPES:
        raise ValueError('Unsupported property type')
    validate_features(subject['features'])
    comps = request['comparables']
    if not isinstance(comps, list) or len(comps) > 50:
        raise ValueError('Comparable budget exceeded')
    policy = request.get('policy', {})
    if not isinstance(policy, dict) or set(policy) - {'max_age_days', 'max_distance_meters', 'max_gross_adjustment_bps', 'max_spread_bps'}:
        raise ValueError('Unknown valuation policy')
    max_age = integer(policy.get('max_age_days', 365), 1, 730)
    max_distance = integer(policy.get('max_distance_meters', 5000), 1, 50000)
    max_gross = integer(policy.get('max_gross_adjustment_bps', 3000), 1, 10000)
    max_spread = integer(policy.get('max_spread_bps', 2000), 1, 10000)
    property_counts = Counter(c.get('property_id') for c in comps if isinstance(c, dict) and isinstance(c.get('property_id'), str))
    sale_counts = Counter(c.get('sale_id') for c in comps if isinstance(c, dict) and isinstance(c.get('sale_id'), str))
    accepted, rejected, review_reasons = [], [], set()
    for index, comp in enumerate(comps):
        reason = None
        try:
            if not isinstance(comp, dict):
                raise ValueError('Malformed comparable')
            property_id, sale_id = token(comp['property_id']), token(comp['sale_id'])
            if property_id == subject_id:
                reason = 'subject_is_not_independent_comparable'
            elif property_counts[property_id] != 1 or sale_counts[sale_id] != 1:
                reason = 'duplicate_property_or_sale'
            elif comp.get('sale_status') != 'closed' or comp.get('verified') is not True or comp.get('arms_length') is not True:
                reason = 'unverified_or_nonclosed_or_nonmarket_sale'
            price = integer(comp['sale_price_cents'], 1)
            source = token(comp['source_ref'])
            comparison_review = token(comp['comparison_review_ref'])
            sold, contracted, available = day(comp['closed_on']), day(comp['contract_on']), day(comp['available_on'])
            age = (as_of - sold).days
            if not contracted <= sold <= available <= as_of:
                reason = reason or 'future_or_inconsistent_sale_evidence'
            elif age > max_age:
                reason = reason or 'sale_outside_age_policy'
            if comp['property_type'] != subject['property_type']:
                reason = reason or 'incompatible_property_type'
            distance = integer(comp['distance_meters'], 0, 1000000)
            if distance > max_distance:
                reason = reason or 'sale_outside_distance_policy'
            validate_features(comp['features'])
            adjustments = comp['adjustments']
            if not isinstance(adjustments, list) or len(adjustments) > len(CATEGORIES):
                raise ValueError('Invalid adjustment budget')
            seen, net, gross, audited = set(), 0, 0, []
            for adjustment in adjustments:
                if not isinstance(adjustment, dict) or adjustment['category'] not in CATEGORIES or adjustment['category'] in seen:
                    raise ValueError('Invalid or repeated adjustment category')
                category = adjustment['category']
                amount = integer(adjustment['amount_cents'], -10**14)
                evidence = token(adjustment['evidence_ref'])
                reviewer = token(adjustment['reviewed_by'])
                if category == 'concessions' and amount > 0:
                    raise ValueError('Concession adjustments cannot be positive')
                seen.add(category)
                net += amount
                gross += abs(amount)
                audited.append({'category': category, 'amount_cents': amount, 'evidence_ref': evidence, 'reviewed_by': reviewer})
            required = {'market_time', 'concessions'}
            required.update(category for feature, category in FEATURES.items() if subject['features'][feature] != comp['features'][feature])
            if token(comp['market_area']) != market:
                token(comp['competitive_market_review_ref'])
                required.add('location')
            if not required <= seen:
                reason = reason or 'unsupported_feature_time_or_concession_adjustment'
            adjusted = price + net
            if not 0 < adjusted <= 10**14:
                reason = reason or 'invalid_adjusted_value'
            if reason:
                rejected.append({'input_index': index, 'reason': reason})
                continue
            gross_bps = int(Decimal(gross) * 10000 / price)
            if gross * 10000 > max_gross * price:
                review_reasons.add('large_gross_adjustments')
            area_gap = Decimal(abs(subject['features']['living_area_sqft'] - comp['features']['living_area_sqft'])) / subject['features']['living_area_sqft']
            weight = Decimal(1) / (1 + Decimal(age) / 180 + Decimal(distance) / 2000 + area_gap)
            accepted.append({'property_id': property_id, 'sale_id': sale_id, 'source_ref': source, 'comparison_review_ref': comparison_review, 'closed_on': sold.isoformat(), 'contract_on': contracted.isoformat(), 'available_on': available.isoformat(), 'sale_price_cents': price, 'adjustments': audited, 'net_adjustment_cents': net, 'gross_adjustment_cents': gross, 'gross_adjustment_bps': gross_bps, 'adjusted_value_cents': adjusted, 'sale_price_per_sqft_cents': cents(Decimal(price) / comp['features']['living_area_sqft']), 'weight': weight})
        except (KeyError, TypeError, ValueError, ArithmeticError):
            rejected.append({'input_index': index, 'reason': 'malformed_or_unsupported_evidence'})
    point, low, high, spread_bps = None, None, None, None
    if len(accepted) >= 3:
        total_weight = sum(c['weight'] for c in accepted)
        estimate = cents(sum(Decimal(c['adjusted_value_cents']) * c['weight'] for c in accepted) / total_weight)
        lower = min(c['adjusted_value_cents'] for c in accepted)
        upper = max(c['adjusted_value_cents'] for c in accepted)
        spread_bps = int(Decimal(upper - lower) * 10000 / estimate)
        if (upper - lower) * 10000 > max_spread * estimate:
            review_reasons.add('wide_adjusted_sale_dispersion')
        if not review_reasons:
            point, low, high = estimate, lower, upper
    for comp in accepted:
        comp['weight'] = str(comp['weight'].quantize(Decimal('0.000001')))
    status = 'needs_data' if len(accepted) < 3 else 'needs_review' if review_reasons else 'ready_advisory'
    return {'schema_version': '1.0', 'method': 'evidence_adjusted_sales_comparison', 'purpose': purpose, 'subject_id': subject_id, 'as_of': as_of.isoformat(), 'status': status, 'point_cents': point, 'supported_low_cents': low, 'supported_high_cents': high, 'range_meaning': 'observed_adjusted_sale_span_not_statistical_confidence_interval', 'spread_bps': spread_bps, 'comparable_count': len(accepted), 'accepted_comparables': sorted(accepted, key=lambda c: c['sale_id']), 'rejected_comparables': rejected, 'review_reasons': sorted(review_reasons), 'quote_authorized': False, 'offer_authorized': False, 'evidence_verification': 'trusted_input_attestations_not_independent_source_research'}


def valuation_for_brief(lead_id, lead, prop, packet):
    request = packet.get('valuation_inputs')
    if request is None:
        return {'schema_version': '1.0', 'lead_id': lead_id, 'status': 'needs_data', 'quote_authorized': False, 'offer_authorized': False}
    try:
        if not isinstance(request, dict) or not isinstance(prop.get('id'), str) or lead.get('property_id') != prop['id'] or request.get('subject', {}).get('property_id') != prop['id']:
            raise ValueError('Subject binding failed')
        result = compare_sales(request)
        result['lead_id'] = lead_id
        if (date.today() - day(result['as_of'])).days > 30:
            result.update(status='needs_data', point_cents=None, supported_low_cents=None, supported_high_cents=None)
            result['review_reasons'].append('stale_valuation_effective_date')
        return result
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError):
        return {'schema_version': '1.0', 'lead_id': lead_id, 'status': 'invalid_input', 'quote_authorized': False, 'offer_authorized': False}
