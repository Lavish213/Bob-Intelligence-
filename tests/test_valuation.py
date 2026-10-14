from copy import deepcopy
from datetime import date, timedelta
from itertools import permutations
import json
import subprocess
import sys

import pytest

from backend.valuation.engine import compare_sales, valuation_for_brief
from backend.valuation.finance import cash_on_cash_return, cost_approach, flip_analysis, mortgage_payment, rental_analysis, repairs_with_contingency, screening_mao
from backend.call_planner.brief_generator import generate_call_brief


def request(purpose='after_repair'):
    now = date.today()
    features = {'living_area_sqft': 1800, 'bedrooms': 3, 'bathrooms_half_units': 4, 'lot_sqft': 6000, 'garage_spaces': 2, 'pool': False, 'condition': 'renovated', 'quality': 'standard'}
    result = {'as_of': now.isoformat(), 'purpose': purpose, 'renovation_plan_ref': 'scope:approved-1', 'subject': {'property_id': 'subject-1', 'market_area': 'stockton-test-market', 'property_type': 'single_family', 'features': features}, 'comparables': []}
    for number, area, price, adjustment, concession in [(1, 1700, 45000000, 1000000, 0), (2, 1850, 46500000, -500000, 0), (3, 1800, 46200000, 0, -200000)]:
        comp = {'property_id': f'comp-{number}', 'sale_id': f'sale-{number}', 'sale_status': 'closed', 'verified': True, 'arms_length': True, 'source_ref': f'mls:synthetic-{number}', 'comparison_review_ref': f'review:synthetic-{number}', 'sale_price_cents': price, 'closed_on': (now - timedelta(days=30)).isoformat(), 'contract_on': (now - timedelta(days=60)).isoformat(), 'available_on': (now - timedelta(days=20)).isoformat(), 'market_area': 'stockton-test-market', 'property_type': 'single_family', 'distance_meters': 500, 'features': {**features, 'living_area_sqft': area}, 'adjustments': [{'category': 'market_time', 'amount_cents': 0, 'evidence_ref': 'trend:stable-period', 'reviewed_by': 'operator:synthetic'}, {'category': 'concessions', 'amount_cents': concession, 'evidence_ref': 'sale:concession-impact', 'reviewed_by': 'operator:synthetic'}]}
        if adjustment:
            comp['adjustments'].append({'category': 'living_area', 'amount_cents': adjustment, 'evidence_ref': 'paired-sales:synthetic-marginal-area', 'reviewed_by': 'operator:synthetic'})
        result['comparables'].append(comp)
    return result


def test_supported_adjusted_sales_are_460k_not_raw_average_price_per_foot():
    result = compare_sales(request())
    assert result['point_cents'] == result['supported_low_cents'] == result['supported_high_cents'] == 46000000
    assert result['status'] == 'ready_advisory'
    assert result['quote_authorized'] is result['offer_authorized'] is False
    assert {c['adjusted_value_cents'] for c in result['accepted_comparables']} == {46000000}
    assert result['accepted_comparables'][0]['net_adjustment_cents'] == 1000000
    assert result['accepted_comparables'][1]['net_adjustment_cents'] == -500000


def test_input_order_does_not_change_reconciliation():
    base = request()
    for comps in permutations(base['comparables']):
        result = compare_sales({**base, 'comparables': list(comps)})
        assert result['point_cents'] == 46000000


@pytest.mark.parametrize('mutation', ['listed', 'unverified', 'nonmarket', 'future', 'unavailable', 'stale', 'different_type', 'distant', 'missing_adjustment', 'duplicate', 'subject', 'float_money', 'bool_money', 'unknown_condition', 'positive_concession', 'missing_reviewer', 'repeat_adjustment'])
def test_bad_comp_cannot_create_a_three_sale_valuation(mutation):
    payload = request()
    comp = payload['comparables'][0]
    if mutation == 'listed': comp['sale_status'] = 'active'
    if mutation == 'unverified': comp['verified'] = False
    if mutation == 'nonmarket': comp['arms_length'] = False
    if mutation == 'future': comp['closed_on'] = (date.today() + timedelta(days=1)).isoformat()
    if mutation == 'unavailable': comp['available_on'] = (date.today() + timedelta(days=1)).isoformat()
    if mutation == 'stale': comp['closed_on'] = (date.today() - timedelta(days=400)).isoformat()
    if mutation == 'different_type': comp['property_type'] = 'manufactured'
    if mutation == 'distant': comp['distance_meters'] = 9000
    if mutation == 'missing_adjustment': comp['adjustments'] = comp['adjustments'][:2]
    if mutation == 'duplicate': payload['comparables'].append(deepcopy(comp))
    if mutation == 'subject': comp['property_id'] = 'subject-1'
    if mutation == 'float_money': comp['sale_price_cents'] = 45000000.0
    if mutation == 'bool_money': comp['sale_price_cents'] = True
    if mutation == 'unknown_condition': del comp['features']['condition']
    if mutation == 'positive_concession': comp['adjustments'][1]['amount_cents'] = 100
    if mutation == 'missing_reviewer': del comp['adjustments'][0]['reviewed_by']
    if mutation == 'repeat_adjustment': comp['adjustments'].append(deepcopy(comp['adjustments'][0]))
    result = compare_sales(payload)
    assert result['status'] == 'needs_data'
    assert result['point_cents'] is None
    assert result['rejected_comparables']


def test_condition_difference_requires_market_evidence_not_renovation_cost():
    payload = request()
    payload['comparables'][0]['features']['condition'] = 'unrenovated'
    assert compare_sales(payload)['point_cents'] is None


def test_time_and_concession_zeroes_still_require_reviewed_evidence():
    payload = request()
    payload['comparables'][0]['adjustments'] = payload['comparables'][0]['adjustments'][2:]
    assert compare_sales(payload)['point_cents'] is None


def test_after_repair_requires_an_explicit_renovation_scope():
    payload = request()
    del payload['renovation_plan_ref']
    with pytest.raises(KeyError):
        compare_sales(payload)
    payload['purpose'] = 'as_is'
    assert compare_sales(payload)['purpose'] == 'as_is'


def test_wide_disagreement_is_reviewed_not_trimmed_until_target_price_matches():
    payload = request()
    payload['comparables'][0]['sale_price_cents'] = 80000000
    result = compare_sales(payload)
    assert result['status'] == 'needs_review'
    assert result['point_cents'] is None
    assert 'wide_adjusted_sale_dispersion' in result['review_reasons']
    assert len(result['accepted_comparables']) == 3


def test_large_gross_offsetting_adjustments_cannot_hide_behind_small_net_adjustment():
    payload = request()
    payload['comparables'][0]['adjustments'].extend([{'category': 'condition', 'amount_cents': 20000000, 'evidence_ref': 'paired:condition', 'reviewed_by': 'operator:synthetic'}, {'category': 'other', 'amount_cents': -20000000, 'evidence_ref': 'paired:other', 'reviewed_by': 'operator:synthetic'}])
    result = compare_sales(payload)
    assert result['status'] == 'needs_review'
    assert 'large_gross_adjustments' in result['review_reasons']


def test_binding_missing_data_and_stale_effective_date_fail_closed():
    lead, prop = {'property_id': 'subject-1'}, {'id': 'subject-1'}
    assert valuation_for_brief('lead-1', lead, prop, {})['status'] == 'needs_data'
    assert valuation_for_brief('lead-1', lead, {'id': 'another'}, {'valuation_inputs': request()})['status'] == 'invalid_input'
    payload = request()
    payload['as_of'] = (date.today() - timedelta(days=60)).isoformat()
    for comp in payload['comparables']:
        for key in ('closed_on', 'contract_on', 'available_on'):
            comp[key] = (date.fromisoformat(comp[key]) - timedelta(days=60)).isoformat()
    result = valuation_for_brief('lead-1', lead, prop, {'valuation_inputs': payload})
    assert result['status'] == 'needs_data' and result['point_cents'] is None


def test_actual_brief_includes_bound_research_without_granting_offer_authority():
    lead = {'property_id': 'subject-1', 'opted_out': False, 'dnc_blocked': False, 'owner_phone': '+12095550123'}
    packet = {'valuation_inputs': request()}
    brief = generate_call_brief('lead-1', lead, {'id': 'subject-1'}, packet, {}).to_dict()
    assert brief['evidence']['valuation']['point_cents'] == 46000000
    assert brief['evidence']['valuation']['lead_id'] == brief['lead_id']
    assert brief['ready_for_call'] is False


def test_repairs_and_70_percent_screen_are_separate_from_market_value():
    budget = repairs_with_contingency([2000000, 1000000], 1500)
    assert budget == {'base_cents': 3000000, 'contingency_cents': 450000, 'total_cents': 3450000}
    assert screening_mao(46000000, 6000000) == 26200000


def test_detailed_flip_costs_and_offer_limit_match_hand_calculation():
    report = flip_analysis(46000000, 28000000, 6000000, 300000, 600000, 1000000, 5000000, 200, 600)
    assert report['total_project_cost_cents'] == 39220000
    assert report['profit_cents'] == 6780000
    assert report['purchase_limit_cents'] == 29745098
    assert report['quote_authorized'] is False
    limit_report = flip_analysis(46000000, report['purchase_limit_cents'], 6000000, 300000, 600000, 1000000, 5000000, 200, 600)
    assert limit_report['profit_cents'] >= 5000000


@pytest.mark.parametrize('resale', range(101, 130))
def test_offer_limit_remains_conservative_after_cent_rounding(resale):
    report = flip_analysis(resale, 1, 20, 5, 4, 2, 10, 233, 677)
    recomputed = flip_analysis(resale, report['purchase_limit_cents'], 20, 5, 4, 2, 10, 233, 677)
    assert recomputed['profit_cents'] >= 10


def test_negative_deals_and_impossible_target_are_not_success():
    report = flip_analysis(10000, 9000, 5000, 0, 0, 0, 12000, 0, 0)
    assert report['profit_cents'] == -4000
    assert report['purchase_limit_cents'] == 0
    assert report['target_profit_feasible_at_limit'] is False


def test_rental_noi_is_not_cash_flow_and_income_value_is_not_sale_appraisal():
    report = rental_analysis(3000000, 500, 0, 900000, 1440000, 240000, 30000000, 650)
    assert report['noi_cents'] == 1950000
    assert report['cash_flow_after_debt_and_reserves_cents'] == 270000
    assert report['income_indication_cents'] == 30000000
    assert report['dscr'] == '1.354167'
    assert cash_on_cash_return(report['cash_flow_after_debt_and_reserves_cents'], 6000000) == '0.045000'


def test_mortgage_pi_excludes_taxes_insurance_hoa_and_mortgage_insurance():
    report = mortgage_payment(30000000, 600, 360, 30000, 10000, 0, 10000)
    assert report['monthly_principal_interest_cents'] == 179865
    assert report['monthly_housing_cost_cents'] == 229865
    assert mortgage_payment(120000, 0, 12)['monthly_principal_interest_cents'] == 10000


def test_cost_indication_requires_depreciation_and_does_not_become_arv():
    assert cost_approach(10000000, 30000000, 5000000, 2000000, 1000000)['cost_indication_cents'] == 32000000
    with pytest.raises(ValueError):
        cost_approach(100, 100, 101, 0, 0)


@pytest.mark.parametrize('value', [True, 1.2, '6000000', -1])
def test_noninteger_or_negative_cost_inputs_are_rejected(value):
    with pytest.raises(ValueError):
        screening_mao(46000000, value)


def test_competing_market_needs_review_and_location_adjustment():
    payload = request()
    comp = payload['comparables'][0]
    comp['market_area'] = 'competing-market'
    assert compare_sales(payload)['point_cents'] is None
    comp['competitive_market_review_ref'] = 'review:competitive-market'
    comp['adjustments'].append({'category': 'location', 'amount_cents': 0, 'evidence_ref': 'paired:location-equivalent', 'reviewed_by': 'operator:synthetic'})
    assert compare_sales(payload)['point_cents'] == 46000000


def test_missing_physical_and_legal_comparison_review_is_not_implicit_approval():
    payload = request()
    del payload['comparables'][0]['comparison_review_ref']
    assert compare_sales(payload)['point_cents'] is None


def test_future_effective_date_and_unknown_policies_are_rejected():
    payload = request()
    payload['as_of'] = (date.today() + timedelta(days=1)).isoformat()
    with pytest.raises(ValueError):
        compare_sales(payload)
    payload = request()
    payload['policy'] = {'ignore_bad_sales': True}
    with pytest.raises(ValueError):
        compare_sales(payload)


def test_repair_budget_limits_and_negative_rental_income_do_not_fabricate_value():
    with pytest.raises(ValueError):
        repairs_with_contingency([], 0)
    with pytest.raises(ValueError):
        repairs_with_contingency([100], 10001)
    result = rental_analysis(0, 0, 0, 10000, 0, 0, 10000000, 500)
    assert result['noi_cents'] == -10000 and result['income_indication_cents'] is None
    assert result['dscr'] is None


def test_cli_emits_json_for_reviewed_input_and_fail_closed_for_invalid_input(tmp_path):
    input_file = tmp_path / 'input.json'
    input_file.write_text(json.dumps(request()))
    command = [sys.executable, '-m', 'backend.valuation', str(input_file)]
    run = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert run.returncode == 0
    assert json.loads(run.stdout)['point_cents'] == 46000000
    input_file.write_text('{"malformed": true}')
    run = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert run.returncode == 2
    assert json.loads(run.stdout)['quote_authorized'] is False


def test_cli_rejects_oversized_input_before_json_parsing(tmp_path):
    input_file = tmp_path / 'input.json'
    input_file.write_text(' ' * 2000001)
    run = subprocess.run([sys.executable, '-m', 'backend.valuation', str(input_file)], capture_output=True, text=True, timeout=15)
    assert run.returncode == 2 and json.loads(run.stdout)['status'] == 'invalid_input'
