from backend.valuation.engine import integer
from backend.valuation.finance import flip_analysis, rounded
from decimal import Decimal


REVIEW_ITEMS = ('verify_title_liens_and_payoffs', 'verify_tenancy_and_applicable_local_rules', 'verify_permits_and_legal_units', 'obtain_property_specific_insurance_quote', 'verify_tax_rate_direct_assessments_and_supplementals', 'itemize_repairs_financing_holding_and_exit_costs', 'review_closed_sales_and_actual_condition', 'verify_contact_permissions_and_suppression')


def california_context(lead_id, lead, prop):
    if not isinstance(prop, dict) or not isinstance(lead, dict) or not prop.get('id') or lead.get('property_id') != prop['id'] or prop.get('state') != 'CA':
        return {}
    return {'schema_version': '1.0', 'lead_id': lead_id, 'state': 'CA', 'status': 'california_review_only', 'profile_version': '2026-10-14', 'review_items': list(REVIEW_ITEMS), 'quote_authorized': False, 'offer_authorized': False}


def flip_stress_grid(costs, resale_declines_bps, repair_increases_bps, additional_holding_cents):
    required = ('resale_cents', 'purchase_cents', 'repairs_cents', 'buying_fixed_cents', 'holding_cents', 'financing_fixed_cents', 'target_profit_cents', 'buying_bps', 'selling_bps')
    if not isinstance(costs, dict) or any(key not in costs or costs[key] is None for key in required):
        raise ValueError('Explicit resale and all cost inputs are required; unknown costs are not zero')
    axes = (resale_declines_bps, repair_increases_bps, additional_holding_cents)
    if any(not isinstance(axis, list) or not 1 <= len(axis) <= 10 for axis in axes):
        raise ValueError('Bounded nonempty scenario axes required')
    base = {key: costs[key] for key in required}
    flip_analysis(**base)
    rows = []
    for decline in resale_declines_bps:
        integer(decline, 0, 9999)
        for increase in repair_increases_bps:
            integer(increase, 0, 10000)
            for holding in additional_holding_cents:
                integer(holding)
                scenario = dict(base)
                scenario['resale_cents'] = max(1, rounded(Decimal(base['resale_cents']) * (10000 - decline) / 10000))
                scenario['repairs_cents'] = rounded(Decimal(base['repairs_cents']) * (10000 + increase) / 10000)
                scenario['holding_cents'] += holding
                result = flip_analysis(**scenario)
                rows.append({'resale_decline_bps': decline, 'repair_increase_bps': increase, 'additional_holding_cents': holding, **result})
    return {'status': 'scenario_analysis_only', 'scenarios': rows, 'worst_profit_cents': min(row['profit_cents'] for row in rows), 'quote_authorized': False, 'offer_authorized': False}
