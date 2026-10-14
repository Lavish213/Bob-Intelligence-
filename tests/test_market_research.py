from copy import deepcopy
import math
import random

import pytest

from backend.valuation.market_research import CATEGORICAL, FEATURES, NUMERIC, MarketResearchModel, calibration_radius, feature_values, log_to_cents


def synthetic_record(index):
    features = {key: '0' for key in NUMERIC} | {key: 'TA' for key in CATEGORICAL}
    features.update({'Lot Area': str(4000 + index * 3), 'Overall Qual': '6', 'Overall Cond': '5', 'Year Built': '2000', 'Year Remod/Add': '2000', 'Garage Yr Blt': '2000', 'Gr Liv Area': str(1400 + index * 5), 'Full Bath': '2', 'Half Bath': '0', 'Bedroom AbvGr': '3', 'Garage Cars': '2', 'Total Bsmt SF': '900', 'Neighborhood': 'test-area', 'Bldg Type': '1Fam', 'House Style': '1Story', 'Functional': 'Typ'})
    price = (100000 + (1400 + index * 5) * 80 + (4000 + index * 3) * 2) * 100
    return {'property_id': f'synthetic-{index}', 'region': 'test-market', 'closed_on': '2019-01-01', 'available_on': '2019-02-01', 'sale_price_cents': price, 'features': features}


@pytest.mark.parametrize('seed', range(1000))
def test_randomized_feature_contract_excludes_price_identity_transaction_and_protected_inputs(seed):
    rng = random.Random(seed)
    row = synthetic_record(rng.randrange(100))['features']
    saved = deepcopy(row)
    first = feature_values(row)
    row.update({'SalePrice': rng.randrange(1, 10**14), 'PID': f'ignored-{seed}', 'Order': seed, 'Sale Condition': 'Family', 'Sale Type': 'New', 'Yr Sold': '2999', 'crime': seed, 'race': 'ignored', 'seller_asking_price_cents': rng.randrange(10**14)})
    assert feature_values(row) == first
    assert set(first) == set(FEATURES)
    assert all(row[key] == value for key, value in saved.items())
    dollars = rng.randrange(100, 10**9)
    assert abs(log_to_cents(math.log(dollars)) - dollars * 100) <= 1


@pytest.mark.parametrize('value', [True, False, [], {}, float('nan'), float('inf'), 'NaN', 'Infinity', '-1', '10000001', 'invalid'])
def test_bad_physical_features_are_not_silently_imputed(value):
    row = synthetic_record(1)['features']
    row['Gr Liv Area'] = value
    with pytest.raises(ValueError):
        feature_values(row)


@pytest.mark.parametrize('value', ['0', '11', '-1'])
def test_quality_scale_is_validated(value):
    row = synthetic_record(1)['features']
    row['Overall Qual'] = value
    with pytest.raises(ValueError):
        feature_values(row)


def test_exact_calibration_quantile_and_insufficient_support():
    assert calibration_radius(list(range(20))) == 18
    assert calibration_radius(list(range(100))) == 90
    with pytest.raises(ValueError):
        calibration_radius(list(range(19)))
    with pytest.raises(ValueError):
        calibration_radius(list(range(20)), alpha_bps=1)


@pytest.mark.parametrize('value', [True, None, float('nan'), float('inf'), -1, 100])
def test_nonfinite_and_unbounded_model_predictions_are_not_prices(value):
    with pytest.raises(ValueError):
        log_to_cents(value)


@pytest.fixture(scope='module')
def fitted_model():
    pytest.importorskip('catboost')
    pytest.importorskip('lightgbm')
    return MarketResearchModel().fit([synthetic_record(i) for i in range(120)], [synthetic_record(i) for i in range(120, 144)], '2020-01-01', 'test-market')


def test_actual_model_families_calibrate_and_return_integer_research_money(fitted_model):
    row = synthetic_record(70)
    result = fitted_model.predict_research([row], '2020-01-01', 'test-market')[0]
    assert result['status'] == 'research_only'
    assert type(result['research_point_cents']) is int
    assert result['research_low_cents'] <= result['research_point_cents'] <= result['research_high_cents']
    assert result['quote_authorized'] is result['offer_authorized'] is result['production_ready'] is False
    assert len(result['artifact_id']) == 64
    changed = deepcopy(row)
    changed['sale_price_cents'] = 1
    changed['features']['SalePrice'] = '999999999'
    assert fitted_model.predict_research([changed], '2020-01-01', 'test-market') == [result]


@pytest.mark.parametrize('mutation', ['region', 'missing', 'unknown_neighborhood', 'size', 'property_type', 'future_metadata', 'stale'])
def test_actual_model_withholds_unsupported_research_indication(fitted_model, mutation):
    row = synthetic_record(70)
    effective, region = '2020-01-01', 'test-market'
    if mutation == 'region': region = 'stockton-ca'
    if mutation == 'missing': row['features']['Year Built'] = None
    if mutation == 'unknown_neighborhood': row['features']['Neighborhood'] = 'unseen-area'
    if mutation == 'size': row['features']['Gr Liv Area'] = '50000'
    if mutation == 'property_type': row['features']['Bldg Type'] = 'Duplex'
    if mutation == 'future_metadata': row['features']['Year Built'] = '2021'
    if mutation == 'stale': effective = '2022-01-01'
    result = fitted_model.predict_research([row], effective, region)[0]
    assert result['status'] == 'needs_review'
    assert result['research_point_cents'] is result['research_low_cents'] is result['research_high_cents'] is None
    assert result['review_reasons']
    assert result['quote_authorized'] is result['offer_authorized'] is False


@pytest.mark.parametrize('mutation', ['overlap', 'future_available', 'future_closed', 'wrong_region', 'money_float', 'missing_feature', 'wrong_type'])
def test_training_contract_prevents_overlap_future_records_and_bad_money(mutation):
    pytest.importorskip('catboost')
    pytest.importorskip('lightgbm')
    fitting = [synthetic_record(i) for i in range(120)]
    calibration = [synthetic_record(i) for i in range(120, 144)]
    if mutation == 'overlap': calibration[0] = deepcopy(fitting[0])
    if mutation == 'future_available': fitting[0]['available_on'] = '2020-02-01'
    if mutation == 'future_closed': fitting[0]['closed_on'] = '2021-01-01'
    if mutation == 'wrong_region': fitting[0]['region'] = 'other'
    if mutation == 'money_float': fitting[0]['sale_price_cents'] = 100.0
    if mutation == 'missing_feature': fitting[0]['features']['Gr Liv Area'] = None
    if mutation == 'wrong_type': fitting[0]['features']['Bldg Type'] = 'Duplex'
    with pytest.raises(ValueError):
        MarketResearchModel().fit(fitting, calibration, '2020-01-01', 'test-market')


def test_failed_refit_cannot_leave_a_previous_model_active(fitted_model):
    model = deepcopy(fitted_model)
    with pytest.raises(ValueError):
        model.fit([], [], '2020-01-01', 'test-market')
    assert model.models == {} and model.cutoff is None and model.artifact_id is None
    with pytest.raises(ValueError):
        model.predict_research([synthetic_record(70)], '2020-01-01', 'test-market')


def test_unsupported_extreme_record_does_not_break_a_valid_batch(fitted_model):
    valid = synthetic_record(70)
    extreme = deepcopy(valid)
    extreme['features']['Lot Area'] = '10000000'
    reports = fitted_model.predict_research([valid, extreme], '2020-01-01', 'test-market')
    assert reports[0]['research_point_cents'] is not None
    assert reports[1]['research_point_cents'] is None
    assert 'essential_feature_outside_training_support' in reports[1]['review_reasons']
