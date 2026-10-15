from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
from decimal import Decimal
import hashlib
import json
import re
import statistics

from backend.valuation.engine import compare_sales, day, integer, token


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def reference(value):
    if not isinstance(value, dict) or set(value) != {'source_ref', 'sha256'}:
        raise ValueError('Source reference and document checksum required')
    token(value['source_ref'])
    if not isinstance(value['sha256'], str) or not re.fullmatch('[a-f0-9]{64}', value['sha256']):
        raise ValueError('Invalid document checksum')


def summarize(rows):
    predicted = [row for row in rows if row['estimate_cents'] is not None]
    result = {'eligible_cases': len(rows), 'predicted_cases': len(predicted), 'abstained_cases': len(rows) - len(predicted), 'statuses': dict(sorted(Counter(row['status'] for row in rows).items()))}
    if not predicted:
        return result
    errors = [row['estimate_cents'] - row['truth_cents'] for row in predicted]
    percentages = sorted(Decimal(abs(error)) * 100 / row['truth_cents'] for error, row in zip(errors, predicted))
    number = lambda value: str(Decimal(value).quantize(Decimal('0.0001')))
    result.update(mean_absolute_error_dollars=number(Decimal(sum(abs(error) for error in errors)) / len(errors) / 100), mean_absolute_percentage_error=number(sum(percentages) / len(percentages)), median_absolute_percentage_error=number(statistics.median(percentages)), p90_absolute_percentage_error=number(percentages[(9 * len(percentages) + 9) // 10 - 1]), mean_signed_percentage_error=number(sum(Decimal(error) * 100 / row['truth_cents'] for error, row in zip(errors, predicted)) / len(errors)), within_10_percent=sum(value <= 10 for value in percentages), observed_comp_span_contains_sale=sum(row['low_cents'] <= row['truth_cents'] <= row['high_cents'] for row in predicted))
    return result


def evaluate(dataset, evaluated_on, predictor=compare_sales):
    evaluated = day(evaluated_on)
    if evaluated > date.today():
        raise ValueError('Future evaluation evidence is unavailable')
    if not isinstance(dataset, dict) or set(dataset) != {'schema_version', 'dataset_kind', 'cohort_ref', 'rights_ref', 'selection_ref', 'cases'}:
        raise ValueError('Explicit bounded cohort manifest required')
    if dataset['schema_version'] != '1.0' or dataset['dataset_kind'] not in {'synthetic', 'attested_local_sales'}:
        raise ValueError('Unknown benchmark evidence class')
    for field in ('cohort_ref', 'rights_ref', 'selection_ref'):
        reference(dataset[field])
    cases = dataset['cases']
    if not isinstance(cases, list) or not 1 <= len(cases) <= 10000:
        raise ValueError('Expected 1 to 10000 cases')
    validated, properties, sales = [], set(), set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {'case_id', 'city', 'county_fips', 'geography_ref', 'features_observed_on', 'request', 'truth'}:
            raise ValueError('Malformed benchmark case')
        token(case['case_id'])
        token(case['city'])
        if case['county_fips'] != '06077':
            raise ValueError('Only San Joaquin County cases are supported')
        reference(case['geography_ref'])
        request = case['request']
        if not isinstance(request, dict) or set(request) - {'as_of', 'purpose', 'renovation_plan_ref', 'subject', 'comparables', 'policy'}:
            raise ValueError('Unexpected predictor input, including target leakage')
        effective = day(request['as_of'])
        if not day(case['features_observed_on']) <= effective <= evaluated:
            raise ValueError('Subject features were not available at prediction time')
        subject_id = token(request['subject']['property_id'])
        if set(request['subject']) != {'property_id', 'market_area', 'property_type', 'features'}:
            raise ValueError('Unexpected subject input')
        if subject_id in properties:
            raise ValueError('Repeated target property inflates cohort size')
        properties.add(subject_id)
        truth = case['truth']
        if not isinstance(truth, dict) or set(truth) != {'property_id', 'sale_id', 'kind', 'price_cents', 'contract_on', 'closed_on', 'available_on', 'arms_length', 'sale_ref', 'condition_basis', 'condition_ref', 'renovation_plan_ref', 'completed_on'}:
            raise ValueError('Exact closed-sale outcome and condition evidence required')
        sale_id = token(truth['sale_id'])
        if sale_id in sales or truth['property_id'] != subject_id or truth['kind'] != 'closed_sale' or truth['arms_length'] is not True:
            raise ValueError('Duplicate, wrong-property or nonmarket target')
        sales.add(sale_id)
        integer(truth['price_cents'], 1)
        contract, closed, available = (day(truth[field]) for field in ('contract_on', 'closed_on', 'available_on'))
        if not effective < contract <= closed <= available <= evaluated or (closed - effective).days > 90:
            raise ValueError('Target must close within 90 days after a precontract prediction')
        reference(truth['sale_ref'])
        reference(truth['condition_ref'])
        if request['purpose'] == 'as_is':
            if truth['condition_basis'] != 'unchanged_as_is' or truth['renovation_plan_ref'] is not None or truth['completed_on'] is not None:
                raise ValueError('As-is outcomes require unchanged condition')
        elif request['purpose'] == 'after_repair':
            if truth['condition_basis'] != 'completed_renovation' or truth['renovation_plan_ref'] != request['renovation_plan_ref'] or not effective < day(truth['completed_on']) <= contract:
                raise ValueError('ARV outcome requires completed matching renovation evidence')
        else:
            raise ValueError('Unsupported benchmark purpose')
        comps = request['comparables']
        if not isinstance(comps, list) or len(comps) > 50:
            raise ValueError('Comparable budget exceeded')
        for comp in comps:
            if not isinstance(comp, dict) or comp.get('property_id') == subject_id or comp.get('sale_id') == sale_id:
                raise ValueError('Target cannot be its own comparable')
            if day(comp['available_on']) > effective or day(comp['closed_on']) > effective:
                raise ValueError('Future comparable information leaked into prediction')
        validated.append(case)
    if len({case['case_id'] for case in validated}) != len(validated):
        raise ValueError('Duplicate case identity')
    predictions = []
    for case in validated:
        frozen = deepcopy(case['request'])
        request_digest = digest(frozen)
        result = predictor(frozen)
        if digest(frozen) != request_digest:
            raise ValueError('Predictor mutated its frozen input')
        point = result['point_cents']
        if point is not None:
            integer(point, 1)
            low, high = result['supported_low_cents'], result['supported_high_cents']
            integer(low, 1)
            integer(high, 1)
            if not low <= point <= high:
                raise ValueError('Inconsistent prediction span')
        else:
            low = high = None
        predictions.append({'case_id': case['case_id'], 'purpose': case['request']['purpose'], 'city': case['city'], 'property_type': case['request']['subject']['property_type'], 'request_sha256': request_digest, 'estimate_cents': point, 'low_cents': low, 'high_cents': high, 'status': result['status'], 'truth_cents': case['truth']['price_cents']})
    grouped = {}
    for dimension in ('purpose', 'city', 'property_type'):
        groups = defaultdict(list)
        for row in predictions:
            groups[row[dimension]].append(row)
        grouped[dimension] = {key: summarize(rows) for key, rows in sorted(groups.items())}
    return {'schema_version': '1.0', 'status': 'synthetic_contract_only' if dataset['dataset_kind'] == 'synthetic' else 'attested_local_evaluation_requires_source_audit', 'dataset_sha256': digest(dataset), 'evaluated_on': evaluated_on, 'metrics': summarize(predictions), 'strata': grouped, 'cases': predictions, 'evidence_limit': 'Checksums and supplied attestations do not independently verify a sale, condition, rights or freedom from analyst hindsight. Sale outcomes are imperfect value proxies. Comp spans are not statistical intervals.', 'production_ready': False, 'quote_authorized': False, 'offer_authorized': False}
