from copy import deepcopy
from datetime import date, timedelta
from fractions import Fraction
from itertools import permutations
import random

import pytest

from backend.valuation.candidates import rank_candidates
from backend.valuation.engine import compare_sales, reconcile_indications
from backend.valuation.finance import flip_analysis
from test_valuation import request


def exact_point(rows, area):
    weights = [1 / (1 + Fraction(r['age_days'], 180) + Fraction(r['distance_meters'], 2000) + Fraction(abs(area - r['living_area_sqft']), area)) for r in rows]
    exact = sum(r['adjusted_value_cents'] * w for r, w in zip(rows, weights)) / sum(weights)
    return (2 * exact.numerator + exact.denominator) // (2 * exact.denominator)


def test_exact_half_cent_is_correct_in_every_comparable_order():
    payload = request('as_is')
    for comp, price, area, distance in zip(payload['comparables'], [41315220, 42649506, 41155786], [2700, 2700, 1800], [5000, 5000, 0]):
        comp['features'] = {**payload['subject']['features'], 'living_area_sqft': area}
        comp['sale_price_cents'] = price
        comp['distance_meters'] = distance
        comp['closed_on'] = (date.today() - timedelta(days=360)).isoformat()
        comp['contract_on'] = comp['available_on'] = comp['closed_on']
        comp['adjustments'] = [{'category': category, 'amount_cents': 0, 'evidence_ref': 'synthetic:half-cent-oracle', 'reviewed_by': 'test:oracle'} for category in ('market_time', 'concessions', 'living_area')]
    for comps in permutations(payload['comparables']):
        assert compare_sales({**payload, 'comparables': list(comps)})['point_cents'] == 41569075


@pytest.mark.parametrize('seed', range(20))
def test_random_exact_reconciliation_order_bounds_and_money_scale(seed):
    rng = random.Random(seed)
    for _ in range(250):
        area = rng.randrange(300, 10000)
        rows = [{'adjusted_value_cents': rng.randrange(1, 10**14), 'age_days': rng.randrange(731), 'distance_meters': rng.randrange(1000001), 'living_area_sqft': rng.randrange(1, 100001)} for _ in range(rng.randrange(3, 20))]
        original = deepcopy(rows)
        result = reconcile_indications(rows, area)
        assert result['point_cents'] == exact_point(rows, area)
        assert min(r['adjusted_value_cents'] for r in rows) <= result['point_cents'] <= max(r['adjusted_value_cents'] for r in rows)
        assert rows == original
        rng.shuffle(rows)
        assert reconcile_indications(rows, area)['point_cents'] == result['point_cents']


@pytest.mark.parametrize('seed', range(20))
def test_random_flip_limit_is_feasible_and_the_next_cent_is_not(seed):
    rng = random.Random(seed + 1941)
    for _ in range(500):
        resale = rng.randrange(1, 10**10)
        repairs, fixed, target = [rng.randrange(0, 10**8) for _ in range(3)]
        buying, selling = rng.randrange(10001), rng.randrange(10001)
        def profit(amount):
            return resale - (resale * selling + 5000) // 10000 - amount - (amount * buying + 5000) // 10000 - repairs - fixed
        result = flip_analysis(resale, 0, repairs, fixed, 0, 0, target, buying, selling)
        limit = result['purchase_limit_cents']
        assert result['target_profit_feasible_at_limit'] == (profit(limit) >= target)
        if result['target_profit_feasible_at_limit']:
            assert profit(limit) >= target
            assert profit(limit + 1) < target
        else:
            assert limit == 0 and profit(0) < target


@pytest.mark.parametrize('seed', range(20))
def test_random_poisoned_evidence_is_withheld_without_changing_inputs(seed):
    rng = random.Random(1000 + seed)
    mutations = ('source_ref', 'comparison_review_ref', 'contract_on', 'available_on', 'features', 'adjustments', 'sale_price_cents', 'verified', 'arms_length', 'sale_status')
    for _ in range(100):
        payload = request()
        comp = rng.choice(payload['comparables'])
        key = rng.choice(mutations)
        if key in ('verified', 'arms_length'):
            comp[key] = False
        elif key == 'sale_status':
            comp[key] = 'pending'
        elif rng.randrange(2):
            comp.pop(key)
        else:
            comp[key] = rng.choice([None, True, [], {}, 4.5, 'unknown\n'])
        saved = deepcopy(payload)
        report = compare_sales(payload)
        assert report['point_cents'] is None
        assert report['quote_authorized'] is report['offer_authorized'] is False
        assert report['status'] == 'needs_data'
        assert payload == saved


def test_candidate_selection_is_price_blind_and_does_not_attest_review():
    payload = request('as_is')
    original = rank_candidates(payload['subject'], payload['comparables'], payload['as_of'])
    candidates = deepcopy(payload['comparables'])
    for comp in candidates:
        comp['sale_price_cents'] = 1
        comp['verified'] = False
        comp.pop('comparison_review_ref')
        comp.pop('adjustments')
    assert rank_candidates(payload['subject'], candidates, payload['as_of']) == original
    assert original['status'] == 'candidate_review_only'
    assert original['offer_authorized'] is original['quote_authorized'] is False
    assert all(c['review_required'] is True for c in original['candidates'])


@pytest.mark.parametrize('bad', ['self', 'duplicate', 'future', 'unavailable', 'stale', 'wrong_market', 'wrong_type', 'large_area', 'missing_feature', 'nonmarket', 'not_closed'])
def test_bad_candidate_is_excluded_before_ranking(bad):
    payload = request('as_is')
    candidate = payload['comparables'][0]
    if bad == 'self': candidate['property_id'] = payload['subject']['property_id']
    if bad == 'duplicate': payload['comparables'].append(deepcopy(candidate))
    if bad == 'future': candidate['closed_on'] = (date.today() + timedelta(days=1)).isoformat()
    if bad == 'unavailable': candidate['available_on'] = (date.today() + timedelta(days=1)).isoformat()
    if bad == 'stale': candidate['closed_on'] = (date.today() - timedelta(days=366)).isoformat()
    if bad == 'wrong_market': candidate['market_area'] = 'other'
    if bad == 'wrong_type': candidate['property_type'] = 'condo'
    if bad == 'large_area': candidate['features']['living_area_sqft'] = 3000
    if bad == 'missing_feature': candidate['features'].pop('condition')
    if bad == 'nonmarket': candidate['arms_length'] = False
    if bad == 'not_closed': candidate['sale_status'] = 'listed'
    result = rank_candidates(payload['subject'], payload['comparables'], payload['as_of'])
    assert candidate['sale_id'] not in {c['sale_id'] for c in result['candidates']}
    assert result['rejected_candidates']


def test_ranking_is_repeatable_and_inputs_are_unchanged():
    payload = request('as_is')
    saved = deepcopy(payload)
    original = rank_candidates(payload['subject'], payload['comparables'], payload['as_of'])
    for comps in permutations(payload['comparables']):
        result = rank_candidates(payload['subject'], list(comps), payload['as_of'])
        assert result['candidates'] == original['candidates']
    assert payload == saved
