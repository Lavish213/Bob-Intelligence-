from itertools import permutations

import pytest

from backend.scoring.opportunity import GRADE_ORDER, economics, evidence_confidence, grade_opportunity


def valuation(status='ready_advisory', point=46000000, count=5, review=None, spread=500):
    return {'status': status, 'point_cents': point, 'comparable_count': count, 'review_reasons': list(review or []), 'spread_bps': spread}


class TestEvidenceConfidenceIsSeparateFromEconomics:
    def test_strong_economics_with_thin_evidence_is_not_a_hot_buy(self):
        thin = grade_opportunity(valuation(status='needs_data', count=2), repairs_cents=2000000, asking_cents=20000000)
        assert thin['readiness'] != 'HOT_BUY'
        assert thin['evidence_confidence'] == 'thin'

    def test_identical_economics_with_verified_evidence_is_a_hot_buy(self):
        verified = grade_opportunity(valuation(), repairs_cents=2000000, asking_cents=20000000)
        assert (verified['readiness'], verified['grade']) == ('HOT_BUY', 'A')

    def test_the_two_differ_only_by_evidence_not_by_economics(self):
        thin = grade_opportunity(valuation(status='needs_data', count=2), repairs_cents=2000000, asking_cents=20000000)
        verified = grade_opportunity(valuation(), repairs_cents=2000000, asking_cents=20000000)
        assert thin['economics']['headroom_cents'] == verified['economics']['headroom_cents']
        assert thin['readiness'] != verified['readiness']

    def test_evidence_confidence_caps_the_grade(self):
        result = grade_opportunity(valuation(status='needs_review', review=['large_gross_adjustments']), repairs_cents=2000000, asking_cents=20000000)
        assert result['grade'] == 'B'
        assert 'grade_limited_by_evidence_confidence' in result['contradictory_evidence']

    @pytest.mark.parametrize('status,expected', [('invalid_input', 'unusable'), ('needs_data', 'thin'), ('needs_review', 'supported'), ('ready_advisory', 'verified')])
    def test_status_maps_to_an_evidence_level(self, status, expected):
        review = ['large_gross_adjustments'] if status == 'needs_review' else []
        assert evidence_confidence(valuation(status=status, review=review))[0] == expected

    def test_absent_valuation_is_unusable_not_assumed_good(self):
        assert evidence_confidence(None)[0] == 'unusable'
        assert evidence_confidence({})[0] == 'unusable'


class TestMissingDataIsNeverTreatedAsZero:
    @pytest.mark.parametrize('field', ['repairs_cents', 'asking_cents'])
    def test_a_missing_money_input_leaves_economics_unknown(self, field):
        kwargs = {'repairs_cents': 2000000, 'asking_cents': 20000000, field: None}
        result = grade_opportunity(valuation(), **kwargs)
        assert result['economics']['state'] == 'unknown'
        assert result['grade'] is None
        assert result['economics']['purchase_limit_cents'] is None

    def test_a_missing_arv_leaves_economics_unknown(self):
        assert economics(valuation(point=None), 2000000, 20000000)['state'] == 'unknown'

    def test_missing_inputs_are_named_in_the_next_action(self):
        result = grade_opportunity(valuation(), repairs_cents=None, asking_cents=20000000)
        assert result['missing_facts'] == ['repair_estimate']
        assert result['next_action'] == 'obtain_repair_estimate'

    @pytest.mark.parametrize('bad', [0, -1, True, 1.5, '20000000', None])
    def test_malformed_asking_prices_do_not_produce_a_grade(self, bad):
        assert grade_opportunity(valuation(), repairs_cents=2000000, asking_cents=bad)['grade'] is None

    def test_zero_repairs_is_a_real_value_not_a_missing_one(self):
        result = grade_opportunity(valuation(), repairs_cents=0, asking_cents=20000000)
        assert result['economics']['state'] == 'known'
        assert result['economics']['repair_estimate_cents'] == 0


class TestLockoutAndReadiness:
    def test_a_blocked_reason_archives_regardless_of_economics(self):
        result = grade_opportunity(valuation(), repairs_cents=2000000, asking_cents=20000000, blocked_reasons=['suppression_not_cleared'])
        assert result['readiness'] == 'ARCHIVED'
        assert result['lockout_class'] == 'blocked_until_suppression_or_contact_restriction_clears'
        assert result['next_action'] == 'resolve_contact_restriction'

    def test_an_unusable_valuation_archives_permanently(self):
        result = grade_opportunity({'status': 'invalid_input'}, repairs_cents=2000000, asking_cents=20000000)
        assert (result['readiness'], result['lockout_class']) == ('ARCHIVED', 'permanent_until_valid_valuation_evidence_exists')

    def test_asking_above_the_limit_is_price_dependent_not_archived(self):
        result = grade_opportunity(valuation(), repairs_cents=2000000, asking_cents=45000000)
        assert (result['grade'], result['readiness'], result['lockout_class']) == ('F', 'WATCH_LIST', 'price_dependent')
        assert result['next_action'] == 'monitor_price_movement'

    def test_unknown_economics_requires_research(self):
        assert grade_opportunity(valuation(), repairs_cents=None, asking_cents=None)['lockout_class'] == 'research_required'


class TestDeterminismAndAuthority:
    def test_nothing_is_ever_authorized(self):
        cases = [grade_opportunity(valuation(), 2000000, 20000000), grade_opportunity(None), grade_opportunity({'status': 'invalid_input'}),
                 grade_opportunity(valuation(), None, None), grade_opportunity(valuation(), 2000000, 20000000, ['suppression_not_cleared'])]
        assert all(case['quote_authorized'] is False and case['offer_authorized'] is False for case in cases)

    def test_grading_basis_is_labelled_as_a_screening_policy(self):
        assert 'not_an_appraisal_or_investment_guarantee' in grade_opportunity(valuation(), 2000000, 20000000)['grading_basis']

    def test_repeated_grading_is_identical(self):
        runs = {str(grade_opportunity(valuation(), 2000000, 20000000)) for _ in range(25)}
        assert len(runs) == 1

    def test_blocked_reason_order_does_not_change_the_outcome(self):
        reasons = ['suppression_not_cleared', 'missing_verified_phone', 'unsafe_intel_packet']
        outcomes = {str(grade_opportunity(valuation(), 2000000, 20000000, list(order))) for order in permutations(reasons)}
        assert len(outcomes) == 1

    def test_every_grade_is_a_known_letter_and_readiness_a_known_state(self):
        for asking in (10000000, 20000000, 30000000, 32000000, 45000000):
            result = grade_opportunity(valuation(), 2000000, asking)
            assert result['grade'] in GRADE_ORDER
            assert result['readiness'] in ('HOT_BUY', 'WATCH_LIST', 'ARCHIVED')

    def test_headroom_is_exact_integer_cents(self):
        money = economics(valuation(point=46000000), 2000000, 20000000)
        assert money['purchase_limit_cents'] == 46000000 * 70 // 100 - 2000000
        assert money['headroom_cents'] == money['purchase_limit_cents'] - 20000000
        assert all(isinstance(money[key], int) for key in ('purchase_limit_cents', 'headroom_cents', 'headroom_bps'))


class TestBriefIntegration:
    def test_the_brief_carries_an_opportunity_block(self):
        from backend.call_planner.brief_generator import generate_call_brief
        evidence = generate_call_brief('lead-1', {'id': 'lead-1', 'property_id': 'p1'}, {'id': 'p1', 'state': 'CA'}, {}, {}).to_dict()['evidence']
        assert 'opportunity' in evidence
        assert evidence['opportunity']['schema_version'] == '1.0'

    def test_a_blocked_brief_archives_the_opportunity(self):
        from backend.call_planner.brief_generator import generate_call_brief
        brief = generate_call_brief('lead-1', {'id': 'lead-1', 'property_id': 'p1'}, {'id': 'p1', 'state': 'CA'}, {}, {}).to_dict()
        assert brief['blocked_reasons']
        assert brief['evidence']['opportunity']['readiness'] == 'ARCHIVED'


class TestKnownFactsSurviveIncompleteEconomics:
    def test_a_known_arv_is_reported_even_when_repairs_are_missing(self):
        result = grade_opportunity(valuation(), repairs_cents=None, asking_cents=20000000)
        assert result['economics']['state'] == 'unknown'
        assert result['economics']['arv_point_cents'] == 46000000
        assert result['economics']['asking_price_cents'] == 20000000
        assert result['economics']['purchase_limit_cents'] is None
        assert result['economics']['headroom_cents'] is None

    def test_a_known_asking_price_is_reported_when_the_arv_is_missing(self):
        result = grade_opportunity(valuation(point=None), repairs_cents=2000000, asking_cents=20000000)
        assert result['economics']['asking_price_cents'] == 20000000
        assert result['economics']['repair_estimate_cents'] == 2000000
        assert result['economics']['arv_point_cents'] is None

    def test_every_economics_shape_exposes_the_same_keys(self):
        shapes = [
            grade_opportunity(valuation(), 2000000, 20000000),
            grade_opportunity(valuation(), None, 20000000),
            grade_opportunity(valuation(point=None), None, None),
        ]
        keys = {frozenset(shape['economics']) for shape in shapes}
        assert len(keys) == 1, 'a consumer should not have to branch on which keys exist'

    def test_derived_figures_are_never_present_without_all_three_inputs(self):
        for repairs, asking in ((None, 20000000), (2000000, None), (None, None)):
            money = grade_opportunity(valuation(), repairs, asking)['economics']
            assert money['purchase_limit_cents'] is None
            assert money['headroom_cents'] is None
            assert money['headroom_bps'] is None


class TestGradingCannotCrashABrief:
    @pytest.mark.parametrize('reasons', [[None, {}, 1, 'large_gross_adjustments'], [{}, []], 'not-a-list', {'a': 1}, None, [None]])
    def test_malformed_review_reasons_never_raise(self, reasons):
        result = grade_opportunity({'status': 'needs_review', 'point_cents': 100, 'comparable_count': 5, 'review_reasons': reasons, 'spread_bps': 1}, 1, 1)
        assert result['readiness'] in ('HOT_BUY', 'WATCH_LIST', 'ARCHIVED')
        assert all(isinstance(reason, str) for reason in result['evidence_reasons'])

    @pytest.mark.parametrize('valuation', [[], 'x', 7, True, {'status': 'ready_advisory'}, {'status': 'ready_advisory', 'comparable_count': True}])
    def test_hostile_valuations_never_raise(self, valuation):
        assert grade_opportunity(valuation, 1, 1)['quote_authorized'] is False

    @pytest.mark.parametrize('blocked', ['a-string', 7, {'a': 1}, [None, 1, 'suppression_not_cleared'], None])
    def test_hostile_blocked_reasons_never_raise(self, blocked):
        result = grade_opportunity({'status': 'ready_advisory', 'point_cents': 100, 'comparable_count': 5, 'review_reasons': [], 'spread_bps': 1}, 1, 1, blocked_reasons=blocked)
        assert all(isinstance(reason, str) for reason in result['blocked_reasons'])

    def test_extreme_money_values_do_not_raise(self):
        for arv, repairs, asking in ((10**14, 10**14, 1), (1, 0, 10**14), (1, 0, 1)):
            result = grade_opportunity({'status': 'ready_advisory', 'point_cents': arv, 'comparable_count': 5, 'review_reasons': [], 'spread_bps': 1}, repairs, asking)
            assert result['grade'] in GRADE_ORDER

    def test_a_grading_failure_does_not_destroy_the_brief(self, monkeypatch):
        from backend.call_planner import brief_generator
        monkeypatch.setattr(brief_generator, 'grade_opportunity', lambda *a, **k: 1 / 0)
        brief = brief_generator.generate_call_brief('lead-1', {'id': 'lead-1', 'property_id': 'p1'}, {'id': 'p1', 'state': 'CA'}, {}, {}).to_dict()
        assert brief['evidence']['opportunity'] is None
        assert brief['lead_id'] == 'lead-1'
        assert brief['evidence']['valuation'] is not None


class TestRandomizedHostileInput:
    POOL = (None, True, False, 0, -1, 1.5, 10**15, 'x', [], {}, [None], {'a': 1},
            'ready_advisory', 'needs_data', 'invalid_input', 3, 50,
            ['suppression_not_cleared'], [1, 'a', None], 'suppressed')

    def test_grading_never_raises_and_never_authorizes(self):
        import random
        generator = random.Random(20261108)
        shapes = set()
        for _ in range(3000):
            value = {key: generator.choice(self.POOL) for key in ('status', 'point_cents', 'comparable_count', 'review_reasons', 'spread_bps')}
            if generator.random() < 0.3:
                value = generator.choice(self.POOL)
            result = grade_opportunity(value, generator.choice(self.POOL), generator.choice(self.POOL), generator.choice(self.POOL))
            assert result['quote_authorized'] is False and result['offer_authorized'] is False
            assert result['readiness'] in ('HOT_BUY', 'WATCH_LIST', 'ARCHIVED')
            assert result['grade'] is None or result['grade'] in GRADE_ORDER
            assert all(isinstance(reason, str) for reason in result['blocked_reasons'])
            assert all(isinstance(reason, str) for reason in result['evidence_reasons'])
            shapes.add(frozenset(result['economics']))
        assert len(shapes) == 1, 'economics must expose one stable key set whatever the input'

    def test_a_string_of_reasons_is_not_split_into_characters(self):
        value = {'status': 'ready_advisory', 'point_cents': 100, 'comparable_count': 5, 'review_reasons': [], 'spread_bps': 1}
        assert grade_opportunity(value, 1, 1, blocked_reasons='suppressed')['blocked_reasons'] == []
        assert grade_opportunity(value, 1, 1, blocked_reasons=['suppression_not_cleared'])['blocked_reasons'] == ['suppression_not_cleared']
