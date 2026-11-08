import argparse
import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.valuation.engine import CATEGORIES, FEATURES, PROPERTY_TYPES

COUNTY_FIPS = '06077'
SALE_COLUMNS = (
    'sale_id', 'apn', 'address', 'city', 'latitude', 'longitude', 'market_area', 'property_type',
    'closed_on', 'contract_on', 'available_on', 'sale_price', 'arms_length',
    'condition_basis', 'condition_ref', 'condition_sha256', 'renovation_plan_ref', 'completed_on',
    'features_observed_on', 'source_ref', 'source_sha256',
) + tuple(FEATURES)
BOOLEAN = {'true': True, 'false': False, '1': True, '0': False, 'yes': True, 'no': False, 't': True, 'f': False}
INTEGER_FEATURES = ('living_area_sqft', 'bedrooms', 'bathrooms_half_units', 'lot_sqft', 'garage_spaces')
REQUIRED_ALWAYS = ('market_time', 'concessions')


class RowRejected(Exception):
    pass


def cents(value):
    try:
        amount = Decimal(str(value).replace('$', '').replace(',', '').strip())
    except (InvalidOperation, AttributeError):
        raise RowRejected('sale_price_not_a_number')
    scaled = amount * 100
    if scaled != scaled.to_integral_value() or scaled <= 0 or scaled > 10**14:
        raise RowRejected('sale_price_not_whole_cents_or_out_of_range')
    return int(scaled)


def iso_date(value, field):
    try:
        parsed = date.fromisoformat((value or '').strip())
    except (ValueError, AttributeError):
        raise RowRejected(f'{field}_not_an_iso_date')
    return parsed


def boolean(value, field):
    key = (value or '').strip().lower()
    if key not in BOOLEAN:
        raise RowRejected(f'{field}_not_a_boolean')
    return BOOLEAN[key]


def whole(value, field, minimum=0):
    text = (value or '').strip()
    if not text.lstrip('-').isdigit():
        raise RowRejected(f'{field}_not_an_integer')
    number = int(text)
    if number < minimum:
        raise RowRejected(f'{field}_below_minimum')
    return number


def coordinate(value, field, limit):
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        raise RowRejected(f'{field}_not_a_coordinate')
    if not -limit <= number <= limit:
        raise RowRejected(f'{field}_outside_valid_range')
    return number


def text(value, field, maximum=300):
    stripped = (value or '').strip()
    if not 0 < len(stripped) <= maximum:
        raise RowRejected(f'{field}_missing')
    return stripped


def metres_between(first, second):
    radius = 6371008.8
    lat1, lat2 = math.radians(first[0]), math.radians(second[0])
    dlat, dlon = lat2 - lat1, math.radians(second[1] - first[1])
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return int(round(2 * radius * math.asin(min(1.0, math.sqrt(a)))))


def parse_sale(row):
    missing = [column for column in SALE_COLUMNS if column not in row]
    if missing:
        raise RowRejected('missing_columns:' + ','.join(sorted(missing)))
    sale = {
        'sale_id': text(row['sale_id'], 'sale_id'),
        'apn': text(row['apn'], 'apn', 30),
        'address': text(row['address'], 'address'),
        'city': text(row['city'], 'city', 100),
        'market_area': text(row['market_area'], 'market_area'),
        'source_ref': text(row['source_ref'], 'source_ref'),
        'source_sha256': text(row['source_sha256'], 'source_sha256', 64),
        'latitude': coordinate(row['latitude'], 'latitude', 90),
        'longitude': coordinate(row['longitude'], 'longitude', 180),
        'sale_price_cents': cents(row['sale_price']),
        'arms_length': boolean(row['arms_length'], 'arms_length'),
        'closed_on': iso_date(row['closed_on'], 'closed_on'),
        'contract_on': iso_date(row['contract_on'], 'contract_on'),
        'available_on': iso_date(row['available_on'], 'available_on'),
        'features_observed_on': iso_date(row['features_observed_on'], 'features_observed_on'),
        'condition_basis': text(row['condition_basis'], 'condition_basis', 40),
        'condition_ref': text(row['condition_ref'], 'condition_ref'),
        'condition_sha256': text(row['condition_sha256'], 'condition_sha256', 64),
        'property_type': text(row['property_type'], 'property_type', 40),
    }
    for field in ('source_sha256', 'condition_sha256'):
        digest_value = sale[field]
        if len(digest_value) != 64 or any(character not in '0123456789abcdef' for character in digest_value.lower()):
            raise RowRejected(f'{field}_not_a_digest')
    if sale['property_type'] not in PROPERTY_TYPES:
        raise RowRejected('unsupported_property_type')
    if sale['condition_basis'] not in {'unchanged_as_is', 'completed_renovation'}:
        raise RowRejected('condition_basis_must_be_unchanged_as_is_or_completed_renovation')
    if not sale['arms_length']:
        raise RowRejected('not_an_arms_length_sale')
    if not sale['contract_on'] <= sale['closed_on'] <= sale['available_on']:
        raise RowRejected('inconsistent_sale_chronology')
    if sale['condition_basis'] == 'completed_renovation':
        sale['renovation_plan_ref'] = text(row['renovation_plan_ref'], 'renovation_plan_ref')
        sale['completed_on'] = iso_date(row['completed_on'], 'completed_on')
        if not sale['completed_on'] <= sale['contract_on']:
            raise RowRejected('renovation_completed_after_contract')
    else:
        if (row['renovation_plan_ref'] or '').strip() or (row['completed_on'] or '').strip():
            raise RowRejected('as_is_sale_carries_renovation_evidence')
        sale['renovation_plan_ref'] = None
        sale['completed_on'] = None
    features = {}
    for name in FEATURES:
        if name in INTEGER_FEATURES:
            features[name] = whole(row[name], name, 1 if name == 'living_area_sqft' else 0)
        elif name == 'pool':
            features[name] = boolean(row[name], name)
        else:
            features[name] = text(row[name], name, 40)
    sale['features'] = features
    return sale


def eligible_comparables(target, sales, as_of, max_age_days, max_distance_meters, max_area_divergence_bps, limit):
    subject_area = target['features']['living_area_sqft']
    candidates = []
    for other in sales:
        if other['apn'] == target['apn'] or other['sale_id'] == target['sale_id']:
            continue
        if other['available_on'] > as_of:
            continue
        age = (as_of - other['closed_on']).days
        if not 0 <= age <= max_age_days:
            continue
        if other['property_type'] != target['property_type']:
            continue
        distance = metres_between((target['latitude'], target['longitude']), (other['latitude'], other['longitude']))
        if distance > max_distance_meters:
            continue
        divergence = abs(other['features']['living_area_sqft'] - subject_area) * 10000 // subject_area
        if divergence > max_area_divergence_bps:
            continue
        candidates.append((divergence, age, distance, other['sale_id'], other, distance, age))
    candidates.sort(key=lambda row: (row[0], row[1], row[2], row[3]))
    return [(row[4], row[5], row[6]) for row in candidates[:limit]]


def required_categories(target, comparable):
    needed = set(REQUIRED_ALWAYS)
    needed.update(category for feature, category in FEATURES.items() if target['features'][feature] != comparable['features'][feature])
    if target['market_area'] != comparable['market_area']:
        needed.add('location')
    return sorted(needed & CATEGORIES)


def build(sales, evaluated_on, purpose, lead_days, max_age_days, max_distance_meters, max_area_divergence_bps, min_comparables, max_comparables):
    cases, review_queue, rejected = [], [], []
    by_apn = defaultdict(list)
    for sale in sales:
        by_apn[sale['apn']].append(sale)
    for target in sorted(sales, key=lambda row: (row['closed_on'], row['sale_id'])):
        if purpose == 'after_repair' and target['condition_basis'] != 'completed_renovation':
            rejected.append({'sale_id': target['sale_id'], 'reason': 'after_repair_cohort_needs_a_completed_renovation_outcome'})
            continue
        if purpose == 'as_is' and target['condition_basis'] != 'unchanged_as_is':
            rejected.append({'sale_id': target['sale_id'], 'reason': 'as_is_cohort_needs_an_unchanged_outcome'})
            continue
        as_of = target['contract_on'] - timedelta(days=lead_days)
        if target['features_observed_on'] > as_of:
            rejected.append({'sale_id': target['sale_id'], 'reason': 'subject_features_not_observable_before_prediction'})
            continue
        if (target['closed_on'] - as_of).days > 90:
            rejected.append({'sale_id': target['sale_id'], 'reason': 'target_does_not_close_within_90_days_of_prediction'})
            continue
        if target['available_on'] > evaluated_on:
            rejected.append({'sale_id': target['sale_id'], 'reason': 'outcome_not_yet_available_on_the_evaluation_date'})
            continue
        if len(by_apn[target['apn']]) > 1:
            rejected.append({'sale_id': target['sale_id'], 'reason': 'repeat_parcel_would_inflate_the_cohort'})
            continue
        chosen = eligible_comparables(target, sales, as_of, max_age_days, max_distance_meters, max_area_divergence_bps, max_comparables)
        if len(chosen) < min_comparables:
            rejected.append({'sale_id': target['sale_id'], 'reason': f'only_{len(chosen)}_leak_free_comparables_found'})
            continue
        comparables = []
        for comparable, distance, age in chosen:
            needed = required_categories(target, comparable)
            comparables.append({
                'property_id': 'apn:' + comparable['apn'], 'sale_id': comparable['sale_id'],
                'sale_status': 'closed', 'verified': True, 'arms_length': True,
                'source_ref': comparable['source_ref'], 'comparison_review_ref': 'REVIEW_REQUIRED',
                'sale_price_cents': comparable['sale_price_cents'],
                'closed_on': comparable['closed_on'].isoformat(), 'contract_on': comparable['contract_on'].isoformat(),
                'available_on': comparable['available_on'].isoformat(),
                'market_area': comparable['market_area'], 'property_type': comparable['property_type'],
                'distance_meters': distance, 'features': dict(comparable['features']), 'adjustments': [],
            })
            review_queue.append({
                'case_id': 'case:' + target['sale_id'], 'comparable_sale_id': comparable['sale_id'],
                'required_adjustment_categories': needed, 'distance_meters': distance, 'age_days': age,
                'sale_price_cents': comparable['sale_price_cents'],
            })
        request = {
            'as_of': as_of.isoformat(), 'purpose': purpose,
            'subject': {'property_id': 'apn:' + target['apn'], 'market_area': target['market_area'],
                        'property_type': target['property_type'], 'features': dict(target['features'])},
            'comparables': comparables,
        }
        if purpose == 'after_repair':
            request['renovation_plan_ref'] = target['renovation_plan_ref']
        cases.append({
            'case_id': 'case:' + target['sale_id'], 'city': target['city'], 'county_fips': COUNTY_FIPS,
            'geography_ref': {'source_ref': target['source_ref'], 'sha256': target['source_sha256']},
            'features_observed_on': target['features_observed_on'].isoformat(),
            'request': request,
            'truth': {
                'property_id': 'apn:' + target['apn'], 'sale_id': target['sale_id'], 'kind': 'closed_sale',
                'price_cents': target['sale_price_cents'], 'contract_on': target['contract_on'].isoformat(),
                'closed_on': target['closed_on'].isoformat(), 'available_on': target['available_on'].isoformat(),
                'arms_length': True, 'sale_ref': {'source_ref': target['source_ref'], 'sha256': target['source_sha256']},
                'condition_basis': target['condition_basis'],
                'condition_ref': {'source_ref': target['condition_ref'], 'sha256': target['condition_sha256']},
                'renovation_plan_ref': target['renovation_plan_ref'],
                'completed_on': target['completed_on'].isoformat() if target['completed_on'] else None,
            },
        })
    return cases, review_queue, rejected


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build a leak-free San Joaquin benchmark cohort skeleton from a closed-sale export. Emits a review queue of the adjustments a human must still supply; it never invents an adjustment, a condition or a price.')
    parser.add_argument('sales_csv', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--review-queue', required=True, type=Path)
    parser.add_argument('--rejects', required=True, type=Path)
    parser.add_argument('--evaluated-on', required=True)
    parser.add_argument('--cohort-ref', required=True)
    parser.add_argument('--rights-ref', required=True)
    parser.add_argument('--selection-ref', required=True)
    parser.add_argument('--purpose', choices=('as_is', 'after_repair'), default='as_is')
    parser.add_argument('--lead-days', type=int, default=1)
    parser.add_argument('--max-age-days', type=int, default=180)
    parser.add_argument('--max-distance-meters', type=int, default=800)
    parser.add_argument('--max-area-divergence-bps', type=int, default=2500)
    parser.add_argument('--min-comparables', type=int, default=3)
    parser.add_argument('--max-comparables', type=int, default=6)
    args = parser.parse_args(argv)

    evaluated_on = date.fromisoformat(args.evaluated_on)
    raw = args.sales_csv.read_bytes()
    if len(raw) > 50_000_000:
        raise SystemExit('Sales export exceeds the 50MB budget')
    sales, rejected = [], []
    for index, row in enumerate(csv.DictReader(raw.decode('utf-8-sig').splitlines())):
        try:
            sales.append(parse_sale(row))
        except RowRejected as error:
            rejected.append({'row': index + 2, 'sale_id': (row.get('sale_id') or '').strip() or None, 'reason': str(error)})
    seen = set()
    unique = []
    for sale in sales:
        if sale['sale_id'] in seen:
            rejected.append({'row': None, 'sale_id': sale['sale_id'], 'reason': 'duplicate_sale_id'})
            continue
        seen.add(sale['sale_id'])
        unique.append(sale)

    cases, review_queue, case_rejects = build(
        unique, evaluated_on, args.purpose, args.lead_days, args.max_age_days,
        args.max_distance_meters, args.max_area_divergence_bps, args.min_comparables, args.max_comparables)
    rejected.extend(case_rejects)

    dataset = {
        'schema_version': '1.0', 'dataset_kind': 'attested_local_sales',
        'cohort_ref': {'source_ref': args.cohort_ref, 'sha256': hashlib.sha256(raw).hexdigest()},
        'rights_ref': {'source_ref': args.rights_ref, 'sha256': hashlib.sha256(args.rights_ref.encode()).hexdigest()},
        'selection_ref': {'source_ref': args.selection_ref, 'sha256': hashlib.sha256(args.selection_ref.encode()).hexdigest()},
        'cases': cases,
    }
    args.out.write_text(json.dumps(dataset, indent=2, sort_keys=True, allow_nan=False) + '\n')
    args.review_queue.write_text(json.dumps({'adjustments_required': review_queue, 'comparison_review_refs_required': sorted({case['case_id'] for case in cases})}, indent=2, sort_keys=True) + '\n')
    args.rejects.write_text(json.dumps(rejected, indent=2, sort_keys=True) + '\n')

    report = {
        'rows_parsed': len(unique), 'rows_rejected': len(rejected), 'cases_built': len(cases),
        'adjustments_awaiting_review': len(review_queue),
        'cohort_sha256': hashlib.sha256(args.out.read_bytes()).hexdigest(),
        'status': 'skeleton_not_yet_evaluable',
        'next_step': 'A reviewer must supply every adjustment in the review queue with its evidence_ref and reviewed_by, and a comparison_review_ref per comparable, before benchmark_san_joaquin.py will accept this cohort.',
    }
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
