from copy import deepcopy
from datetime import date, timedelta
import json
import os
from pathlib import Path

import pytest

from backend.valuation.engine import compare_sales
from backend.valuation.local_benchmark import ratio_study
from test_valuation import request


BASELINE = Path(__file__).parent / 'valuation_output_baseline.json'
TRACKED = ('status', 'point_cents', 'supported_low_cents', 'supported_high_cents', 'spread_bps', 'comparable_count', 'purpose', 'range_meaning', 'quote_authorized', 'offer_authorized', 'evidence_verification', 'evidence_verification_meaning', 'verification_counts', 'method', 'schema_version')


def _oversized_line(comp):
    comp['adjustments'].append({'category': 'quality', 'amount_cents': 20000000, 'evidence_ref': 'paired:quality', 'reviewed_by': 'operator:synthetic'})


def _condition_bridge(comp):
    comp['features']['condition'] = 'unrenovated'
    comp['adjustments'].append({'category': 'condition', 'amount_cents': 2000000, 'evidence_ref': 'paired:condition', 'reviewed_by': 'operator:synthetic'})


def _aged(comp):
    comp['closed_on'] = (date.today() - timedelta(days=181)).isoformat()
    comp['contract_on'] = comp['closed_on']


SCENARIOS = {
    'clean_after_repair': ('after_repair', lambda comp: None),
    'clean_as_is': ('as_is', lambda comp: None),
    'oversized_single_line': ('after_repair', _oversized_line),
    'area_divergence': ('after_repair', lambda comp: comp['features'].update(living_area_sqft=2700)),
    'area_boundary_accepted': ('after_repair', lambda comp: comp['features'].update(living_area_sqft=2250)),
    'distance_outside_policy': ('after_repair', lambda comp: comp.update(distance_meters=801)),
    'distance_boundary_accepted': ('after_repair', lambda comp: comp.update(distance_meters=800)),
    'age_outside_policy': ('after_repair', _aged),
    'after_repair_condition_bridge': ('after_repair', _condition_bridge),
    'as_is_condition_bridge': ('as_is', _condition_bridge),
    'unverified_sale': ('after_repair', lambda comp: comp.update(verified=False)),
    'non_arms_length': ('after_repair', lambda comp: comp.update(arms_length=False)),
}


def observed():
    snapshot = {}
    for name, (purpose, mutate) in sorted(SCENARIOS.items()):
        payload = deepcopy(request(purpose))
        mutate(payload['comparables'][0])
        result = compare_sales(payload)
        snapshot[name] = {field: result[field] for field in TRACKED}
        snapshot[name]['rejection_reasons'] = sorted(r['reason'] for r in result['rejected_comparables'])
        snapshot[name]['review_reasons'] = sorted(result['review_reasons'])
        snapshot[name]['adjusted_values'] = sorted(c['adjusted_value_cents'] for c in result['accepted_comparables'])
    snapshot['_ratio_study_oracle'] = ratio_study([
        {'estimate_cents': estimate, 'truth_cents': truth} for estimate, truth in (
            (10000000, 10000000), (10500000, 10000000), (19000000, 20000000),
            (28500000, 30000000), (41000000, 40000000),
        )
    ])
    return snapshot


def test_valuation_outputs_have_not_drifted():
    current = observed()
    if os.environ.get('BOB_REGENERATE_VALUATION_BASELINE') == '1':
        BASELINE.write_text(json.dumps(current, indent=2, sort_keys=True) + '\n')
        pytest.skip('baseline regenerated')
    assert BASELINE.exists(), 'run with BOB_REGENERATE_VALUATION_BASELINE=1 to create the baseline'
    expected = json.loads(BASELINE.read_text())
    drift = []
    for name in sorted(set(expected) | set(current)):
        if name not in expected:
            drift.append(f'{name}: new scenario with no baseline')
        elif name not in current:
            drift.append(f'{name}: scenario removed from the matrix')
        else:
            for field in sorted(set(expected[name]) | set(current[name])):
                before, after = expected[name].get(field), current[name].get(field)
                if before != after:
                    drift.append(f'{name}.{field}: {before!r} -> {after!r}')
    assert not drift, 'valuation output drift detected; review each change and regenerate deliberately:\n' + '\n'.join(drift)


def test_baseline_covers_every_scenario_and_new_gate():
    expected = json.loads(BASELINE.read_text())
    assert set(expected) == set(SCENARIOS) | {'_ratio_study_oracle'}
    reasons = {reason for name, row in expected.items() if name != '_ratio_study_oracle' for reason in row['rejection_reasons']}
    assert {'single_adjustment_exceeds_line_policy', 'living_area_outside_divergence_policy', 'sale_outside_distance_policy', 'sale_outside_age_policy', 'after_repair_requires_renovated_comp_evidence'} <= reasons


def test_no_test_module_mutates_the_global_decimal_context():
    from decimal import DefaultContext, getcontext
    current = getcontext()
    assert current.prec == DefaultContext.prec, (
        f'global Decimal precision is {current.prec}, expected {DefaultContext.prec}. '
        'A module-level getcontext().prec assignment leaks into every other test in the '
        'process and silently changes valuation rounding. Use localcontext() instead.'
    )
    assert current.rounding == DefaultContext.rounding


def test_the_drift_baseline_is_insensitive_to_the_calendar_day():
    from datetime import date, timedelta
    snapshot = observed()
    for name, row in snapshot.items():
        if name == '_ratio_study_oracle':
            continue
        for key, value in row.items():
            assert not isinstance(value, str) or not value.startswith(str(date.today().year) + '-'), (
                f'{name}.{key} embeds a calendar date, which would make this gate fail every day'
            )
    assert (date.today() + timedelta(days=1)).isoformat() not in str(snapshot)
