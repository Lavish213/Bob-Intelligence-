from datetime import date, timedelta
import random

import pytest

from backend.valuation.san_joaquin import county_context, index_ratio, normalize_apn, parcel_evidence
from backend.call_planner.brief_generator import generate_call_brief


@pytest.mark.parametrize('seed', range(1000))
def test_county_apn_preserves_zeroes_and_parcels_are_not_sold_comps(seed):
    rng = random.Random(seed)
    apn = f'{rng.randrange(1, 100000000):08d}'
    formatted = f'{apn[:3]}-{apn[3:6]}-{apn[6:]}'
    assert normalize_apn(formatted) == normalize_apn(apn) == apn
    attrs = {'APN': apn, 'APN_DASH': formatted, 'LAND_VALUE': 100000, 'IMPROVEMENT_VALUE': 200000, 'TOTALLIV_AREA': 1700, 'BEDROOMS': 3, 'BATHROOM_WHOLE': 2, 'BATHROOM_HALF': 0, 'YEAR_BUILT': '1990', 'SITUSCITYNAME': 'STOCKTON', 'SALE_PRICE': 900000, 'OWNER': 'ignored'}
    result = parcel_evidence(attrs, date.today().isoformat())
    assert result['bathrooms_half_units'] == 4
    assert result['assessed_land_and_improvement_cents'] == 30000000
    assert result['sale_price_cents'] is result['condition'] is result['quality'] is None
    assert result['quote_authorized'] is result['offer_authorized'] is False
    assert 'OWNER' not in result and result['city_label_verifies_jurisdiction'] is False


@pytest.mark.parametrize('bad', [12345678, True, None, '00000000', '1234567', '123456789', "12345678' OR 1=1", '123-456-789', '１２３４５６７８'])
def test_bad_apns_are_not_guessed(bad):
    with pytest.raises(ValueError):
        normalize_apn(bad)


def test_missing_assessment_component_and_unknown_physical_values_stay_unknown():
    result = parcel_evidence({'APN': '01234567', 'LAND_VALUE': 50000, 'BATHROOM_WHOLE': 2, 'YEAR_BUILT': 'unknown'}, date.today().isoformat())
    assert result['assessed_land_and_improvement_cents'] is result['bathrooms_half_units'] is result['year_built'] is None
    assert result['sale_price_cents'] is None


def test_conflicting_parcel_and_future_retrieval_are_rejected():
    with pytest.raises(ValueError):
        parcel_evidence({'APN': '01234567', 'APN_DASH': '111-111-11'}, date.today().isoformat())
    with pytest.raises(ValueError):
        parcel_evidence({'APN': '01234567'}, (date.today() + timedelta(days=1)).isoformat())


def test_revised_index_vintage_cannot_enter_an_earlier_backtest():
    series = {'county_fips': '06077', 'series_id': 'ATNHPIUS06077A', 'retrieved_on': '2026-10-14', 'source_release_on': '2026-06-30', 'observations': {'2024': '288.12', '2025': '285.59'}}
    assert index_ratio(series, 2024, 2025, '2026-10-14')['ratio'] == '0.991219'
    with pytest.raises(ValueError):
        index_ratio(series, 2024, 2025, '2025-12-31')
    series['county_fips'] = '06019'
    with pytest.raises(ValueError):
        index_ratio(series, 2024, 2025, '2026-10-14')


def test_local_context_is_bound_and_general_not_property_verification_or_pricing():
    prop = {'id': 'property-1', 'county': 'San Joaquin', 'state': 'CA'}
    lead = {'property_id': 'property-1'}
    context = county_context('lead-1', lead, prop)
    assert context['county_fips'] == '06077' and context['parcel_verified'] is False
    assert county_context('lead-1', lead, {**prop, 'id': 'other'}) == {}
    assert county_context('lead-1', lead, {**prop, 'county': 'Fresno'}) == {}
    assert county_context('lead-1', lead, {**prop, 'state': 'TX'}) == {}
    brief = generate_call_brief('lead-1', lead, prop, {}, {}).to_dict()
    assert brief['evidence']['county_context'] == context
    assert brief['ready_for_call'] is False and brief['evidence']['valuation']['status'] == 'needs_data'
