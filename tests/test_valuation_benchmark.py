from copy import deepcopy
import csv
from decimal import Decimal
import hashlib
import json
import subprocess
import sys

import pytest

from scripts import benchmark_valuation as benchmark
from test_valuation import request


def test_benchmark_grades_are_actual_absolute_errors_with_bias_and_range_coverage():
    cases = [{'sale_price_cents': 10000, 'estimate_cents': 10000 + error, 'low_cents': 9000, 'high_cents': 11000} for error in (500, -1000, 1500, -2000, 2100)]
    result = benchmark.metrics(cases)
    assert result['error_grade_counts'] == {'A': 1, 'B': 1, 'C': 1, 'D': 1, 'F': 1}
    assert result['mean_absolute_percentage_error'] == '14.2000'
    assert result['mean_signed_percentage_error'] == '2.2000'
    assert result['observed_comp_span_contains_sale'] == 5
    assert benchmark.metrics([]) == {'count': 0}


def test_subject_price_and_future_sales_do_not_leak_into_estimate(tmp_path, monkeypatch):
    base = {'Yr Sold': '2009', 'Mo Sold': '6', 'PID': 'comp-1', 'Order': '1', 'SalePrice': '100000', 'Neighborhood': 'fixture-market', 'Bldg Type': '1Fam', 'Sale Condition': 'Normal', 'Sale Type': 'WD ', 'Gr Liv Area': '1800', 'Lot Area': '6000', 'Bedroom AbvGr': '3', 'Full Bath': '2', 'Half Bath': '0', 'Garage Cars': '2', 'Pool Area': '0', 'Overall Qual': '6', 'Overall Cond': '5'}
    rows = [{**base, 'PID': f'comp-{i}', 'Order': str(i), 'Mo Sold': str(5 + i)} for i in range(1, 4)]
    rows += [{**base, 'Yr Sold': '2010', 'Mo Sold': '1', 'PID': 'target', 'Order': '4', 'SalePrice': '200000'}, {**base, 'Yr Sold': '2011', 'PID': 'future', 'Order': '5', 'SalePrice': '90000000'}]
    path = tmp_path / 'synthetic.tsv'
    def write(records):
        with path.open('w') as f:
            writer = csv.DictWriter(f, fieldnames=list(base), delimiter='\t')
            writer.writeheader()
            writer.writerows(records)
        monkeypatch.setattr(benchmark, 'SOURCE_SHA256', hashlib.sha256(path.read_bytes()).hexdigest())
    write(rows)
    first = benchmark.run(path, seeds=2)
    assert first['summaries']['2010']['strict_bob_advisory_prices'] == 0
    assert first['summaries']['2010']['eligible_subjects_common_to_methods'] == 1
    example = first['worst_feature_ranked_examples'][0]
    assert example['estimate_cents'] == 10000000
    assert example['comparable_ids'] == ['ames:1', 'ames:2', 'ames:3']
    changed = deepcopy(rows)
    changed[3]['SalePrice'] = '300000'
    changed[4]['SalePrice'] = '1'
    write(changed)
    second = benchmark.run(path, seeds=2)
    assert second['worst_feature_ranked_examples'][0]['estimate_cents'] == example['estimate_cents']
    assert Decimal(second['summaries']['2010']['feature_ranked']['mean_absolute_percentage_error']) > Decimal(first['summaries']['2010']['feature_ranked']['mean_absolute_percentage_error'])


def test_benchmark_rejects_unexpected_dataset_bytes(tmp_path):
    path = tmp_path / 'changed.tsv'
    path.write_text('unexpected')
    with pytest.raises(ValueError, match='checksum'):
        benchmark.run(path)


def test_candidate_cli_returns_only_review_candidates(tmp_path):
    path = tmp_path / 'candidates.json'
    path.write_text(json.dumps(request('as_is')))
    result = subprocess.run([sys.executable, '-m', 'backend.valuation', str(path), '--rank-candidates'], capture_output=True, text=True)
    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report['status'] == 'candidate_review_only'
    assert 'point_cents' not in report
    assert report['quote_authorized'] is report['offer_authorized'] is False
