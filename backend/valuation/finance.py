from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP

from backend.valuation.engine import integer


def rounded(value):
    return int(value.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def repairs_with_contingency(line_item_cents, contingency_bps):
    if not isinstance(line_item_cents, list) or not line_item_cents or len(line_item_cents) > 500:
        raise ValueError('Itemized repair budget is required')
    base = sum(integer(item) for item in line_item_cents)
    contingency = rounded(Decimal(base) * integer(contingency_bps, 0, 10000) / 10000)
    return {'base_cents': base, 'contingency_cents': contingency, 'total_cents': base + contingency}


def screening_mao(arv_cents, repairs_cents, multiplier_bps=7000):
    amount = Decimal(integer(arv_cents, 1)) * integer(multiplier_bps, 1, 10000) / 10000 - integer(repairs_cents)
    return max(0, int(amount.to_integral_value(rounding=ROUND_FLOOR)))


def flip_analysis(resale_cents, purchase_cents, repairs_cents, buying_fixed_cents, holding_cents, financing_fixed_cents, target_profit_cents, buying_bps, selling_bps):
    resale, purchase = integer(resale_cents, 1), integer(purchase_cents)
    repairs = integer(repairs_cents)
    fixed = sum(integer(v) for v in (buying_fixed_cents, holding_cents, financing_fixed_cents))
    buy_rate = Decimal(integer(buying_bps, 0, 10000)) / 10000
    sell_rate = Decimal(integer(selling_bps, 0, 10000)) / 10000
    buying = rounded(Decimal(purchase) * buy_rate)
    selling = rounded(Decimal(resale) * sell_rate)
    invested = purchase + repairs + fixed + buying
    profit = resale - selling - invested
    limit = (Decimal(resale) * (1 - sell_rate) - repairs - fixed - integer(target_profit_cents)) / (1 + buy_rate)
    maximum = max(0, int(limit.to_integral_value(rounding=ROUND_FLOOR)))
    def limit_profit(amount):
        return resale - selling - amount - rounded(Decimal(amount) * buy_rate) - repairs - fixed
    while maximum and limit_profit(maximum) < target_profit_cents:
        maximum -= 1
    return {'buying_variable_cents': buying, 'selling_cents': selling, 'total_project_cost_cents': invested + selling, 'profit_cents': profit, 'profit_over_pre_sale_project_cost': str((Decimal(profit) / invested).quantize(Decimal('0.000001'))) if invested else None, 'purchase_limit_cents': maximum, 'target_profit_feasible_at_limit': limit_profit(maximum) >= target_profit_cents, 'cost_model': 'fixed_holding_and_financing_inputs_must_be_recomputed_if_purchase_or_term_changes', 'quote_authorized': False}


def rental_analysis(annual_gross_rent_cents, vacancy_bps, other_income_cents, operating_expenses_cents, annual_debt_service_cents, capital_reserve_cents, property_value_cents, market_cap_rate_bps):
    gross = integer(annual_gross_rent_cents)
    loss = rounded(Decimal(gross) * integer(vacancy_bps, 0, 10000) / 10000)
    income = gross - loss + integer(other_income_cents)
    noi = income - integer(operating_expenses_cents)
    debt, reserve = integer(annual_debt_service_cents), integer(capital_reserve_cents)
    value = integer(property_value_cents, 1)
    cap = integer(market_cap_rate_bps, 1, 10000)
    return {'effective_gross_income_cents': income, 'noi_cents': noi, 'cash_flow_after_debt_and_reserves_cents': noi - debt - reserve, 'dscr': str((Decimal(noi) / debt).quantize(Decimal('0.000001'))) if debt else None, 'cap_rate': str((Decimal(noi) / value).quantize(Decimal('0.000001'))), 'income_indication_cents': rounded(Decimal(noi) * 10000 / cap) if noi > 0 else None, 'income_indication_is_market_appraisal': False}


def mortgage_payment(principal_cents, annual_interest_bps, term_months, monthly_tax_cents=0, monthly_insurance_cents=0, monthly_hoa_cents=0, monthly_mortgage_insurance_cents=0):
    principal = integer(principal_cents)
    months = integer(term_months, 1, 600)
    monthly_rate = Decimal(integer(annual_interest_bps, 0, 10000)) / 120000
    payment = Decimal(principal) / months if not monthly_rate else Decimal(principal) * monthly_rate / (1 - (1 + monthly_rate) ** -months)
    pi = rounded(payment)
    extras = sum(integer(item) for item in (monthly_tax_cents, monthly_insurance_cents, monthly_hoa_cents, monthly_mortgage_insurance_cents))
    return {'monthly_principal_interest_cents': pi, 'monthly_housing_cost_cents': pi + extras, 'loan_type': 'fixed_rate_fully_amortizing', 'last_payment_may_differ_due_to_rounding': True}


def cost_approach(land_cents, replacement_improvements_cents, physical_depreciation_cents, functional_depreciation_cents, external_depreciation_cents):
    land, improvements = integer(land_cents), integer(replacement_improvements_cents)
    depreciation = sum(integer(v) for v in (physical_depreciation_cents, functional_depreciation_cents, external_depreciation_cents))
    if depreciation > improvements:
        raise ValueError('Depreciation exceeds replacement improvements')
    return {'cost_indication_cents': land + improvements - depreciation, 'cost_indication_is_market_appraisal': False}


def cash_on_cash_return(annual_cash_flow_cents, initial_equity_cents):
    cash = integer(annual_cash_flow_cents, -10**14)
    equity = integer(initial_equity_cents, 1)
    return str((Decimal(cash) / equity).quantize(Decimal('0.000001')))
