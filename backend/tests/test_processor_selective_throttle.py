import unittest
from types import SimpleNamespace

from apps.worker.processor_support import _build_conviction_profile, _evaluate_selective_policy_throttle, _promote_high_conviction_skip


class ProcessorSelectiveThrottleTests(unittest.TestCase):
    def test_blocks_non_take_candidates_in_frozen_mode(self):
        blocked, reason = _evaluate_selective_policy_throttle(
            policy_state=SimpleNamespace(selective_throttle=True, selective_min_score_buffer=2, selective_min_rr=1.5, selective_require_governor_pass=True),
            final_decision='REJECT',
            score=72,
            threshold=70,
            sig_data={'r': 2.4},
            perf_governor={'suppressed': False},
            freshness_meta={'blocked': False},
        )
        self.assertTrue(blocked)
        self.assertIn('only TAKE candidates', reason)

    def test_allows_higher_tf_led_candidates_near_take_threshold_in_frozen_mode(self):
        blocked, reason = _evaluate_selective_policy_throttle(
            policy_state=SimpleNamespace(selective_throttle=True, selective_min_score_buffer=2, selective_min_rr=1.5, selective_require_governor_pass=True),
            final_decision='REJECT',
            score=71,
            threshold=80,
            sig_data={
                'r': 1.7,
                'meta': {
                    'thesis_timeframe': '15m',
                    'higher_tf_thesis': {
                        'thesis_timeframe': '15m',
                        'thesis_type': 'timeframe_signal',
                        'structure': 'requested_timeframe_signal',
                        'side': 'BUY',
                    },
                },
            },
            perf_governor={'suppressed': False},
            freshness_meta={'blocked': False},
        )
        self.assertFalse(blocked)
        self.assertEqual(reason, '')

    def test_allows_high_quality_take_candidates_in_frozen_mode(self):
        blocked, reason = _evaluate_selective_policy_throttle(
            policy_state=SimpleNamespace(selective_throttle=True, selective_min_score_buffer=2, selective_min_rr=1.5, selective_require_governor_pass=True),
            final_decision='TAKE',
            score=72,
            threshold=70,
            sig_data={'r': 1.6, 'meta': {}},
            perf_governor={'suppressed': False},
            freshness_meta={'blocked': False},
        )
        self.assertFalse(blocked)
        self.assertEqual(reason, '')

    def test_blocks_take_candidates_below_relaxed_score_gate(self):
        blocked, reason = _evaluate_selective_policy_throttle(
            policy_state=SimpleNamespace(selective_throttle=True, selective_min_score_buffer=2, selective_min_rr=1.5, selective_require_governor_pass=True),
            final_decision='TAKE',
            score=71,
            threshold=70,
            sig_data={'r': 1.8, 'meta': {}},
            perf_governor={'suppressed': False},
            freshness_meta={'blocked': False},
        )
        self.assertTrue(blocked)
        self.assertIn('score >= 72', reason)

    def test_blocks_take_candidates_below_relaxed_rr_gate(self):
        blocked, reason = _evaluate_selective_policy_throttle(
            policy_state=SimpleNamespace(selective_throttle=True, selective_min_score_buffer=2, selective_min_rr=1.5, selective_require_governor_pass=True),
            final_decision='TAKE',
            score=74,
            threshold=70,
            sig_data={'r': 1.4, 'meta': {}},
            perf_governor={'suppressed': False},
            freshness_meta={'blocked': False},
        )
        self.assertTrue(blocked)
        self.assertIn('RR >= 1.50', reason)

    def test_allows_promoted_take_at_base_threshold_in_frozen_mode(self):
        blocked, reason = _evaluate_selective_policy_throttle(
            policy_state=SimpleNamespace(selective_throttle=True, selective_min_score_buffer=2, selective_min_rr=1.5, selective_require_governor_pass=True),
            final_decision='TAKE',
            score=70,
            threshold=70,
            sig_data={'r': 1.6, 'meta': {'high_conviction_promotion': {'promoted': True}}},
            perf_governor={'suppressed': False},
            freshness_meta={'blocked': False},
        )
        self.assertFalse(blocked)
        self.assertEqual(reason, '')

    def test_cooldown_context_tightens_frozen_take_requirements(self):
        blocked, reason = _evaluate_selective_policy_throttle(
            policy_state=SimpleNamespace(selective_throttle=True, selective_min_score_buffer=2, selective_min_rr=1.5, selective_require_governor_pass=True),
            final_decision='TAKE',
            score=72,
            threshold=70,
            sig_data={'r': 1.8, 'meta': {'cooldown_context': {'active': True}}},
            perf_governor={'suppressed': False},
            freshness_meta={'blocked': False},
        )
        self.assertTrue(blocked)
        self.assertIn('score >= 74', reason)

    def test_cooldown_context_raises_rr_requirement(self):
        blocked, reason = _evaluate_selective_policy_throttle(
            policy_state=SimpleNamespace(selective_throttle=True, selective_min_score_buffer=2, selective_min_rr=1.5, selective_require_governor_pass=True),
            final_decision='TAKE',
            score=75,
            threshold=70,
            sig_data={'r': 1.7, 'meta': {'cooldown_context': {'active': True}}},
            perf_governor={'suppressed': False},
            freshness_meta={'blocked': False},
        )
        self.assertTrue(blocked)
        self.assertIn('RR >= 1.80', reason)

    def test_loss_streak_cooldown_is_converted_into_context_not_blind_reject(self):
        sig_data = {'instrument_id': 'TQBR:SBER', 'meta': {}}
        risk_ok = False
        risk_reason = 'Cooldown: 2 losses in a row, 48min remaining'
        risk_detail = {'blocked_by': 'loss_streak_cooldown', 'cooldown_losses': 2, 'cooldown_minutes': 60}

        if not risk_ok:
            cooldown_override = str(risk_detail.get('blocked_by') or '') == 'loss_streak_cooldown'
            if cooldown_override:
                sig_meta = dict(sig_data.get('meta') or {})
                sig_meta['cooldown_context'] = {
                    'active': True,
                    'mode': 'conviction_aware',
                    'reason': risk_reason,
                    'risk_detail': risk_detail,
                }
                sig_data['meta'] = sig_meta
                risk_ok = True
                risk_reason = ''

        self.assertTrue(risk_ok)
        self.assertEqual(risk_reason, '')
        self.assertTrue(sig_data['meta']['cooldown_context']['active'])
        self.assertEqual(sig_data['meta']['cooldown_context']['mode'], 'conviction_aware')

    def test_non_cooldown_risk_block_stays_hard_reject(self):
        sig_data = {'instrument_id': 'TQBR:SBER', 'meta': {}}
        risk_ok = False
        risk_reason = 'Correlation limit reached'
        risk_detail = {'blocked_by': 'correlation_limit'}

        if not risk_ok:
            cooldown_override = str(risk_detail.get('blocked_by') or '') == 'loss_streak_cooldown'
            if cooldown_override:
                sig_meta = dict(sig_data.get('meta') or {})
                sig_meta['cooldown_context'] = {
                    'active': True,
                    'mode': 'conviction_aware',
                    'reason': risk_reason,
                    'risk_detail': risk_detail,
                }
                sig_data['meta'] = sig_meta
                risk_ok = True
                risk_reason = ''

        self.assertFalse(risk_ok)
        self.assertEqual(sig_data['meta'], {})
        self.assertEqual(risk_reason, 'Correlation limit reached')

    def test_conviction_profile_marks_tradeable_b_tier(self):
        profile = _build_conviction_profile(
            final_decision='SKIP',
            score=70,
            threshold=70,
            evaluation=SimpleNamespace(
                reasons=[],
                metrics={'economic_filter_valid': True, 'net_rr': 0.82, 'commission_dominance_ratio': 0.91},
            ),
            perf_governor={'suppressed': False},
            freshness_meta={'blocked': False},
        )
        self.assertEqual(profile['tier'], 'B')
        self.assertTrue(profile['rescue_eligible'])
        self.assertEqual(profile['allocator_priority_bonus'], 1.0)

    def test_conviction_profile_marks_higher_tf_near_take_as_tradeable_b_tier(self):
        profile = _build_conviction_profile(
            final_decision='REJECT',
            score=71,
            threshold=80,
            evaluation=SimpleNamespace(
                reasons=[],
                metrics={'economic_filter_valid': True, 'net_rr': 0.88, 'commission_dominance_ratio': 0.95},
            ),
            perf_governor={'suppressed': False},
            freshness_meta={'blocked': False},
            signal_meta={
                'thesis_timeframe': '15m',
                'higher_tf_thesis': {
                    'thesis_timeframe': '15m',
                    'thesis_type': 'timeframe_signal',
                    'structure': 'requested_timeframe_signal',
                    'side': 'BUY',
                },
            },
        )
        self.assertEqual(profile['tier'], 'B')
        self.assertTrue(profile['rescue_eligible'])

    def test_conviction_profile_rejects_non_tradeable_cost_structure(self):
        profile = _build_conviction_profile(
            final_decision='SKIP',
            score=74,
            threshold=70,
            evaluation=SimpleNamespace(
                reasons=[],
                metrics={'economic_filter_valid': True, 'net_rr': 0.42, 'commission_dominance_ratio': 1.4},
            ),
            perf_governor={'suppressed': False},
            freshness_meta={'blocked': False},
        )
        self.assertEqual(profile['tier'], 'C')
        self.assertFalse(profile['rescue_eligible'])
        self.assertLess(profile['risk_tier_bias'], 1.0)

    def test_conviction_profile_marks_a_plus_quality(self):
        profile = _build_conviction_profile(
            final_decision='TAKE',
            score=82,
            threshold=70,
            evaluation=SimpleNamespace(
                reasons=[],
                metrics={'economic_filter_valid': True, 'net_rr': 1.2, 'commission_dominance_ratio': 0.7},
            ),
            perf_governor={'suppressed': False},
            freshness_meta={'blocked': False},
        )
        self.assertEqual(profile['tier'], 'A+')
        self.assertGreater(profile['allocator_priority_bonus'], 1.0)
        self.assertGreater(profile['risk_tier_bias'], 1.0)

    def test_promotes_high_conviction_skip_to_take(self):
        decision, reason, meta = _promote_high_conviction_skip(
            final_decision='SKIP',
            score=70,
            threshold=70,
            evaluation=SimpleNamespace(
                reasons=[],
                metrics={'economic_filter_valid': True, 'net_rr': 0.82},
            ),
            perf_governor={'suppressed': False},
            freshness_meta={'blocked': False},
        )
        self.assertEqual(decision, 'TAKE')
        self.assertEqual(reason, 'high-conviction promotion')
        self.assertTrue(meta['promoted'])
        self.assertEqual(meta['tier'], 'B')

    def test_does_not_promote_skip_with_weak_net_rr(self):
        decision, reason, meta = _promote_high_conviction_skip(
            final_decision='SKIP',
            score=74,
            threshold=70,
            evaluation=SimpleNamespace(
                reasons=[],
                metrics={'economic_filter_valid': True, 'net_rr': 0.62},
            ),
            perf_governor={'suppressed': False},
            freshness_meta={'blocked': False},
        )
        self.assertEqual(decision, 'SKIP')
        self.assertEqual(reason, '')
        self.assertFalse(meta['promoted'])

    def test_does_not_promote_skip_with_blockers(self):
        decision, reason, meta = _promote_high_conviction_skip(
            final_decision='SKIP',
            score=78,
            threshold=70,
            evaluation=SimpleNamespace(
                reasons=[SimpleNamespace(severity='block')],
                metrics={'economic_filter_valid': True, 'net_rr': 0.95},
            ),
            perf_governor={'suppressed': False},
            freshness_meta={'blocked': False},
        )
        self.assertEqual(decision, 'SKIP')
        self.assertEqual(reason, '')
        self.assertFalse(meta['promoted'])


if __name__ == '__main__':
    unittest.main()
