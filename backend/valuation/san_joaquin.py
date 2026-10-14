from datetime import date
from decimal import Decimal
import re

from backend.valuation.engine import day, integer


COUNTY_FIPS = '06077'
PARCEL_SOURCE = 'https://sjmap.org/server/rest/services/Apps/DistrictViewerSvc/MapServer/10'
REVIEW_ITEMS = ('verify_parcel_and_competitive_submarket', 'verify_city_or_unincorporated_permit_authority', 'verify_permitted_living_area_and_adu_scope', 'review_flood_levee_and_insurance_evidence', 'review_actual_tax_rate_assessments_and_supplemental_costs', 'review_rural_utilities_access_and_land_contracts', 'verify_condition_and_current_closed_sale_evidence')


def normalize_apn(value):
    if not isinstance(value, str):
        raise ValueError('Parcel identifiers must preserve leading zeroes')
    text = value.strip()
    if not re.fullmatch(r'(?:[0-9]{8}|[0-9]{3}-[0-9]{3}-[0-9]{2})', text):
        raise ValueError('Expected San Joaquin eight-digit parcel identifier')
    result = text.replace('-', '')
    if result == '00000000':
        raise ValueError('Placeholder parcel identifier')
    return result


def _known_integer(value, minimum, maximum):
    return value if type(value) is int and minimum <= value <= maximum else None


def parcel_evidence(attrs, retrieved_on, source_url=PARCEL_SOURCE):
    if not isinstance(attrs, dict) or source_url != PARCEL_SOURCE:
        raise ValueError('Expected official county parcel attributes')
    retrieved = day(retrieved_on)
    if retrieved > date.today():
        raise ValueError('Future source retrieval')
    apn = normalize_apn(attrs['APN'])
    if attrs.get('APN_DASH') and normalize_apn(attrs['APN_DASH']) != apn:
        raise ValueError('Conflicting parcel identifiers')
    land = _known_integer(attrs.get('LAND_VALUE'), 0, 10**12)
    improvements = _known_integer(attrs.get('IMPROVEMENT_VALUE'), 0, 10**12)
    area = _known_integer(attrs.get('TOTALLIV_AREA'), 1, 100000)
    bedrooms = _known_integer(attrs.get('BEDROOMS'), 0, 100)
    whole = _known_integer(attrs.get('BATHROOM_WHOLE'), 0, 100)
    half = _known_integer(attrs.get('BATHROOM_HALF'), 0, 100)
    year = attrs.get('YEAR_BUILT')
    year = int(year) if isinstance(year, str) and re.fullmatch(r'[0-9]{4}', year) else None
    year = year if year is not None and 1600 <= year <= retrieved.year else None
    city = attrs.get('SITUSCITYNAME')
    city = city.strip() if isinstance(city, str) and 0 < len(city.strip()) <= 80 and all(ord(c) >= 32 for c in city) else None
    return {'schema_version': '1.0', 'county_fips': COUNTY_FIPS, 'apn': apn, 'source_url': source_url, 'retrieved_on': retrieved_on, 'status': 'parcel_context_only', 'living_area_sqft': area, 'bedrooms': bedrooms, 'bathrooms_half_units': whole * 2 + half if whole is not None and half is not None else None, 'year_built': year, 'situs_city_label': city, 'city_label_verifies_jurisdiction': False, 'assessed_land_and_improvement_cents': (land + improvements) * 100 if land is not None and improvements is not None else None, 'sale_price_cents': None, 'condition': None, 'quality': None, 'property_type': None, 'quote_authorized': False, 'offer_authorized': False}


def index_ratio(series, from_year, to_year, as_of):
    effective = day(as_of)
    if series.get('county_fips') != COUNTY_FIPS or series.get('series_id') != 'ATNHPIUS06077A' or day(series['retrieved_on']) > effective or day(series['source_release_on']) > effective:
        raise ValueError('Wrong geography or source vintage unavailable at effective date')
    integer(from_year, 1975, effective.year)
    integer(to_year, from_year, effective.year)
    observations = series['observations']
    values = [Decimal(observations[str(year)]) for year in (from_year, to_year)]
    if any(not value.is_finite() or value <= 0 for value in values):
        raise ValueError('Missing or invalid index observation')
    return {'status': 'county_trend_context_only', 'county_fips': COUNTY_FIPS, 'from_year': from_year, 'to_year': to_year, 'ratio': str((values[1] / values[0]).quantize(Decimal('0.000001'))), 'individual_property_adjustment_authorized': False, 'quote_authorized': False, 'offer_authorized': False}


def county_context(lead_id, lead, prop):
    if not isinstance(prop, dict) or not isinstance(lead, dict) or lead.get('property_id') != prop.get('id'):
        return {}
    county = prop.get('county')
    state = prop.get('state')
    if not isinstance(county, str) or county.strip().lower() not in {'san joaquin', 'san joaquin county'} or state != 'CA':
        return {}
    return {'schema_version': '1.0', 'lead_id': lead_id, 'county_fips': COUNTY_FIPS, 'profile_version': '2026-10-14', 'status': 'county_context_only', 'parcel_verified': False, 'review_items': list(REVIEW_ITEMS), 'quote_authorized': False, 'offer_authorized': False}
