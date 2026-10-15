from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

from backend.valuation.local_benchmark import evaluate, summarize


def cohort(purpose='as_is'):
    evidence = {'source_ref': 'fixture:synthetic-not-a-real-sale', 'sha256': 'a' * 64}
    features = {'living_area_sqft': 1800, 'bedrooms': 3, 'bathrooms_half_units': 4, 'lot_sqft': 6000, 'garage_spaces': 2, 'pool': False, 'condition': 'renovated', 'quality': 'standard'}
    request = {'as_of': '2026-06-01', 'purpose': purpose, 'subject': {'property_id': 'subject:1', 'market_area': 'stockton:fixture', 'property_type': 'single_family', 'features': features}, 'comparables': []}
    if purpose == 'after_repair':
        request['renovation_plan_ref'] = 'scope:1'
    for i in range(3):
        request['comparables'].append({'property_id': f'comp:{i}', 'sale_id': f'sale:{i}', 'source_ref': f'fixture:{i}', 'sale_status': 'closed', 'verified': True, 'arms_length': True, 'comparison_review_ref': 'fixture:review', 'sale_price_cents': 46000000, 'closed_on': '2026-04-15', 'contract_on': '2026-03-15', 'available_on': '2026-04-20', 'property_type': 'single_family', 'market_area': 'stockton:fixture', 'distance_meters': 500, 'features': deepcopy(features), 'adjustments': [{'category': category, 'amount_cents': 0, 'evidence_ref': 'fixture:review', 'reviewed_by': 'fixture:reviewer'} for category in ('market_time', 'concessions')]})
    truth = {'property_id': 'subject:1', 'sale_id': 'target:1', 'kind': 'closed_sale', 'price_cents': 50000000, 'contract_on': '2026-06-20', 'closed_on': '2026-07-01', 'available_on': '2026-07-10', 'arms_length': True, 'sale_ref': evidence, 'condition_basis': 'unchanged_as_is' if purpose == 'as_is' else 'completed_renovation', 'condition_ref': evidence, 'renovation_plan_ref': None if purpose == 'as_is' else 'scope:1', 'completed_on': None if purpose == 'as_is' else '2026-06-15'}
    return {'schema_version': '1.0', 'dataset_kind': 'synthetic', 'cohort_ref': evidence, 'rights_ref': evidence, 'selection_ref': evidence, 'cases': [{'case_id': 'case:1', 'city': 'stockton', 'county_fips': '06077', 'geography_ref': evidence, 'features_observed_on': '2026-05-25', 'request': request, 'truth': truth}]}


def test_actual_predictor_metrics_keep_target_separate_and_never_grant_authority():
    original = cohort()
    saved = deepcopy(original)
    result = evaluate(original, '2026-08-01')
    assert original == saved
    assert result['metrics']['mean_absolute_error_dollars'] == '40000.0000'
    assert result['metrics']['mean_absolute_percentage_error'] == '8.0000'
    assert result['metrics']['median_absolute_percentage_error'] == '8.0000'
    assert result['metrics']['mean_signed_percentage_error'] == '-8.0000'
    assert result['metrics']['observed_comp_span_contains_sale'] == 0
    assert result['status'] == 'synthetic_contract_only'
    assert result['production_ready'] is result['offer_authorized'] is result['quote_authorized'] is False


@pytest.mark.parametrize('mutation', ['county', 'future_features', 'future_comp', 'target_comp', 'same_sale', 'duplicate_property', 'duplicate_case', 'duplicate_sale', 'assessment', 'float', 'boolean', 'nonmarket', 'precontract', 'long_horizon', 'unavailable_label', 'missing_hash', 'extra_target', 'arv_unfinished', 'arv_wrong_scope', 'asis_changed'])
def test_invalid_cohort_cannot_silently_drop_bad_rows_or_receive_grade(mutation):
    data = cohort('after_repair' if mutation.startswith('arv') else 'as_is')
    case = data['cases'][0]
    truth = case['truth']
    if mutation == 'county': case['county_fips'] = '06099'
    if mutation == 'future_features': case['features_observed_on'] = '2026-06-02'
    if mutation == 'future_comp': case['request']['comparables'][0]['available_on'] = '2026-06-02'
    if mutation == 'target_comp': case['request']['comparables'][0]['property_id'] = truth['property_id']
    if mutation == 'same_sale': case['request']['comparables'][0]['sale_id'] = truth['sale_id']
    if mutation in {'duplicate_property', 'duplicate_case', 'duplicate_sale'}:
        other = deepcopy(case)
        if mutation != 'duplicate_case': other['case_id'] = 'case:2'
        if mutation != 'duplicate_property':
            other['request']['subject']['property_id'] = other['truth']['property_id'] = 'subject:2'
        if mutation != 'duplicate_sale': other['truth']['sale_id'] = 'target:2'
        data['cases'].append(other)
    if mutation == 'assessment': truth['kind'] = 'tax_assessment'
    if mutation == 'float': truth['price_cents'] = 50000000.0
    if mutation == 'boolean': truth['price_cents'] = True
    if mutation == 'nonmarket': truth['arms_length'] = False
    if mutation == 'precontract': truth['contract_on'] = '2026-06-01'
    if mutation == 'long_horizon': truth['closed_on'] = truth['available_on'] = '2026-09-01'
    if mutation == 'unavailable_label': truth['available_on'] = '2026-08-02'
    if mutation == 'missing_hash': truth['sale_ref'] = {'source_ref': 'fixture:missing'}
    if mutation == 'extra_target': case['request']['target_price_cents'] = truth['price_cents']
    if mutation == 'arv_unfinished': truth['completed_on'] = '2026-06-21'
    if mutation == 'arv_wrong_scope': truth['renovation_plan_ref'] = 'scope:different'
    if mutation == 'asis_changed': truth['condition_basis'] = 'completed_renovation'
    with pytest.raises((ValueError, KeyError)):
        evaluate(data, '2026-08-01')


def test_arv_separate_from_as_is_and_attestation_is_not_independent_verification():
    data = cohort('after_repair')
    data['dataset_kind'] = 'attested_local_sales'
    result = evaluate(data, '2026-08-01')
    assert set(result['strata']['purpose']) == {'after_repair'}
    assert result['status'] == 'attested_local_evaluation_requires_source_audit'
    assert result['production_ready'] is False


def test_abstentions_remain_in_denominator_and_predictor_does_not_receive_truth():
    data = cohort()
    data['cases'][0]['request']['comparables'] = []
    seen = []
    from backend.valuation.engine import compare_sales
    def predictor(request):
        seen.append(set(request))
        return compare_sales(request)
    result = evaluate(data, '2026-08-01', predictor)
    assert 'truth' not in seen[0]
    assert result['metrics'] == {'eligible_cases': 1, 'predicted_cases': 0, 'abstained_cases': 1, 'statuses': {'needs_data': 1}}


def test_predictor_mutation_is_rejected():
    def predictor(request):
        request['purpose'] = 'wrong'
        return {}
    with pytest.raises(ValueError, match='mutated'):
        evaluate(cohort(), '2026-08-01', predictor)


def test_one_thousand_randomized_prices_use_actual_integer_cent_predictor_and_independent_errors():
    rng = random.Random(606077)
    for i in range(1000):
        data = cohort()
        estimate, truth = rng.randrange(10000000, 150000000), rng.randrange(10000000, 150000000)
        for comp in data['cases'][0]['request']['comparables']:
            comp['sale_price_cents'] = estimate
        data['cases'][0]['truth']['price_cents'] = truth
        result = evaluate(data, '2026-08-01')
        assert result['cases'][0]['estimate_cents'] == estimate
        assert result['metrics']['within_10_percent'] == int(abs(estimate - truth) * 10 <= truth)
        assert result['metrics']['observed_comp_span_contains_sale'] == int(estimate == truth)
        assert result['status'] == 'synthetic_contract_only'


def test_percentiles_empty_and_selective_coverage_are_explicit():
    assert summarize([]) == {'eligible_cases': 0, 'predicted_cases': 0, 'abstained_cases': 0, 'statuses': {}}
    rows = [{'estimate_cents': 100 + i, 'truth_cents': 100, 'status': 'ready_advisory', 'low_cents': 100, 'high_cents': 200} for i in range(10)]
    assert summarize(rows)['p90_absolute_percentage_error'] == '8.0000'


def test_cli_requires_exact_frozen_bytes_and_rejects_invalid_payload(tmp_path):
    path = tmp_path / 'cohort.json'
    path.write_text(json.dumps(cohort()))
    command = [sys.executable, 'scripts/benchmark_san_joaquin.py', str(path), '--evaluated-on', '2026-08-01', '--expected-sha256']
    good = subprocess.run(command + [hashlib.sha256(path.read_bytes()).hexdigest()], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    assert good.returncode == 0
    assert json.loads(good.stdout)['status'] == 'synthetic_contract_only'
    bad = subprocess.run(command + ['0' * 64], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    assert bad.returncode == 2
    assert json.loads(bad.stdout)['status'] == 'invalid_input'
