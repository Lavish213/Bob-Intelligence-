import random
from decimal import Decimal, ROUND_HALF_UP

import pytest

from backend.valuation.california import california_context, flip_stress_grid


@pytest.mark.parametrize('seed', range(1000))
def test_stress_profit_matches_independent_cent_ledger(seed):
    rng = random.Random(seed)
    costs = dict(resale_cents=rng.randint(10000000, 200000000), purchase_cents=rng.randint(1000000, 100000000), repairs_cents=rng.randint(0, 10000000), buying_fixed_cents=200000, holding_cents=600000, financing_fixed_cents=400000, target_profit_cents=3000000, buying_bps=200, selling_bps=600)
    decline, increase, holding = rng.randint(0, 3000), rng.randint(0, 5000), rng.randint(0, 5000000)
    cents = lambda v: int(v.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    resale = cents(Decimal(costs['resale_cents']) * (10000-decline)/10000)
    repairs = cents(Decimal(costs['repairs_cents']) * (10000+increase)/10000)
    expected = resale-cents(Decimal(resale)*600/10000)-costs['purchase_cents']-cents(Decimal(costs['purchase_cents'])*200/10000)-repairs-1200000-holding
    report = flip_stress_grid(costs, [decline], [increase], [holding])
    assert report['worst_profit_cents'] == expected
    assert report['offer_authorized'] is False


def test_unknown_costs_are_not_free():
    with pytest.raises(ValueError):
        flip_stress_grid({'repairs_cents': None}, [0], [0], [0])


def test_california_context_requires_canonical_property():
    assert california_context('lead', {'property_id': 'a'}, {'id': 'a', 'state': 'CA'})['status'] == 'california_review_only'
    assert california_context('lead', {'property_id': 'b'}, {'id': 'a', 'state': 'CA'}) == {}
    assert california_context('lead', {}, {'state': 'CA'}) == {}
