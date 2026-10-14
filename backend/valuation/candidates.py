from collections import Counter
from fractions import Fraction

from backend.valuation.engine import PROPERTY_TYPES, day, integer, token, validate_features


def rank_candidates(subject, candidates, as_of, limit=5):
    effective = day(as_of)
    subject_id = token(subject['property_id'])
    market = token(subject['market_area'])
    if subject['property_type'] not in PROPERTY_TYPES:
        raise ValueError('Unsupported subject type')
    features = subject['features']
    validate_features(features)
    integer(limit, 3, 50)
    if not isinstance(candidates, list) or len(candidates) > 10000:
        raise ValueError('Candidate budget exceeded')
    properties = Counter(c.get('property_id') for c in candidates if isinstance(c, dict) and isinstance(c.get('property_id'), str))
    sales = Counter(c.get('sale_id') for c in candidates if isinstance(c, dict) and isinstance(c.get('sale_id'), str))
    eligible, rejected = [], []
    for index, candidate in enumerate(candidates):
        try:
            property_id, sale_id = token(candidate['property_id']), token(candidate['sale_id'])
            if property_id == subject_id or properties[property_id] != 1 or sales[sale_id] != 1:
                raise ValueError('Subject or duplicate candidate')
            if candidate.get('sale_status') != 'closed' or candidate.get('arms_length') is False:
                raise ValueError('Nonclosed or known nonmarket sale')
            if candidate['property_type'] != subject['property_type'] or token(candidate['market_area']) != market:
                raise ValueError('Different property type or market')
            closed, available = day(candidate['closed_on']), day(candidate['available_on'])
            age = (effective - closed).days
            if not closed <= available <= effective or not 0 <= age <= 365:
                raise ValueError('Unavailable or stale candidate')
            other = candidate['features']
            validate_features(other)
            area_gap = Fraction(abs(features['living_area_sqft'] - other['living_area_sqft']), features['living_area_sqft'])
            if area_gap > Fraction(1, 4):
                raise ValueError('Living area outside candidate screening band')
            lot_gap = Fraction(abs(features['lot_sqft'] - other['lot_sqft']), max(1, features['lot_sqft'], other['lot_sqft']))
            score = area_gap + lot_gap / 4 + Fraction(age, 3650)
            score += int(features['quality'] != other['quality']) + int(features['condition'] != other['condition'])
            score += Fraction(abs(features['bedrooms'] - other['bedrooms']), 4)
            score += Fraction(abs(features['bathrooms_half_units'] - other['bathrooms_half_units']), 8)
            score += Fraction(abs(features['garage_spaces'] - other['garage_spaces']), 4) + int(features['pool'] != other['pool'])
            differences = sorted(key for key in features if features[key] != other[key])
            eligible.append((score, sale_id, {'property_id': property_id, 'sale_id': sale_id, 'source_ref': token(candidate['source_ref']), 'feature_differences': differences, 'review_required': True}))
        except (KeyError, TypeError, ValueError):
            rejected.append({'input_index': index, 'reason': 'candidate_not_eligible'})
    eligible.sort(key=lambda row: (row[0], row[1]))
    return {'status': 'candidate_review_only', 'candidates': [row[2] for row in eligible[:limit]], 'eligible_count': len(eligible), 'rejected_candidates': rejected, 'quote_authorized': False, 'offer_authorized': False, 'screening_policy': 'same_type_market_365days_25percent_area_gap_not_appraisal_standard'}
