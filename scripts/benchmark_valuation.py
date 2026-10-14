import argparse
import calendar
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
import csv
import hashlib
import json
from pathlib import Path
import random
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.valuation.candidates import rank_candidates
from backend.valuation.engine import compare_sales, reconcile_indications


SOURCE_URL = 'https://jse.amstat.org/v19n3/decock/AmesHousing.txt'
SOURCE_SHA256 = '6cfe6cb525ba437de428653a1040e2aed7d696640bf75203786a6d7a0e67cfcc'


def amount(value):
    return int(value)


def record(row):
    year, month = amount(row['Yr Sold']), amount(row['Mo Sold'])
    closed = date(year, month, calendar.monthrange(year, month)[1])
    available = closed + timedelta(days=30)
    return {'property_id': row['PID'], 'sale_id': 'ames:' + row['Order'], 'source_ref': 'jse:ames-row-' + row['Order'], 'sale_status': 'closed', 'verified': False, 'arms_length': None, 'sale_price_cents': amount(row['SalePrice']) * 100, 'closed_on': closed.isoformat(), 'available_on': available.isoformat(), 'market_area': row['Neighborhood'], 'property_type': 'single_family', 'features': {'living_area_sqft': amount(row['Gr Liv Area']), 'lot_sqft': amount(row['Lot Area']), 'bedrooms': amount(row['Bedroom AbvGr']), 'bathrooms_half_units': 2 * amount(row['Full Bath']) + amount(row['Half Bath']), 'garage_spaces': amount(row['Garage Cars']), 'pool': amount(row['Pool Area']) > 0, 'quality': 'rating:' + row['Overall Qual'], 'condition': 'rating:' + row['Overall Cond']}, 'year': year, 'month': month}


def numeric_estimate(subject, comps, effective):
    return reconcile_indications([{'adjusted_value_cents': c['sale_price_cents'], 'age_days': (effective - date.fromisoformat(c['closed_on'])).days, 'distance_meters': 0, 'living_area_sqft': c['features']['living_area_sqft']} for c in comps], subject['features']['living_area_sqft'])['point_cents']


def metrics(cases):
    if not cases:
        return {'count': 0}
    absolute = [abs(c['estimate_cents'] - c['sale_price_cents']) for c in cases]
    percentages = [Decimal(e) * 100 / c['sale_price_cents'] for e, c in zip(absolute, cases)]
    bias = [Decimal(c['estimate_cents'] - c['sale_price_cents']) * 100 / c['sale_price_cents'] for c in cases]
    def number(value):
        return str(Decimal(value).quantize(Decimal('0.0001')))
    grades = Counter('A' if p <= 5 else 'B' if p <= 10 else 'C' if p <= 15 else 'D' if p <= 20 else 'F' for p in percentages)
    return {'count': len(cases), 'mean_absolute_error_dollars': number(Decimal(sum(absolute)) / len(cases) / 100), 'median_absolute_percentage_error': number(statistics.median(percentages)), 'mean_absolute_percentage_error': number(sum(percentages) / len(cases)), 'mean_signed_percentage_error': number(sum(bias) / len(cases)), 'within_10_percent': sum(p <= 10 for p in percentages), 'worst_absolute_percentage_error': number(max(percentages)), 'observed_comp_span_contains_sale': sum(c['low_cents'] <= c['sale_price_cents'] <= c['high_cents'] for c in cases), 'error_grade_counts': {g: grades[g] for g in 'ABCDF'}}


def run(input_path, seeds=20):
    raw = Path(input_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('Dataset checksum differs from the audited source')
    rows = list(csv.DictReader(raw.decode('utf-8').splitlines(), delimiter='\t'))
    excluded = Counter()
    records = []
    for row in rows:
        if row['Bldg Type'] != '1Fam':
            excluded['not_detached_single_family'] += 1
        elif row['Sale Condition'] != 'Normal' or row['Sale Type'].strip() not in {'WD', 'CWD', 'VWD'}:
            excluded['not_normal_warranty_deed_sale'] += 1
        else:
            try:
                records.append(record(row))
            except (ValueError, TypeError):
                excluded['missing_or_invalid_numeric_features'] += 1
    summaries = {}
    worst = []
    for year in (2009, 2010):
        random_cases, selected_cases, ready = [], [], 0
        eligible_subjects, target_count, candidate_shortfalls = 0, 0, 0
        for subject in sorted(records, key=lambda r: r['sale_id']):
            if subject['year'] != year:
                continue
            target_count += 1
            effective = date(year, subject['month'], 1)
            pool = [r for r in records if r['property_id'] != subject['property_id'] and r['market_area'] == subject['market_area'] and date.fromisoformat(r['available_on']) <= effective and 0 <= (effective - date.fromisoformat(r['closed_on'])).days <= 365]
            shortlist = rank_candidates(subject, pool, effective.isoformat(), limit=5)
            selected_ids = {r['sale_id'] for r in shortlist['candidates']}
            selected = [r for r in pool if r['sale_id'] in selected_ids]
            strict = compare_sales({'as_of': effective.isoformat(), 'purpose': 'as_is', 'subject': subject, 'comparables': selected}, today=date(2011, 1, 1))
            ready += strict['status'] == 'ready_advisory'
            if len(selected) < 3:
                candidate_shortfalls += 1
                continue
            eligible_subjects += 1
            def scored(comps, estimate, seed=None):
                return {'property_id': subject['property_id'], 'as_of': effective.isoformat(), 'sale_price_cents': subject['sale_price_cents'], 'estimate_cents': estimate, 'low_cents': min(r['sale_price_cents'] for r in comps), 'high_cents': max(r['sale_price_cents'] for r in comps), 'comparable_ids': sorted(r['sale_id'] for r in comps), 'seed': seed}
            selected_cases.append(scored(selected, numeric_estimate(subject, selected, effective)))
            for seed in range(seeds):
                rng = random.Random(str(seed) + ':' + subject['sale_id'])
                chosen = rng.sample(sorted(pool, key=lambda r: r['sale_id']), len(selected))
                random_cases.append(scored(chosen, numeric_estimate(subject, chosen, effective), seed))
        per_seed = {str(seed): metrics([r for r in random_cases if r['seed'] == seed]) for seed in range(seeds)}
        summaries[str(year)] = {'target_count': target_count, 'eligible_subjects_common_to_methods': eligible_subjects, 'candidate_shortfalls': candidate_shortfalls, 'strict_bob_advisory_prices': ready, 'random_same_neighborhood': metrics(random_cases), 'feature_ranked': metrics(selected_cases), 'random_per_seed': per_seed}
        worst.extend(sorted(selected_cases, key=lambda r: Decimal(abs(r['estimate_cents'] - r['sale_price_cents'])) / r['sale_price_cents'], reverse=True)[:5])
    return {'schema_version': '1.0', 'dataset': {'source_url': SOURCE_URL, 'sha256': SOURCE_SHA256, 'rows': len(rows), 'retained': len(records), 'exclusions': dict(excluded)}, 'scope': 'offline_as_is_numerical_diagnostic_not_production_appraisal_or_arv_backtest', 'error_grade_policy': 'Project diagnostic only: A <=5%, B <=10%, C <=15%, D <=20%, F >20% absolute sale-price error', 'assumptions': ['Month-only sales assigned month-end; targets scored at start of their sale month', 'Assumed publication lag of 30 days; historical publication times are not known', 'Subject sale price is hidden from candidate ranking and numerical estimation, then revealed for scoring', 'No subject sale, same-month sale, or later sale used as a comp', 'Same neighborhood, prior 365 days, no demographic variables', 'Geographic distance unavailable and omitted from numerical weights', 'No market-time, concession, condition, or other dollar adjustments invented', 'No source verification, inspection, or comparison review attested; strict Bob withholds all prices', '2009 is development diagnostic; ranking frozen before 2010 evaluation', 'Both methods scored on identical subjects with equal comp counts; random method repeated across fixed seeds', 'Historical dataset retains only latest sale per parcel and is not an as-of records archive', 'Observed comp-price span is not a calibrated confidence interval', 'Single old Iowa market does not establish current California or after-repair accuracy'], 'summaries': summaries, 'worst_feature_ranked_examples': worst, 'quote_authorized': False, 'offer_authorized': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('dataset')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(run(args.dataset), indent=2) + '\n')


if __name__ == '__main__':
    main()
