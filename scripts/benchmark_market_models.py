import argparse
import calendar
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
import csv
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.valuation.market_research import FEATURES, MODEL_NAMES, MarketResearchModel, log_to_cents
from backend.valuation.candidates import rank_candidates
from benchmark_valuation import SOURCE_SHA256, SOURCE_URL, metrics, numeric_estimate, record


def load_records(path):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('Source checksum differs from the audited dataset')
    records, excluded = [], Counter()
    rows = list(csv.DictReader(raw.decode().splitlines(), delimiter='\t'))
    for row in rows:
        if row['Bldg Type'] != '1Fam' or row['Sale Condition'] != 'Normal' or row['Sale Type'].strip() not in {'WD', 'CWD', 'VWD'}:
            excluded['outside_prespecified_property_or_transaction_scope'] += 1
            continue
        year, month = int(row['Yr Sold']), int(row['Mo Sold'])
        closed = date(year, month, calendar.monthrange(year, month)[1])
        if any(row[k] not in ('', 'NA') and int(row[k]) > year for k in ('Year Built', 'Year Remod/Add', 'Garage Yr Blt')):
            excluded['inconsistent_future_construction_metadata'] += 1
            continue
        records.append({'property_id': row['PID'], 'region': 'ames-iowa', 'closed_on': closed.isoformat(), 'available_on': (closed + timedelta(days=30)).isoformat(), 'sale_price_cents': int(row['SalePrice']) * 100, 'features': {k: row[k] for k in FEATURES}, 'year': year, 'source_ref': 'jse:row-' + row['Order']})
    return records, {'rows': len(rows), 'retained': len(records), 'exclusions': dict(excluded), 'source_url': SOURCE_URL, 'sha256': SOURCE_SHA256}


def scored(row, prices, model, name):
    point = prices[name]
    radius = model.radii[name]
    return {'property_id': row['property_id'], 'source_ref': row['source_ref'], 'sale_price_cents': row['sale_price_cents'], 'estimate_cents': point, 'low_cents': log_to_cents(math.log(point / 100) - radius), 'high_cents': log_to_cents(math.log(point / 100) + radius), 'neighborhood': row['features']['Neighborhood'], 'quality': row['features']['Overall Qual']}


def model_metrics(cases):
    result = metrics(cases)
    result['calibrated_residual_band_contains_sale'] = result.pop('observed_comp_span_contains_sale', 0)
    result['residual_band_empirical_coverage_percent'] = str((Decimal(result['calibrated_residual_band_contains_sale']) * 100 / len(cases)).quantize(Decimal('0.0001'))) if cases else None
    return result


def run(path, seed=3342):
    records, dataset = load_records(path)
    original_rows = list(csv.DictReader(Path(path).read_text().splitlines(), delimiter='\t'))
    original_records = [record(row) for row in original_rows if row['Bldg Type'] == '1Fam' and row['Sale Condition'] == 'Normal' and row['Sale Type'].strip() in {'WD', 'CWD', 'VWD'}]
    original_by_id = {row['property_id']: row for row in original_records}
    folds = {}
    all_cases = {name: [] for name in MODEL_NAMES}
    failures = []
    guards = Counter()
    started = time.monotonic()
    for year in (2008, 2009, 2010):
        cutoff = date(year, 1, 1)
        eligible = sorted([r for r in records if date.fromisoformat(r['available_on']) <= cutoff], key=lambda r: (r['available_on'], r['property_id']))
        split = len(eligible) * 85 // 100
        fitting, calibration = eligible[:split], eligible[split:]
        targets = sorted([r for r in records if r['year'] == year], key=lambda r: r['property_id'])
        if set(r['property_id'] for r in eligible) & set(r['property_id'] for r in targets):
            raise ValueError('Target parcel leaked into training')
        model = MarketResearchModel(seed).fit(fitting, calibration, cutoff.isoformat(), 'ames-iowa')
        prices = model.numerical_predictions(targets)
        fold = {'cutoff': cutoff.isoformat(), 'fitting_rows': len(fitting), 'calibration_rows': len(calibration), 'target_rows': len(targets), 'artifact_id': model.artifact_id, 'models': {}, 'model_comparison_policy': 'fixed_parameters_equal_log_weight_ensemble_no_target_year_tuning'}
        importances = model.models['catboost'].get_feature_importance()
        fold['catboost_top_feature_importance'] = [{'feature': FEATURES[i], 'importance_percent': str(Decimal(str(importances[i])).quantize(Decimal('0.0001')))} for i in sorted(range(len(FEATURES)), key=lambda i: importances[i], reverse=True)[:15]]
        for name in MODEL_NAMES:
            cases = [scored(row, price, model, name) for row, price in zip(targets, prices)]
            fold['models'][name] = model_metrics(cases)
            all_cases[name].extend(cases)
            if name == 'ensemble':
                failures.extend(sorted(cases, key=lambda r: Decimal(abs(r['estimate_cents'] - r['sale_price_cents'])) / r['sale_price_cents'], reverse=True)[:5])
                fold['quality_segments'] = {quality: model_metrics([c for c in cases if c['quality'] == quality]) for quality in sorted(set(c['quality'] for c in cases))}
        for report in model.predict_research(targets, cutoff.isoformat(), 'ames-iowa'):
            guards.update(report['review_reasons'])
        paired_legacy, paired_new = [], []
        for row, price in zip(targets, prices):
            subject = original_by_id[row['property_id']]
            effective = date(year, subject['month'], 1)
            pool = [r for r in original_records if r['property_id'] != subject['property_id'] and r['market_area'] == subject['market_area'] and date.fromisoformat(r['available_on']) <= effective and 0 <= (effective - date.fromisoformat(r['closed_on'])).days <= 365]
            shortlist = rank_candidates(subject, pool, effective.isoformat())
            selected_ids = {r['sale_id'] for r in shortlist['candidates']}
            selected = [r for r in pool if r['sale_id'] in selected_ids]
            if len(selected) >= 3:
                paired_legacy.append({'sale_price_cents': row['sale_price_cents'], 'estimate_cents': numeric_estimate(subject, selected, effective), 'low_cents': min(c['sale_price_cents'] for c in selected), 'high_cents': max(c['sale_price_cents'] for c in selected)})
                paired_new.append(scored(row, price, model, 'ensemble'))
        fold['identical_target_comparison'] = {'old_unadjusted_shortlist': metrics(paired_legacy), 'new_research_ensemble': model_metrics(paired_new)}
        folds[str(year)] = fold
    total = len(all_cases['ensemble'])
    return {'schema_version': '1.0', 'dataset': dataset, 'scope': 'retrospective_as_is_research_model_comparison_not_current_market_or_arv_validation', 'distinct_out_of_fitting_and_calibration_sale_targets': total, 'model_sale_comparisons': total * len(MODEL_NAMES), 'folds': folds, 'aggregate': {name: model_metrics(cases) for name, cases in all_cases.items()}, 'review_guard_counts': dict(guards), 'worst_ensemble_examples': failures, 'features': list(FEATURES), 'dependencies': {name: importlib.metadata.version(name) for name in ('numpy', 'pandas', 'scikit-learn', 'catboost', 'lightgbm', 'scipy')}, 'seed': seed, 'elapsed_seconds': str(Decimal(str(time.monotonic() - started)).quantize(Decimal('0.01'))), 'limitations': ['Original assessor dataset is retrospective and retains only latest sale per parcel; as-of characteristic versions and publication times are unknown', 'Month-end closing and 30-day availability lag are assumptions, not historical source attestations', '2010 was previously examined in the earlier benchmark; this is a repeat benchmark, not a newly sealed independent test', 'Every target parcel and label is excluded from fitting and calibration for its year; preprocessing fits only fitting records', 'Fixed model settings and equal log ensemble weights; no test-year early stopping or target-price-based comp selection', 'Calibration uses a disjoint most recent 15% of earlier records and the finite-sample 90% residual quantile; temporal exchangeability is not established', 'Empirical band coverage is measured honestly and may miss its nominal 90%; no guaranteed coverage claim', 'Numeric evaluations retain all target failures, including predictions withheld by research review guards', 'No sale-price-driven target exclusions, no protected-class or crime inputs, and no seller asking-price predictor', 'Floating point is confined to model fitting and log prediction; monetary outputs are bounded integer cents', 'Research reports cannot become ready_advisory, grant offers or quote prices; no automatic Sophia integration', 'Current California valuation, live data freshness, independent source verification and completed-renovation ARV accuracy remain untested'], 'quote_authorized': False, 'offer_authorized': False, 'production_ready': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('dataset')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(run(args.dataset), indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
