from decimal import Decimal, localcontext

import pytest

from backend.valuation.finance import (debt_yield, equity_multiple, financing_fees, internal_rate_of_return,
                                       interest_only_payment, leverage_ratios, mortgage_payment,
                                       net_present_value, remaining_balance, yield_on_cost)


class TestLeverageAndCoverage:
    def test_loan_to_value_and_cost_against_hand_computation(self):
        result = leverage_ratios(30000000, 40000000, 35000000)
        assert result['loan_to_value'] == '0.750000'
        assert result['loan_to_cost'] == '0.857143'
        assert result['equity_required_cents'] == 10000000

    def test_loan_to_cost_is_absent_when_no_cost_is_supplied(self):
        assert leverage_ratios(30000000, 40000000)['loan_to_cost'] is None

    def test_equity_required_never_goes_negative_on_an_overfunded_loan(self):
        assert leverage_ratios(50000000, 40000000)['equity_required_cents'] == 0

    def test_debt_yield_and_yield_on_cost(self):
        assert debt_yield(3000000, 30000000) == '0.100000'
        assert yield_on_cost(3500000, 50000000) == '0.070000'

    def test_negative_noi_is_reported_not_floored(self):
        assert debt_yield(-500000, 30000000).startswith('-')

    @pytest.mark.parametrize('denominator', [0, -1])
    def test_a_zero_or_negative_denominator_is_refused(self, denominator):
        with pytest.raises(ValueError):
            debt_yield(1000, denominator)
        with pytest.raises(ValueError):
            leverage_ratios(1000, denominator)


class TestInterestOnlyAndFees:
    def test_interest_only_payment_against_hand_computation(self):
        result = interest_only_payment(30000000, 850)
        assert result['monthly_interest_cents'] == 212500
        assert result['principal_repaid_cents'] == 0
        assert result['balloon_at_maturity_cents'] == 30000000

    def test_a_zero_rate_interest_only_loan_costs_nothing_monthly(self):
        assert interest_only_payment(30000000, 0)['monthly_interest_cents'] == 0

    def test_points_and_flat_fees(self):
        assert financing_fees(30000000, 200, 150000) == {'points_cents': 600000, 'flat_fee_cents': 150000, 'total_financing_fees_cents': 750000}


class TestAmortization:
    def test_remaining_balance_matches_an_independent_amortization_loop(self):
        principal, bps, term, elapsed = 30000000, 650, 360, 120
        with localcontext() as context:
            context.prec = 40
            rate = Decimal(bps) / Decimal(120000)
            payment = Decimal(principal) * rate / (1 - (1 + rate) ** -term)
            balance = Decimal(principal)
            for _ in range(elapsed):
                balance = balance * (1 + rate) - payment
            oracle = int(balance.quantize(Decimal('1')))
        assert abs(oracle - remaining_balance(principal, bps, term, elapsed)['balance_cents']) <= 1

    def test_balance_is_full_at_origination_and_zero_at_maturity(self):
        assert remaining_balance(30000000, 650, 360, 0)['balance_cents'] == 30000000
        assert remaining_balance(30000000, 650, 360, 360)['balance_cents'] == 0

    def test_balance_decreases_monotonically(self):
        balances = [remaining_balance(30000000, 650, 360, month)['balance_cents'] for month in range(0, 361, 12)]
        assert balances == sorted(balances, reverse=True)
        assert len(set(balances)) == len(balances)

    def test_a_zero_rate_loan_amortizes_linearly(self):
        assert remaining_balance(12000000, 0, 120, 60)['balance_cents'] == 6000000

    def test_principal_repaid_and_balance_always_reconstruct_the_principal(self):
        for elapsed in (0, 1, 60, 180, 359, 360):
            result = remaining_balance(30000000, 650, 360, elapsed)
            assert result['balance_cents'] + result['principal_repaid_cents'] == 30000000

    def test_the_monthly_payment_agrees_with_the_existing_mortgage_function(self):
        rate, term, principal = 650, 360, 30000000
        monthly = Decimal(rate) / Decimal(120000)
        expected = Decimal(principal) * monthly / (1 - (1 + monthly) ** -term)
        assert abs(mortgage_payment(principal, rate, term)['monthly_principal_interest_cents'] - int(expected.quantize(Decimal('1')))) <= 1

    def test_elapsed_beyond_the_term_is_refused(self):
        with pytest.raises(ValueError):
            remaining_balance(30000000, 650, 360, 361)


class TestDiscountedCashFlow:
    def test_net_present_value_against_hand_computation(self):
        oracle = -100000 + sum(Decimal(50000) / Decimal('1.1') ** period for period in (1, 2, 3))
        assert net_present_value([-100000, 50000, 50000, 50000], 1000) == int(oracle.quantize(Decimal('1')))

    def test_an_exact_break_even_series_discounts_to_zero(self):
        assert net_present_value([-100000, 110000], 1000) == 0

    def test_a_zero_discount_rate_is_a_plain_sum(self):
        assert net_present_value([-100000, 40000, 40000, 40000], 0) == 20000

    @pytest.mark.parametrize('series', [[], 'x', {}, None])
    def test_a_malformed_series_is_refused(self, series):
        with pytest.raises(ValueError):
            net_present_value(series, 1000)


class TestInternalRateOfReturn:
    @pytest.mark.parametrize('series,expected', [([-100000, 110000], 1000), ([-100000, 0, 121000], 1000), ([-100000, 50000, 50000, 50000], 2337)])
    def test_irr_brackets_the_known_rate(self, series, expected):
        assert abs(internal_rate_of_return(series)['irr_bps'] - expected) <= 3

    def test_the_net_present_value_at_the_reported_irr_is_near_zero(self):
        series = [-100000, 50000, 50000, 50000]
        rate = internal_rate_of_return(series)['irr_bps']
        assert abs(net_present_value(series, rate)) <= 100

    @pytest.mark.parametrize('series', [[-100000, -50000], [100000, 50000], [0, 0]])
    def test_a_series_without_a_sign_change_refuses_rather_than_guesses(self, series):
        result = internal_rate_of_return(series)
        assert result['irr_bps'] is None
        assert result['reason']

    def test_the_method_is_labelled_as_bisection_not_closed_form(self):
        assert 'bisection' in internal_rate_of_return([-100000, 110000])['method']

    def test_irr_is_deterministic(self):
        assert len({internal_rate_of_return([-100000, 50000, 50000, 50000])['irr_bps'] for _ in range(20)}) == 1

    @pytest.mark.parametrize('series', [[100000], [], 'x'])
    def test_a_series_too_short_to_have_a_return_is_refused(self, series):
        with pytest.raises(ValueError):
            internal_rate_of_return(series)


class TestEquityMultiple:
    def test_equity_multiple_against_hand_computation(self):
        result = equity_multiple([10000000, 5000000], [9000000, 12000000])
        assert result['invested_cents'] == 15000000
        assert result['returned_cents'] == 21000000
        assert result['equity_multiple'] == '1.400000'
        assert result['profit_cents'] == 6000000

    def test_a_total_loss_reports_a_zero_multiple_and_a_negative_profit(self):
        result = equity_multiple([10000000], [0])
        assert result['equity_multiple'] == '0.000000'
        assert result['profit_cents'] == -10000000

    def test_zero_invested_capital_is_refused_rather_than_dividing_by_zero(self):
        with pytest.raises(ValueError):
            equity_multiple([], [10000])


class TestNoFloatsAndNoSilentDefaults:
    @pytest.mark.parametrize('bad', [1.5, True, '100', None])
    def test_float_boolean_string_and_missing_money_are_refused(self, bad):
        for call in (lambda: leverage_ratios(bad, 40000000), lambda: debt_yield(bad, 1000),
                     lambda: interest_only_payment(bad, 100), lambda: financing_fees(bad, 100),
                     lambda: remaining_balance(bad, 650, 360, 12), lambda: net_present_value([bad], 100),
                     lambda: equity_multiple([bad], [1])):
            with pytest.raises((ValueError, TypeError)):
                call()
