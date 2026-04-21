import unittest
from types import SimpleNamespace

from apps.worker.processor_support import _build_conviction_profile, _build_pending_review_outcome_seed, _build_pre_persist_review_enrichment, _build_review_readiness_seed, _evaluate_selective_policy_throttle, _promote_high_conviction_skip, _reconcile_review_readiness, _should_queue_capacity_blocked_candidate, _should_relax_governor_suppression


class ProcessorSelectiveThrottleTests(unittest.TestCase):
    def test_relaxes_governor_suppression_for_tradeable_higher_tf_candidate(self):
        relaxed = _should_relax_governor_suppression(
            sig_meta={
                'thesis_timeframe': '15m',
                'higher_tf_thesis': {'thesis_timeframe': '15m', 'thesis_type': 'timeframe_signal'},
                'conviction_profile': {'tier': 'B', 'score_gap': -9},
            },
            perf_governor={'suppressed': True},
        )
        self.assertTrue(relaxed)

    def test_does_not_relax_governor_for_weak_candidate(self):
        relaxed = _should_relax_governor_suppression(
            sig_meta={
                'thesis_timeframe': '15m',
                'higher_tf_thesis': {'thesis_timeframe': '15m', 'thesis_type': 'timeframe_signal'},
                'conviction_profile': {'tier': 'C', 'score_gap': -19},
            },
            perf_governor={'suppressed': True},
        )
        self.assertFalse(relaxed)

    def test_review_readiness_seed_preserves_higher_tf_context(self):
        seed = _build_review_readiness_seed({
            'side': 'SELL',
            'entry': 100.0,
            'r': 1.8,
            'meta': {
                'strategy_name': 'breakout',
                'thesis_timeframe': '15m',
                'timeframe_selection_reason': 'requested',
                'higher_tf_thesis': {
                    'thesis_timeframe': '15m',
                    'thesis_type': 'continuation',
                    'structure': 'near_low_break_continuation',
                    'side': 'SELL',
                },
            },
        })
        self.assertEqual(seed['thesis_timeframe'], '15m')
        self.assertEqual(seed['selection_reason'], 'requested')
        self.assertEqual(seed['thesis_type'], 'continuation')
        self.assertEqual(seed['structure'], 'near_low_break_continuation')
        self.assertEqual(seed['initial_rr'], 1.8)

    def test_pre_persist_review_enrichment_marks_strong_higher_tf_candidate(self):
        enrichment = _build_pre_persist_review_enrichment({
            'side': 'SELL',
            'r': 2.0,
            'meta': {
                'strategy_name': 'breakout',
                'thesis_timeframe': '15m',
                'timeframe_selection_reason': 'requested',
                'higher_tf_thesis': {
                    'thesis_timeframe': '15m',
                    'thesis_type': 'continuation',
                    'structure': 'near_low_break_continuation',
                    'side': 'SELL',
                },
            },
        }, block_reason='selective throttle keeps only TAKE candidates during frozen mode')
        self.assertEqual(enrichment['conviction_profile']['tier'], 'B')
        self.assertTrue(enrichment['conviction_profile']['tradable'])
        self.assertEqual(enrichment['review_readiness']['thesis_timeframe'], '15m')

    def test_pending_review_outcome_seed_marks_auto_paper_higher_tf_candidate(self):
        seed = _build_pending_review_outcome_seed({
            'side': 'BUY',
            'r': 2.4,
            'meta': {
                'strategy_name': 'breakout',
                'thesis_timeframe': '15m',
                'timeframe_selection_reason': 'requested',
                'execution_timeframe': '15m',
                'higher_tf_thesis': {
                    'thesis_timeframe': '15m',
                    'thesis_type': 'timeframe_signal',
                    'structure': 'requested_timeframe_signal',
                    'side': 'BUY',
                },
            },
        }, trade_mode='auto_paper')
        self.assertTrue(seed['approval_candidate'])
        self.assertEqual(seed['approval_reason'], 'higher_tf_strong_pending_candidate')
        self.assertGreaterEqual(seed['queue_priority'], 80)

    def test_pending_review_outcome_seed_keeps_review_only_when_not_strong_enough(self):
        seed = _build_pending_review_outcome_seed({
            'side': 'BUY',
            'r': 1.4,
            'meta': {
                'strategy_name': 'breakout',
                'thesis_timeframe': '5m',
                'timeframe_selection_reason': 'fallback',
                'execution_timeframe': '1m',
                'higher_tf_thesis': {
                    'thesis_timeframe': '5m',
                    'thesis_type': 'timeframe_signal',
                    'structure': 'fallback_timeframe_signal',
                    'side': 'BUY',
                },
            },
        }, trade_mode='auto_paper')
        self.assertFalse(seed['approval_candidate'])
        self.assertEqual(seed['approval_reason'], 'review_only_pending_candidate')
        self.assertLess(seed['queue_priority'], 80)

    def test_reconcile_review_readiness_demotes_candidate_after_hard_blockers(self):
        reconciled = _reconcile_review_readiness(
            {'approval_candidate': True, 'approval_reason': 'higher_tf_strong_pending_candidate'},
            {'tier': 'C', 'has_blockers': True, 'economic_filter_valid': False},
        )
        self.assertFalse(reconciled['approval_candidate'])
        self.assertEqual(reconciled['approval_reason'], 'demoted_after_decision_flow')

    def test_queues_capacity_blocked_requested_15m_candidate_for_review(self):
        should_queue = _should_queue_capacity_blocked_candidate(
            {
                'r': 2.4,
                'meta': {
                    'thesis_timeframe': '15m',
                    'timeframe_selection_reason': 'requested',
                    'higher_tf_thesis': {'thesis_timeframe': '15m', 'thesis_type': 'timeframe_signal'},
                },
            },
            block_reason='Max positions reached (4/4)',
        )
        self.assertTrue(should_queue)

    def test_does_not_queue_weak_capacity_blocked_candidate(self):
        should_queue = _should_queue_capacity_blocked_candidate(
            {
                'r': 1.2,
                'meta': {
                    'thesis_timeframe': '1m',
                    'timeframe_selection_reason': 'execution_fallback',
                },
            },
            block_reason='Max positions reached (4/4)',
        )
        self.assertFalse(should_queue)

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

    def test_allows_promoted_requested_15m_candidate_with_moderate_gap_in_frozen_mode(self):
        blocked, reason = _evaluate_selective_policy_throttle(
            policy_state=SimpleNamespace(selective_throttle=True, selective_min_score_buffer=2, selective_min_rr=1.5, selective_require_governor_pass=True),
            final_decision='TAKE',
            score=68,
            threshold=86,
            sig_data={
                'r': 2.4,
                'meta': {
                    'thesis_timeframe': '15m',
                    'timeframe_selection_reason': 'requested',
                    'high_conviction_promotion': {'promoted': True},
                    'conviction_profile': {'tier': 'B', 'score_gap': -18, 'economic_filter_valid': True, 'has_blockers': False},
                    'higher_tf_thesis': {
                        'thesis_timeframe': '15m',
                        'thesis_type': 'timeframe_signal',
                        'structure': 'requested_timeframe_signal',
                        'side': 'SELL',
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

    def test_conviction_profile_marks_requested_15m_candidate_tradeable_with_moderate_gap(self):
        profile = _build_conviction_profile(
            final_decision='REJECT',
            score=68,
            threshold=96,
            evaluation=SimpleNamespace(
                reasons=[],
                metrics={'economic_filter_valid': True, 'net_rr': 1.31, 'commission_dominance_ratio': 0.6},
            ),
            perf_governor={'suppressed': False},
            freshness_meta={'blocked': False},
            signal_meta={
                'thesis_timeframe': '15m',
                'timeframe_selection_reason': 'requested',
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
