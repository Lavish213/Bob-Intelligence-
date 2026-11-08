import csv
import hashlib
import importlib.util
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from backend.valuation.local_benchmark import evaluate

SPEC = importlib.util.spec_from_file_location('cohort_builder', Path(__file__).resolve().parents[1] / 'scripts' / 'build_san_joaquin_cohort.py')
builder = importlib.util.module_from_spec(SPEC)
sys.modules['cohort_builder'] = builder
SPEC.loader.exec_module(builder)

FEATMAP = {'living_area_sqft': 'living_area', 'bedrooms': 'bedrooms', 'bathrooms_half_units': 'bathrooms',
           'lot_sqft': 'lot', 'garage_spaces': 'garage', 'pool': 'pool', 'condition': 'condition', 'quality': 'quality'}


def row(index, **changes):
    closed = date(2026, 1, 5) + timedelta(days=index * 3)
    contract = closed - timedelta(days=30)
    value = {
        'sale_id': f'h-{index:04d}', 'apn': f'1{index:02d}-{index:03d}-01',
        'address': f'{200 + index} Test Way', 'city': 'Stockton',
        'latitude': f'{37.9577 + index * 0.00002:.6f}', 'longitude': f'{-121.2908 + index * 0.00002:.6f}',
        'market_area': 'stockton-central', 'property_type': 'single_family',
        'closed_on': closed.isoformat(), 'contract_on': contract.isoformat(),
        'available_on': (closed + timedelta(days=2)).isoformat(),
        'sale_price': '320000.00', 'arms_length': 'true',
        'condition_basis': 'unchanged_as_is', 'condition_ref': f'assessor:cond-{index}',
        'condition_sha256': hashlib.sha256(f'c{index}'.encode()).hexdigest(),
        'renovation_plan_ref': '', 'completed_on': '',
        'features_observed_on': (contract - timedelta(days=30)).isoformat(),
        'source_ref': f'sjcounty:rec-{index}', 'source_sha256': hashlib.sha256(f's{index}'.encode()).hexdigest(),
        'living_area_sqft': '1800', 'bedrooms': '3', 'bathrooms_half_units': '4',
        'lot_sqft': '6000', 'garage_spaces': '2', 'pool': 'false', 'condition': 'average', 'quality': 'standard',
    }
    value.update(changes)
    return value


def write_csv(tmp_path, rows):
    path = tmp_path / 'sales.csv'
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def run(tmp_path, rows, **flags):
    source = write_csv(tmp_path, rows)
    out, queue, rejects = tmp_path / 'c.json', tmp_path / 'q.json', tmp_path / 'r.json'
    argv = [str(source), '--out', str(out), '--review-queue', str(queue), '--rejects', str(rejects),
            '--evaluated-on', '2026-11-08', '--cohort-ref', 'sjcounty:test',
            '--rights-ref', 'contract:test', '--selection-ref', 'policy:test']
    for key, value in flags.items():
        argv += ['--' + key.replace('_', '-'), str(value)]
    builder.main(argv)
    return json.loads(out.read_text()), json.loads(queue.read_text()), json.loads(rejects.read_text())


def fill(cohort):
    for case in cohort['cases']:
        subject = case['request']['subject']
        for comparable in case['request']['comparables']:
            needed = {'market_time', 'concessions'}
            needed.update(category for feature, category in FEATMAP.items() if subject['features'][feature] != comparable['features'][feature])
            if subject['market_area'] != comparable['market_area']:
                needed.add('location')
            comparable['comparison_review_ref'] = 'review:test'
            comparable['adjustments'] = [{'category': name, 'amount_cents': 0, 'evidence_ref': 'test:zero', 'reviewed_by': 'test:reviewer'} for name in sorted(needed)]
    return cohort


class TestNoLeakage:
    def test_no_comparable_closes_or_becomes_available_after_the_prediction_date(self, tmp_path):
        cohort, _, _ = run(tmp_path, [row(i) for i in range(40)])
        assert cohort['cases']
        for case in cohort['cases']:
            as_of = date.fromisoformat(case['request']['as_of'])
            for comparable in case['request']['comparables']:
                assert date.fromisoformat(comparable['closed_on']) <= as_of
                assert date.fromisoformat(comparable['available_on']) <= as_of

    def test_the_prediction_precedes_the_target_contract(self, tmp_path):
        cohort, _, _ = run(tmp_path, [row(i) for i in range(40)])
        for case in cohort['cases']:
            assert date.fromisoformat(case['request']['as_of']) < date.fromisoformat(case['truth']['contract_on'])

    def test_the_target_sale_is_never_its_own_comparable(self, tmp_path):
        cohort, _, _ = run(tmp_path, [row(i) for i in range(40)])
        for case in cohort['cases']:
            identifiers = {comparable['sale_id'] for comparable in case['request']['comparables']}
            parcels = {comparable['property_id'] for comparable in case['request']['comparables']}
            assert case['truth']['sale_id'] not in identifiers
            assert case['request']['subject']['property_id'] not in parcels

    def test_a_repeat_parcel_is_dropped_rather_than_inflating_the_cohort(self, tmp_path):
        rows = [row(i) for i in range(40)]
        rows.append(row(99, apn=rows[20]['apn'], sale_id='repeat-1'))
        _, _, rejects = run(tmp_path, rows)
        assert any(entry['reason'] == 'repeat_parcel_would_inflate_the_cohort' for entry in rejects)

    def test_every_case_target_and_subject_is_unique(self, tmp_path):
        cohort, _, _ = run(tmp_path, [row(i) for i in range(40)])
        subjects = [case['request']['subject']['property_id'] for case in cohort['cases']]
        sales = [case['truth']['sale_id'] for case in cohort['cases']]
        assert len(subjects) == len(set(subjects))
        assert len(sales) == len(set(sales))


class TestRowRejection:
    @pytest.mark.parametrize('changes,reason', [
        ({'sale_price': 'not-a-number'}, 'sale_price_not_a_number'),
        ({'sale_price': '320000.005'}, 'sale_price_not_whole_cents_or_out_of_range'),
        ({'sale_price': '0'}, 'sale_price_not_whole_cents_or_out_of_range'),
        ({'arms_length': 'false'}, 'not_an_arms_length_sale'),
        ({'arms_length': 'maybe'}, 'arms_length_not_a_boolean'),
        ({'condition_basis': 'looks_fine'}, 'condition_basis_must_be_unchanged_as_is_or_completed_renovation'),
        ({'renovation_plan_ref': 'scope:1'}, 'as_is_sale_carries_renovation_evidence'),
        ({'property_type': 'castle'}, 'unsupported_property_type'),
        ({'source_sha256': 'short'}, 'source_sha256_not_a_digest'),
        ({'condition_sha256': 'zzzz'}, 'condition_sha256_not_a_digest'),
        ({'closed_on': 'not-a-date'}, 'closed_on_not_an_iso_date'),
        ({'living_area_sqft': '0'}, 'living_area_sqft_below_minimum'),
        ({'living_area_sqft': 'big'}, 'living_area_sqft_not_an_integer'),
        ({'latitude': '999'}, 'latitude_outside_valid_range'),
        ({'city': ''}, 'city_missing'),
    ])
    def test_a_malformed_row_is_rejected_with_a_named_reason(self, tmp_path, changes, reason):
        rows = [row(i) for i in range(10)] + [row(50, **changes)]
        _, _, rejects = run(tmp_path, rows)
        assert any(entry['reason'] == reason for entry in rejects), [entry['reason'] for entry in rejects]

    def test_a_duplicate_sale_id_is_rejected(self, tmp_path):
        rows = [row(i) for i in range(10)]
        rows.append(row(60, sale_id=rows[0]['sale_id']))
        _, _, rejects = run(tmp_path, rows)
        assert any(entry['reason'] == 'duplicate_sale_id' for entry in rejects)

    def test_a_missing_column_is_reported_rather_than_defaulted(self, tmp_path):
        rows = [row(i) for i in range(5)]
        for entry in rows:
            del entry['condition_sha256']
        _, _, rejects = run(tmp_path, rows)
        assert all('missing_columns' in entry['reason'] for entry in rejects)

    def test_a_case_without_enough_leak_free_comparables_is_dropped(self, tmp_path):
        _, _, rejects = run(tmp_path, [row(i) for i in range(6)])
        assert any('leak_free_comparables_found' in entry['reason'] for entry in rejects)


class TestOutputIsAcceptedByTheBenchmark:
    def test_a_filled_cohort_passes_the_benchmark_validator(self, tmp_path):
        cohort, _, _ = run(tmp_path, [row(i) for i in range(40)])
        report = evaluate(fill(cohort), '2026-11-08')
        assert report['metrics']['eligible_cases'] == len(cohort['cases'])
        assert report['production_ready'] is False

    def test_a_homogeneous_cohort_produces_a_ratio_study(self, tmp_path):
        rows = [row(i, sale_price=f'{320000 + (i % 7) * 900}.00') for i in range(40)]
        cohort, _, _ = run(tmp_path, rows)
        report = evaluate(fill(cohort), '2026-11-08')
        study = report['metrics'].get('ratio_study')
        assert study is not None
        assert study['ratio_cases'] == report['metrics']['predicted_cases']
        assert float(study['coefficient_of_dispersion']) >= 0

    def test_the_skeleton_scores_nothing_until_a_reviewer_supplies_adjustments(self, tmp_path):
        cohort, queue, _ = run(tmp_path, [row(i) for i in range(40)])
        assert queue['adjustments_required']
        assert all(comparable['comparison_review_ref'] == 'REVIEW_REQUIRED' for case in cohort['cases'] for comparable in case['request']['comparables'])
        report = evaluate(cohort, '2026-11-08')
        assert report['metrics']['predicted_cases'] == 0
        assert report['metrics']['abstained_cases'] == report['metrics']['eligible_cases']
        assert report['metrics'].get('ratio_study') is None

    def test_review_turns_an_abstaining_skeleton_into_a_scored_cohort(self, tmp_path):
        rows = [row(i, sale_price=f'{320000 + (i % 7) * 900}.00') for i in range(40)]
        cohort, _, _ = run(tmp_path, rows)
        before = evaluate(json.loads(json.dumps(cohort)), '2026-11-08')['metrics']
        after = evaluate(fill(cohort), '2026-11-08')['metrics']
        assert before['predicted_cases'] == 0
        assert after['predicted_cases'] > 0
        assert after['ratio_study'] is not None

    def test_the_review_queue_names_every_required_adjustment_category(self, tmp_path):
        cohort, queue, _ = run(tmp_path, [row(i, lot_sqft='7000' if i % 2 else '6000') for i in range(40)])
        by_pair = {(entry['case_id'], entry['comparable_sale_id']): entry['required_adjustment_categories'] for entry in queue['adjustments_required']}
        for case in cohort['cases']:
            subject = case['request']['subject']
            for comparable in case['request']['comparables']:
                expected = {'market_time', 'concessions'}
                expected.update(category for feature, category in FEATMAP.items() if subject['features'][feature] != comparable['features'][feature])
                assert set(by_pair[(case['case_id'], comparable['sale_id'])]) == expected


class TestDeterminismAndProvenance:
    def test_two_runs_over_the_same_export_are_byte_identical(self, tmp_path):
        rows = [row(i) for i in range(30)]
        first, _, _ = run(tmp_path / 'a', rows) if (tmp_path / 'a').mkdir() or True else (None, None, None)
        second, _, _ = run(tmp_path / 'b', rows) if (tmp_path / 'b').mkdir() or True else (None, None, None)
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)

    def test_the_cohort_digest_covers_the_source_export(self, tmp_path):
        rows = [row(i) for i in range(20)]
        source = write_csv(tmp_path, rows)
        cohort, _, _ = run(tmp_path, rows)
        assert cohort['cohort_ref']['sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()

    def test_condition_evidence_is_carried_as_a_reference_with_its_own_digest(self, tmp_path):
        cohort, _, _ = run(tmp_path, [row(i) for i in range(20)])
        for case in cohort['cases']:
            assert set(case['truth']['condition_ref']) == {'source_ref', 'sha256'}
            assert len(case['truth']['condition_ref']['sha256']) == 64

    def test_money_crosses_the_boundary_as_integer_cents(self, tmp_path):
        cohort, _, _ = run(tmp_path, [row(i, sale_price='319999.99') for i in range(20)])
        for case in cohort['cases']:
            assert case['truth']['price_cents'] == 31999999
            assert all(isinstance(comparable['sale_price_cents'], int) for comparable in case['request']['comparables'])
