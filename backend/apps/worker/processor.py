"""
P4-08: SignalProcessor — strategy + DE + AI + save + execution pipeline.

P4-01: AIMode controls how AI merges with DE decision
P4-02: InternetCollector provides news/macro context (parallel with DE)
P4-07: Every AI call is logged to ai_decisions table
"""
from __future__ import annotations

import asyncio
import resource
import logging
import time
import uuid
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy.orm import Session

from apps.worker.decision_engine.engine import DecisionEngine
from apps.worker.decision_engine.types import Decision, MarketSnapshot
from apps.worker.ai.historical import HistoricalContextAnalyzer
from apps.worker.ai.fast_path import evaluate_ai_fast_path
from core.config import get_token, settings as runtime_config
from core.events.bus import bus
from core.execution.controls import prefers_paper_execution
from core.execution.paper import PaperExecutionEngine
from core.metrics import record_signal, record_risk_block
from core.risk.manager import RiskManager
from core.services.symbol_adaptive import build_symbol_plan, get_symbol_diagnostics, get_symbol_profile
from core.services.event_regime import analyze_event_regime, persist_event_regime
from core.services.geometry_optimizer import optimize_signal_geometry, should_retry_geometry
from core.services.timeframe_engine import align_signal_to_execution, detect_trend, normalize_timeframe, resample_candles, timeframe_rank
from core.services.signal_freshness import apply_signal_freshness
from core.services.cognitive_layer import build_cognitive_layer_payload
from core.services.degrade_policy import evaluate_degrade_policy
from core.services.performance_governor import evaluate_signal_governor
from core.ml.runtime import evaluate_ml_overlay
from core.services.signal_execution_uow import SignalExecutionUnitOfWork
from core.services.portfolio_optimizer import build_portfolio_optimizer_overlay
from core.services.sector_filters import apply_sector_overrides, get_instrument_sector_payload
from core.sentiment.repo import build_prompt_sentiment_context
from core.storage.repos import settings as settings_repo
from core.storage.repos import signals as signal_repo
from core.storage.repos.ai_repo import save_ai_decision
from core.storage.decision_log_utils import append_decision_log_best_effort
from core.strategy.base import BaseStrategy
from apps.worker.correlation_map import build_correlation_candles_map

logger = logging.getLogger(__name__)


def _elapsed_ms(start: float) -> int:
    return max(0, int(round((time.perf_counter() - start) * 1000)))


from apps.worker.processor_support import (
    _apply_event_regime,
    _json_safe,
    _append_decision_log,
    _build_conviction_profile,
    _build_merge_payload,
    _build_pre_persist_candidate_payload,
    _build_signal_pipeline_payload,
    _apply_geometry_pass,
    _build_candles_summary,
    _build_pre_persist_review_enrichment,
    _build_pending_review_outcome_seed,
    _reconcile_review_readiness,
    _build_review_readiness_seed,
    _should_queue_capacity_blocked_candidate,
    _should_relax_governor_suppression,
    _evaluate_selective_policy_throttle,
    _promote_high_conviction_skip,
    _candidate_timeframes,
    _run_strategy_timeframe_search,
    _attach_execution_geometry,
    _snapshot_for_history,
)


class SignalProcessor:
    def __init__(self, strategy: BaseStrategy, internet_collector=None, aggregator=None):
        self.strategy = strategy
        self._internet = internet_collector  # P4-02: optional InternetCollector
        self._aggregator = aggregator        # P5-06: for correlation candles_map

    async def _prepare_signal_context(self, ticker: str, candle_history: list[dict], db: Session, adaptive_plan: dict | None = None) -> dict | None:
        settings = settings_repo.get_settings(db)
        pending_ttl_sec = int(getattr(settings, 'pending_review_ttl_sec', 900) or 900)
        signal_repo.expire_stale_pending_signals(db, ticker, ttl_sec=pending_ttl_sec)
        if len(candle_history) < self.strategy.lookback:
            logger.debug("%s: history too short (%d < %d)", ticker, len(candle_history), self.strategy.lookback)
            return None

        if adaptive_plan is None and candle_history:
            try:
                built_plan = build_symbol_plan(db, ticker, candle_history, settings)
                adaptive_plan = built_plan.to_meta() if built_plan else None
            except Exception as exc:
                logger.warning("%s: adaptive plan fallback build failed: %s", ticker, exc)

        confirmation_tf = normalize_timeframe((adaptive_plan or {}).get('confirmation_timeframe') or getattr(settings, 'higher_timeframe', '15m') or '15m', '15m')
        confirmation_history = resample_candles(candle_history, confirmation_tf) if confirmation_tf != '1m' else list(candle_history)

        # 1. Strategy signal on adaptive timeframe with fallback search
        sig_data, analysis_history, timeframe_meta = _run_strategy_timeframe_search(
            self.strategy,
            ticker,
            candle_history,
            adaptive_plan,
            settings,
        )
        if not sig_data:
            logger.debug("Strategy analyzed %s: signal=none history_len=%d requested_tf=%s", ticker, len(candle_history), timeframe_meta.get('requested_timeframe'))
            return None

        execution_tf = normalize_timeframe((adaptive_plan or {}).get('execution_timeframe') or (sig_data.get('meta') or {}).get('execution_timeframe') or '1m', '1m')
        execution_history = resample_candles(candle_history, execution_tf) if execution_tf != '1m' else list(candle_history)

        sig_data = _attach_execution_geometry(
            sig_data,
            execution_history=execution_history,
            confirmation_history=confirmation_history,
            adaptive_plan=adaptive_plan,
        )

        logger.info(
            "Strategy analyzed %s: signal=found side=%s entry=%.4f analysis_tf=%s exec_tf=%s history_len=%d",
            ticker,
            sig_data["side"],
            sig_data["entry"],
            (sig_data.get('meta') or {}).get('analysis_timeframe'),
            (sig_data.get('meta') or {}).get('execution_timeframe'),
            len(analysis_history),
        )

        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        sig_meta = dict(sig_data.get("meta") or {})
        sector_payload = get_instrument_sector_payload(ticker)
        sig_meta['sector'] = sector_payload.get('sector_id')
        sig_meta['sector_filters'] = apply_sector_overrides(settings, ticker)
        if adaptive_plan:
            sig_meta["adaptive_plan"] = adaptive_plan
            if adaptive_plan.get("strategy_name"):
                sig_meta["strategy_name"] = adaptive_plan.get("strategy_name")
            if adaptive_plan.get("strategy_source"):
                sig_meta["strategy_source"] = adaptive_plan.get("strategy_source")
        sig_meta.setdefault("strategy_name", sig_meta.get("strategy") or getattr(self.strategy, "name", None))
        sig_meta.setdefault("strategy_source", 'global' if ',' not in str(getattr(self.strategy, 'name', '') or '') else 'regime')
        sig_meta["trace_id"] = trace_id
        sig_meta["multi_timeframe"] = {
            'requested_timeframe': timeframe_meta.get('requested_timeframe'),
            'selected_timeframe': timeframe_meta.get('selected_timeframe'),
            'candidates': timeframe_meta.get('candidates') or [],
        }
        sig_data["meta"] = sig_meta

        sig_data, _ = _apply_geometry_pass(
            db=db,
            ticker=ticker,
            sig_data=sig_data,
            candles=analysis_history,
            settings=settings,
            adaptive_plan=adaptive_plan,
            phase='initial',
        )

        return {
            "ticker": ticker,
            "candle_history": candle_history,
            "settings": settings,
            "adaptive_plan": adaptive_plan,
            "analysis_history": analysis_history,
            "confirmation_history": confirmation_history,
            "execution_history": execution_history,
            "sig_data": sig_data,
            "trace_id": trace_id,
            "timeframe_meta": timeframe_meta,
        }

    def _apply_risk_and_sizing(self, db: Session, context: dict) -> dict | None:
        ticker = context["ticker"]
        candle_history = context["candle_history"]
        settings = context["settings"]
        adaptive_plan = context["adaptive_plan"]
        sig_data = context["sig_data"]
        trace_id = context["trace_id"]
        # Memory logging
        import resource
        mem_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        logger.debug("%s: risk_and_sizing memory before: %d KB", ticker, mem_before)
        policy_state = evaluate_degrade_policy(db, settings)
        if policy_state.state == 'frozen' and policy_state.block_new_entries and not bool(getattr(policy_state, 'selective_throttle', False)):
            risk_reason = f"Automatic freeze policy blocked new entries: {'; '.join(policy_state.reasons)}"
            logger.warning('%s: %s', ticker, risk_reason)
            record_risk_block('auto_freeze_policy')
            _append_decision_log(
                db,
                log_type='auto_runtime_guard',
                message=f"{ticker} frozen by automatic degrade/freeze policy",
                payload={'instrument_id': ticker, 'trace_id': trace_id, 'policy': policy_state.to_meta(), 'signal': _json_safe(sig_data)},
            )
            sig_meta = dict(sig_data.get('meta') or {})
            sig_meta['auto_policy'] = policy_state.to_meta()
            sig_meta['pre_persist_block'] = {
                'code': 'auto_freeze_policy',
                'reason': risk_reason,
                'stage': 'policy_blocked',
                'ts': int(time.time() * 1000),
            }
            sig_meta['candidate_snapshot'] = _build_pre_persist_candidate_payload(
                ticker=ticker,
                sig_data=sig_data,
                strategy_name=(adaptive_plan or {}).get('strategy_name'),
                stage='policy_blocked',
                block_code='auto_freeze_policy',
                block_reason=risk_reason,
            )
            sig_meta['cognitive_layer'] = {
                'status': 'blocked_before_reasoning',
                'final_decision': 'REJECT',
                'strategy': (adaptive_plan or {}).get('strategy_name') or sig_meta.get('strategy_name') or sig_meta.get('strategy'),
                'regime': (adaptive_plan or {}).get('regime'),
                'operator_summary': {
                    'overall_confidence': None,
                    'contradiction_count': 0,
                    'highest_risk_axis': 'policy',
                    'bounded': True,
                    'blocked_before_reasoning': True,
                },
                'contradictions': ['policy_freeze_block'],
            }
            sig_meta['final_decision'] = 'REJECT'
            sig_meta['decision_merge'] = {
                'pre_ai_final_decision': 'REJECT',
                'event_merge_reason': risk_reason,
                'freshness_reason': None,
                'event_adjusted_score': None,
            }
            sig_meta.update(_build_pre_persist_review_enrichment(sig_data, block_reason=risk_reason))
            sig_data['meta'] = sig_meta
            sig_data['status'] = 'rejected'
            sig_data['reason'] = risk_reason
            context['sig_data'] = sig_data
            context['policy_state'] = policy_state
            context['pre_persist_blocked'] = True
            context['pre_persist_block_reason'] = risk_reason
            return context
        # 2. Risk check (with correlation candles_map if aggregator available)
        risk = RiskManager(db)
        candles_map = build_correlation_candles_map(db, self._aggregator, ticker, candle_history)
        risk_ok, risk_reason = risk.check_new_signal(sig_data, candles_map=candles_map)
        if not risk_ok:
            risk_detail = dict(getattr(risk, 'last_check_details', {}) or {})
            cooldown_override = str(risk_detail.get('blocked_by') or '') == 'loss_streak_cooldown'
            if cooldown_override:
                logger.info("%s: cooldown-aware proceed after risk warning — %s", ticker, risk_reason)
                sig_meta = dict(sig_data.get('meta') or {})
                sig_meta['cooldown_context'] = {
                    'active': True,
                    'mode': 'conviction_aware',
                    'reason': risk_reason,
                    'risk_detail': _json_safe(risk_detail),
                }
                sig_data['meta'] = sig_meta
                _append_decision_log(
                    db,
                    log_type="cooldown_aware_proceed",
                    message=f"{ticker} proceeded under conviction-aware cooldown: {risk_reason}",
                    payload={
                        "instrument_id": ticker,
                        "risk_reason": risk_reason,
                        "risk_detail": _json_safe(risk_detail),
                        "signal": _json_safe(sig_data),
                    },
                )
                risk_ok = True
                risk_reason = ''
            if not risk_ok:
                logger.info("%s: blocked by risk — %s", ticker, risk_reason)
                record_risk_block(risk_reason)
                _append_decision_log(
                    db,
                    log_type="signal_risk_block",
                    message=f"{ticker} blocked by risk: {risk_reason}",
                    payload={"instrument_id": ticker, "risk_reason": risk_reason, "risk_detail": getattr(risk, "last_check_details", None), "signal": _json_safe(sig_data)},
                )
                sig_meta = dict(sig_data.get('meta') or {})
                sig_meta['pre_persist_block'] = {
                    'code': 'risk_block',
                    'reason': risk_reason,
                    'stage': 'risk_blocked',
                    'ts': int(time.time() * 1000),
                    'risk_detail': _json_safe(getattr(risk, 'last_check_details', None)),
                }
                sig_meta['candidate_snapshot'] = _build_pre_persist_candidate_payload(
                    ticker=ticker,
                    sig_data=sig_data,
                    strategy_name=(adaptive_plan or {}).get('strategy_name'),
                    stage='risk_blocked',
                    block_code='risk_block',
                    block_reason=risk_reason,
                )
                sig_meta['final_decision'] = 'REJECT'
                sig_meta['decision_merge'] = {
                    'pre_ai_final_decision': 'REJECT',
                    'event_merge_reason': risk_reason,
                    'freshness_reason': None,
                    'event_adjusted_score': None,
                }
                sig_meta.update(_build_pre_persist_review_enrichment(sig_data, block_reason=risk_reason))
                sig_data['meta'] = sig_meta
                sig_data['status'] = 'pending_review' if _should_queue_capacity_blocked_candidate(sig_data, block_reason=risk_reason) else 'rejected'
                sig_data['reason'] = risk_reason
                context['sig_data'] = sig_data
                context['risk'] = risk
                context['pre_persist_blocked'] = True
                context['pre_persist_block_reason'] = risk_reason
                return context

        # 3. Position sizing
        sig_meta = dict(sig_data.get('meta') or {})
        optimizer_overlay = build_portfolio_optimizer_overlay(db, settings, sig_data)
        optimizer_mult = float((optimizer_overlay or {}).get('optimizer_risk_multiplier') or 1.0)
        base_risk_mult = float((adaptive_plan or {}).get("risk_multiplier") or 1.0)
        policy_mult = float(getattr(policy_state, 'risk_multiplier_override', 1.0) or 1.0)
        conviction_profile = dict(sig_meta.get('conviction_profile') or {})
        conviction_risk_bias = float(conviction_profile.get('risk_tier_bias') or 1.0)
        conviction_risk_bias = max(0.9, min(1.08, conviction_risk_bias))
        cooldown_context = dict(sig_meta.get('cooldown_context') or {})
        cooldown_risk_bias = 1.0
        if bool(cooldown_context.get('active')):
            tier = str(conviction_profile.get('tier') or 'C')
            if tier == 'A+':
                cooldown_risk_bias = 0.72
            elif tier == 'A':
                cooldown_risk_bias = 0.62
            elif tier == 'B':
                cooldown_risk_bias = 0.45
            else:
                cooldown_risk_bias = 0.0
        combined_risk_mult = max(0.0, base_risk_mult * optimizer_mult * policy_mult * conviction_risk_bias)
        combined_risk_mult = max(0.0, combined_risk_mult * cooldown_risk_bias)
        sig_data["size"] = float(risk.calculate_position_size(
            entry=sig_data["entry"], sl=sig_data["sl"], lot_size=1,
            risk_multiplier=combined_risk_mult,
        ))
        sig_meta['portfolio_optimizer'] = dict(optimizer_overlay or {})
        sig_meta['sector_filters'] = apply_sector_overrides(settings, ticker)
        sig_meta['risk_sizing'] = dict(getattr(risk, 'last_size_details', {}) or {})
        sig_meta['risk_sizing']['base_signal_risk_multiplier'] = round(base_risk_mult, 4)
        sig_meta['risk_sizing']['optimizer_risk_multiplier'] = round(optimizer_mult, 4)
        sig_meta['risk_sizing']['auto_policy_risk_multiplier'] = round(policy_mult, 4)
        sig_meta['risk_sizing']['conviction_risk_multiplier'] = round(conviction_risk_bias, 4)
        sig_meta['risk_sizing']['cooldown_risk_multiplier'] = round(cooldown_risk_bias, 4)
        sig_meta['risk_sizing']['combined_signal_risk_multiplier'] = round(combined_risk_mult, 4)
        sig_meta['auto_policy'] = policy_state.to_meta()
        sig_data['meta'] = sig_meta
        if abs(optimizer_mult - 1.0) >= 0.01 or (optimizer_overlay or {}).get('trim_candidates'):
            _append_decision_log(
                db,
                log_type='portfolio_optimizer_overlay',
                message=f"{ticker} portfolio optimizer overlay applied",
                payload={'instrument_id': ticker, 'trace_id': trace_id, 'optimizer': _json_safe(optimizer_overlay or {}), 'combined_risk_multiplier': combined_risk_mult},
            )
        if policy_state.state == 'degraded':
            _append_decision_log(
                db,
                log_type='auto_runtime_guard',
                message=f"{ticker} degraded by automatic policy",
                payload={'instrument_id': ticker, 'trace_id': trace_id, 'policy': policy_state.to_meta()},
            )
        if float((getattr(risk, 'last_size_details', {}) or {}).get('portfolio_risk_multiplier') or 1.0) < 0.999:
            _append_decision_log(
                db,
                log_type='pm_risk_throttle',
                message=f"{ticker} size throttled by PM overlay",
                payload={'instrument_id': ticker, 'trace_id': trace_id, 'risk_sizing': _json_safe(getattr(risk, 'last_size_details', {}) or {})},
            )
        if sig_data["size"] <= 0:
            risk_reason = "No size left after exposure caps"
            record_risk_block(risk_reason)
            _append_decision_log(
                db,
                log_type="signal_risk_block",
                message=f"{ticker} blocked by risk: {risk_reason}",
                payload={"instrument_id": ticker, "risk_reason": risk_reason, "risk_detail": getattr(risk, "last_check_details", None), "signal": _json_safe(sig_data)},
            )
            sig_meta = dict(sig_data.get('meta') or {})
            sig_meta['pre_persist_block'] = {
                'code': 'zero_size',
                'reason': risk_reason,
                'stage': 'risk_blocked',
                'ts': int(time.time() * 1000),
                'risk_detail': _json_safe(getattr(risk, 'last_check_details', None)),
            }
            sig_meta['candidate_snapshot'] = _build_pre_persist_candidate_payload(
                ticker=ticker,
                sig_data=sig_data,
                strategy_name=(adaptive_plan or {}).get('strategy_name'),
                stage='risk_blocked',
                block_code='zero_size',
                block_reason=risk_reason,
            )
            sig_meta['final_decision'] = 'REJECT'
            sig_meta['decision_merge'] = {
                'pre_ai_final_decision': 'REJECT',
                'event_merge_reason': risk_reason,
                'freshness_reason': None,
                'event_adjusted_score': None,
            }
            sig_meta.update(_build_pre_persist_review_enrichment(sig_data, block_reason=risk_reason))
            sig_data['meta'] = sig_meta
            sig_data['status'] = 'pending_review' if _should_queue_capacity_blocked_candidate(sig_data, block_reason=risk_reason) else 'rejected'
            sig_data['reason'] = risk_reason
            context['sig_data'] = sig_data
            context['risk'] = risk
            context['pre_persist_blocked'] = True
            context['pre_persist_block_reason'] = risk_reason
            return context

        # 4. Check for existing pending signal
        pending_ttl_sec = int(getattr(settings, 'pending_review_ttl_sec', 900) or 900)
        max_pending_per_symbol = int(getattr(settings, 'max_pending_per_symbol', 1) or 1)
        sig_meta = dict(sig_data.get('meta') or {})
        sig_meta.setdefault('review_readiness', _build_pending_review_outcome_seed(sig_data, trade_mode=(getattr(settings, 'trade_mode', None) or 'review')))
        sig_data['meta'] = sig_meta
        if signal_repo.count_pending_signals(db, ticker, ttl_sec=pending_ttl_sec, max_pending=max_pending_per_symbol) >= max_pending_per_symbol:
            incoming_priority = int(((sig_data.get('meta') or {}).get('review_readiness') or {}).get('queue_priority') or 0)
            if not signal_repo.replace_weaker_pending_signal(db, ticker, incoming_priority=incoming_priority, ttl_sec=pending_ttl_sec):
                logger.debug("%s: already has active pending signal", ticker)
                return None

        context["sig_data"] = sig_data
        context["risk"] = risk
        context['policy_state'] = policy_state
        context['combined_risk_mult'] = combined_risk_mult
        # Memory logging after
        mem_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        logger.debug("%s: risk_and_sizing memory after: %d KB (delta: %d KB)", ticker, mem_after, mem_after - mem_before)
        return context

    def _persist_signal(self, db: Session, context: dict) -> dict | None:
        ticker = context["ticker"]
        sig_data = context["sig_data"]
        trace_id = context["trace_id"]
        meta = dict(sig_data.get('meta') or {})
        meta.setdefault('review_readiness', _build_review_readiness_seed(sig_data))
        if str(sig_data.get('status') or '') == 'pending_review':
            trade_mode = (getattr(context.get('settings'), 'trade_mode', None) or 'review')
            meta['review_readiness'] = _build_pending_review_outcome_seed(sig_data, trade_mode=trade_mode)
        sig_data['meta'] = meta
        # 5. Persist signal
        try:
            signal_orm = signal_repo.create_signal(db, sig_data, commit=False)
        except Exception as e:
            logger.error("%s: failed to create signal — %s", ticker, e, exc_info=True)
            return None

        _append_decision_log(
            db,
            log_type="signal_created",
            message=f"Signal created for {ticker}",
            payload={"signal_id": signal_orm.id, "instrument_id": ticker, "trace_id": trace_id, "signal": _json_safe(sig_data)},
        )

        db.commit()
        db.refresh(signal_orm)

        context["signal_orm"] = signal_orm
        return context

    async def _run_decision_flow(self, db: Session, context: dict) -> dict | None:
        ticker = context["ticker"]
        sig_data = context["sig_data"]
        signal_orm = context["signal_orm"]
        analysis_history = context["analysis_history"]
        confirmation_history = context["confirmation_history"]
        execution_history = context["execution_history"]
        candle_history = context["candle_history"]
        settings = context["settings"]
        adaptive_plan = context["adaptive_plan"]
        trace_id = context["trace_id"]
        risk = context.get("risk")
        policy_state = context.get('policy_state')
        decision_timing: dict[str, int] = {}
        # 6. Load settings
        settings = settings_repo.get_settings(db)
        if not settings:
            logger.warning("%s: no settings row — skipping DE/AI", ticker)
            context["halt_after_persist"] = True
            context["settings"] = settings
            return context

        # 7. P4-08: Run DE and internet collection in parallel
        snapshot = _snapshot_for_history(sig_data, analysis_history, confirmation_history)
        de = DecisionEngine(settings)

        section_started = time.perf_counter()
        if self._internet:
            evaluation, internet_ctx = await asyncio.gather(
                asyncio.to_thread(de.evaluate, signal_orm, snapshot),
                self._internet.get_context(ticker),
                return_exceptions=False,
            )
        else:
            evaluation = de.evaluate(signal_orm, snapshot)
            internet_ctx = None
        decision_timing['de_and_internet_ms'] = _elapsed_ms(section_started)

        # 8. Event regime + geometry rescue before AI
        from apps.worker.ai.types import AIMode
        ai_mode_str = getattr(settings, "ai_mode", "advisory") or "advisory"
        try:
            ai_mode = AIMode(ai_mode_str)
        except ValueError:
            ai_mode = AIMode.OFF

        strategy_name = (sig_data.get('meta') or {}).get("strategy_name") or (sig_data.get('meta') or {}).get("strategy") or getattr(self.strategy, "name", None)
        section_started = time.perf_counter()
        symbol_profile = get_symbol_profile(ticker, db=db)
        symbol_diagnostics = get_symbol_diagnostics(db, ticker, lookback_days=180, timeframe='1m')
        event_regime_obj = analyze_event_regime(
            ticker,
            sig_data["side"],
            internet_ctx,
            symbol_profile=symbol_profile,
            symbol_diagnostics=symbol_diagnostics,
        )
        event_meta = event_regime_obj.to_meta()
        event_meta['block_threshold'] = float(getattr(settings, 'event_regime_block_severity', 0.82) or 0.82)
        if bool(getattr(settings, 'event_regime_enabled', True)):
            try:
                persist_event_regime(db, event_regime_obj)
            except Exception as exc:
                logger.debug("Event regime snapshot persist failed for %s: %s", ticker, exc)
        decision_timing['event_regime_ms'] = _elapsed_ms(section_started)

        section_started = time.perf_counter()
        if should_retry_geometry(evaluation):
            optimized_retry, geometry_retry = _apply_geometry_pass(
                db=db,
                ticker=ticker,
                sig_data=sig_data,
                candles=analysis_history,
                settings=settings,
                adaptive_plan=adaptive_plan,
                event_regime=event_meta if bool(getattr(settings, 'event_regime_enabled', True)) else None,
                evaluation_metrics=dict(getattr(evaluation, 'metrics', {}) or {}),
                phase='rescue',
            )
            if geometry_retry and geometry_retry.get('applied'):
                sig_data = optimized_retry
                rescue_hint = geometry_retry.get('suggested_timeframe')
                if rescue_hint:
                    rescue_signal, rescue_history, rescue_meta = _run_strategy_timeframe_search(
                        self.strategy,
                        ticker,
                        candle_history,
                        adaptive_plan,
                        settings,
                        rescue_hint=rescue_hint,
                    )
                    if rescue_signal and rescue_meta.get('selected_timeframe'):
                        rescue_confirmation_tf = normalize_timeframe((adaptive_plan or {}).get('confirmation_timeframe') or getattr(settings, 'higher_timeframe', '15m') or '15m', '15m')
                        rescue_confirmation_history = resample_candles(candle_history, rescue_confirmation_tf) if rescue_confirmation_tf != '1m' else list(candle_history)
                        rescue_signal = _attach_execution_geometry(
                            rescue_signal,
                            execution_history=execution_history,
                            confirmation_history=rescue_confirmation_history,
                            adaptive_plan=adaptive_plan,
                        )
                        rescue_signal, geometry_retry = _apply_geometry_pass(
                            db=db,
                            ticker=ticker,
                            sig_data=rescue_signal,
                            candles=rescue_history,
                            settings=settings,
                            adaptive_plan=adaptive_plan,
                            event_regime=event_meta if bool(getattr(settings, 'event_regime_enabled', True)) else None,
                            evaluation_metrics=dict(getattr(evaluation, 'metrics', {}) or {}),
                            phase='rescue_mtf',
                        )
                        analysis_history = rescue_history
                        confirmation_history = rescue_confirmation_history
                        snapshot = _snapshot_for_history(rescue_signal, analysis_history, confirmation_history)
                        sig_data = rescue_signal
                        sig_meta = dict(sig_data.get('meta') or {})
                        sig_meta['multi_timeframe'] = {
                            'requested_timeframe': rescue_meta.get('requested_timeframe'),
                            'selected_timeframe': rescue_meta.get('selected_timeframe'),
                            'candidates': rescue_meta.get('candidates') or [],
                            'phase': 'rescue',
                        }
                        sig_data['meta'] = sig_meta
                signal_orm.entry = sig_data['entry']
                signal_orm.sl = sig_data['sl']
                signal_orm.tp = sig_data['tp']
                signal_orm.r = sig_data['r']
                rescue_optimizer_overlay = build_portfolio_optimizer_overlay(db, settings, sig_data)
                rescue_optimizer_mult = float((rescue_optimizer_overlay or {}).get('optimizer_risk_multiplier') or 1.0)
                rescue_base_mult = float((adaptive_plan or {}).get('risk_multiplier') or 1.0)
                rescue_size = float(risk.calculate_position_size(
                    entry=sig_data['entry'],
                    sl=sig_data['sl'],
                    lot_size=1,
                    risk_multiplier=max(0.1, rescue_base_mult * rescue_optimizer_mult),
                ))
                sig_meta = dict(sig_data.get('meta') or {})
                sig_meta['portfolio_optimizer'] = dict(rescue_optimizer_overlay or {})
                sig_meta['risk_sizing'] = dict(getattr(risk, 'last_size_details', {}) or {})
                sig_meta['risk_sizing']['base_signal_risk_multiplier'] = round(rescue_base_mult, 4)
                sig_meta['risk_sizing']['optimizer_risk_multiplier'] = round(rescue_optimizer_mult, 4)
                sig_meta['risk_sizing']['combined_signal_risk_multiplier'] = round(max(0.1, rescue_base_mult * rescue_optimizer_mult), 4)
                sig_data['meta'] = sig_meta
                if rescue_size > 0:
                    sig_data['size'] = rescue_size
                    signal_orm.size = rescue_size
                signal_orm.meta = dict(sig_data.get('meta') or {})
                db.flush()
                evaluation = de.evaluate(signal_orm, snapshot)
                logger.info(
                    "%s: geometry rescue re-evaluated signal action=%s tf=%s r=%.2f entry=%.4f sl=%.4f tp=%.4f size=%.2f",
                    ticker,
                    geometry_retry.get('action') if isinstance(geometry_retry, dict) else None,
                    (sig_data.get('meta') or {}).get('analysis_timeframe'),
                    float(sig_data.get('r') or 0.0),
                    float(sig_data.get('entry') or 0.0),
                    float(sig_data.get('sl') or 0.0),
                    float(sig_data.get('tp') or 0.0),
                    float(sig_data.get('size') or 0.0),
                )
        decision_timing['geometry_rescue_ms'] = _elapsed_ms(section_started)

        de_reasons = [r.model_dump() for r in evaluation.reasons]
        strategy_name = (sig_data.get('meta') or {}).get("strategy_name") or (sig_data.get('meta') or {}).get("strategy") or strategy_name
        regime_name = str((event_meta or {}).get('regime') or (adaptive_plan or {}).get('regime') or (sig_data.get('meta') or {}).get('regime') or 'unknown')
        sig_meta = dict(sig_data.get('meta') or {})
        if sig_meta.get('analysis_timeframe'):
            sig_meta['thesis_timeframe'] = sig_meta.get('thesis_timeframe') or sig_meta.get('analysis_timeframe')
            sig_meta['execution_timeframe'] = sig_meta.get('execution_timeframe') or normalize_timeframe((adaptive_plan or {}).get('execution_timeframe') or '1m', '1m')
            sig_meta['market_regime_profile'] = sig_meta.get('market_regime_profile') or regime_name
            sig_data['meta'] = sig_meta
        section_started = time.perf_counter()
        perf_governor = evaluate_signal_governor(
            db,
            settings,
            instrument_id=ticker,
            strategy=str(strategy_name or 'unknown'),
            regime=regime_name,
        )
        sig_meta = dict(sig_data.get('meta') or {})
        sig_meta['performance_governor'] = perf_governor
        risk_sizing_meta = dict(sig_meta.get('risk_sizing') or {})
        perf_risk_mult = float(perf_governor.get('risk_multiplier') or 1.0)
        current_combined_mult = float(context.get('combined_risk_mult') or risk_sizing_meta.get('combined_signal_risk_multiplier') or 1.0)
        effective_combined_mult = max(0.05, current_combined_mult * perf_risk_mult)
        risk_sizing_meta['performance_governor_risk_multiplier'] = round(perf_risk_mult, 4)
        risk_sizing_meta['combined_signal_risk_multiplier_after_governor'] = round(effective_combined_mult, 4)
        sig_meta['risk_sizing'] = risk_sizing_meta
        sig_data['meta'] = sig_meta
        if risk is not None:
            resized = float(risk.calculate_position_size(
                entry=sig_data['entry'],
                sl=sig_data['sl'],
                lot_size=1,
                risk_multiplier=effective_combined_mult,
            ))
            if resized > 0:
                sig_data['size'] = resized
                signal_orm.size = resized
        signal_orm.meta = dict(sig_data.get('meta') or {})
        db.flush()
        decision_timing['performance_governor_ms'] = _elapsed_ms(section_started)

        section_started = time.perf_counter()
        ml_overlay = evaluate_ml_overlay(
            db,
            settings,
            instrument_id=ticker,
            side=sig_data['side'],
            entry=float(sig_data['entry']),
            sl=float(sig_data['sl']),
            tp=float(sig_data['tp']),
            size=float(sig_data['size']),
            ts_ms=int(getattr(signal_orm, 'created_ts', 0) or int(time.time() * 1000)),
            meta=dict(sig_data.get('meta') or {}),
            final_decision=str(evaluation.decision.value or 'UNKNOWN').upper(),
        )
        sig_meta = dict(sig_data.get('meta') or {})
        sig_meta['ml_overlay'] = ml_overlay.to_meta()
        sig_data['meta'] = sig_meta
        perf_governor = dict(perf_governor or {})
        if _should_relax_governor_suppression(sig_meta=sig_meta, perf_governor=perf_governor):
            perf_governor['suppressed'] = False
            perf_governor['relaxed_for_higher_tf'] = True
            perf_governor['relaxation_reason'] = 'higher_tf_tradeable_candidate'
        ml_risk_mult = float(ml_overlay.risk_multiplier or 1.0)
        risk_sizing_meta = dict(sig_meta.get('risk_sizing') or {})
        risk_sizing_meta['ml_risk_multiplier'] = round(ml_risk_mult, 4)
        risk_sizing_meta['combined_signal_risk_multiplier_after_ml'] = round(float(risk_sizing_meta.get('combined_signal_risk_multiplier_after_governor') or effective_combined_mult) * ml_risk_mult, 4)
        sig_meta['risk_sizing'] = risk_sizing_meta
        if risk is not None:
            resized = float(risk.calculate_position_size(
                entry=sig_data['entry'],
                sl=sig_data['sl'],
                lot_size=1,
                risk_multiplier=float(risk_sizing_meta['combined_signal_risk_multiplier_after_ml']),
            ))
            if resized > 0:
                sig_data['size'] = resized
                signal_orm.size = resized
        signal_orm.meta = dict(sig_data.get('meta') or {})
        db.flush()
        _append_decision_log(
            db,
            log_type='ml_signal_overlay',
            message=f"{ticker} adjusted by ML overlay",
            payload={'signal_id': signal_orm.id, 'trace_id': trace_id, 'instrument_id': ticker, 'ml_overlay': ml_overlay.to_meta()},
        )
        decision_timing['ml_overlay_ms'] = _elapsed_ms(section_started)
        if perf_governor.get('suppressed'):
            de_reasons.append({'code': 'performance_governor', 'severity': 'block', 'message': '; '.join(perf_governor.get('reasons') or ['weak slice suppressed'])})
            _append_decision_log(
                db,
                log_type='performance_governor_block',
                message=f"{ticker} blocked by performance governor",
                payload={'signal_id': signal_orm.id, 'trace_id': trace_id, 'instrument_id': ticker, 'performance_governor': perf_governor},
            )
        else:
            _append_decision_log(
                db,
                log_type='performance_governor_adjustment',
                message=f"{ticker} adjusted by performance governor",
                payload={'signal_id': signal_orm.id, 'trace_id': trace_id, 'instrument_id': ticker, 'performance_governor': perf_governor},
            )

        ai_result = None
        ai_log_record = None
        de_has_blockers = any(r.severity.value == 'block' for r in evaluation.reasons)
        effective_threshold = int((adaptive_plan or {}).get('decision_threshold') or getattr(settings, 'decision_threshold', 70) or 70)
        effective_threshold += int(perf_governor.get('threshold_adjustment') or 0)
        effective_threshold += int(ml_overlay.threshold_adjustment or 0)
        if policy_state and getattr(policy_state, 'state', 'normal') == 'degraded':
            effective_threshold += int(getattr(policy_state, 'threshold_penalty', 0) or 0)
            sig_meta = dict(sig_data.get('meta') or {})
            sig_meta['auto_policy'] = getattr(policy_state, 'to_meta', lambda: policy_state)()
            sig_meta['effective_threshold_after_policy'] = effective_threshold
            sig_data['meta'] = sig_meta
        final_decision, event_adjusted_score, event_merge_reason = _apply_event_regime(
            evaluation.decision.value,
            int(evaluation.score),
            effective_threshold,
            event_meta if bool(getattr(settings, 'event_regime_enabled', True)) else None,
            has_blockers=de_has_blockers or bool(perf_governor.get('suppressed')),
        )
        if perf_governor.get('suppressed'):
            final_decision = 'SKIP'
            event_adjusted_score = min(int(event_adjusted_score), max(0, effective_threshold - 1))
            event_merge_reason = f"{event_merge_reason}; performance governor suppression"
        if ml_overlay.suppress_take and final_decision == 'TAKE':
            final_decision = 'SKIP'
            event_adjusted_score = min(int(event_adjusted_score), max(0, effective_threshold - 1))
            event_merge_reason = f"{event_merge_reason}; ML overlay veto"
        analysis_ts = int((analysis_history[-1] or {}).get('time') or 0) * 1000 if analysis_history else 0
        execution_ts = int((execution_history[-1] or {}).get('time') or 0) * 1000 if execution_history else analysis_ts
        section_started = time.perf_counter()
        freshness_decision, freshness_score, freshness_meta_obj = apply_signal_freshness(
            decision=final_decision,
            score=event_adjusted_score,
            threshold=effective_threshold,
            analysis_ts=analysis_ts,
            execution_ts=execution_ts,
            execution_timeframe=(sig_data.get('meta') or {}).get('execution_timeframe') or (adaptive_plan or {}).get('execution_timeframe') or '1m',
            settings=settings,
        )
        freshness_meta = freshness_meta_obj.to_meta()
        freshness_merge_reason = freshness_meta.get('reason') or 'signal freshness observed'
        final_decision = freshness_decision
        event_adjusted_score = freshness_score
        freshness_blocked = bool(freshness_meta.get('blocked'))
        merge_payload = None
        conviction_profile = _build_conviction_profile(
            final_decision=final_decision,
            score=event_adjusted_score,
            threshold=effective_threshold,
            evaluation=evaluation,
            perf_governor=perf_governor,
            freshness_meta=freshness_meta,
            signal_meta=sig_data.get('meta') or {},
        )
        sig_meta = dict(sig_data.get('meta') or {})
        sig_meta['conviction_profile'] = conviction_profile
        sig_data['meta'] = sig_meta
        promoted_decision, promotion_reason, promotion_meta = _promote_high_conviction_skip(
            final_decision=final_decision,
            score=event_adjusted_score,
            threshold=effective_threshold,
            evaluation=evaluation,
            perf_governor=perf_governor,
            freshness_meta=freshness_meta,
            conviction_profile=conviction_profile,
        )
        if promoted_decision != final_decision:
            final_decision = promoted_decision
            event_merge_reason = f"{event_merge_reason}; {promotion_reason}"
            sig_meta = dict(sig_data.get('meta') or {})
            sig_meta['high_conviction_promotion'] = promotion_meta
            sig_data['meta'] = sig_meta
            _append_decision_log(
                db,
                log_type='high_conviction_promotion',
                message=f"{ticker} promoted from SKIP to TAKE by high-conviction rule",
                payload={
                    'signal_id': signal_orm.id,
                    'trace_id': trace_id,
                    'instrument_id': ticker,
                    'promotion': promotion_meta,
                    'score': int(event_adjusted_score),
                    'threshold': int(effective_threshold),
                },
            )

        if freshness_meta.get('applied'):
            _append_decision_log(
                db,
                log_type='signal_freshness',
                message=f"Signal freshness for {ticker}: {freshness_merge_reason}",
                payload={
                    'signal_id': signal_orm.id,
                    'trace_id': trace_id,
                    'instrument_id': ticker,
                    'analysis_ts': analysis_ts,
                    'execution_ts': execution_ts,
                    'freshness': freshness_meta,
                    'decision_before': evaluation.decision.value,
                    'decision_after': final_decision,
                    'score_before': int(evaluation.score),
                    'score_after': int(event_adjusted_score),
                },
            )
        decision_timing['freshness_ms'] = _elapsed_ms(section_started)

        selective_policy_blocked = False
        selective_policy_reason = ''
        if policy_state and getattr(policy_state, 'state', '') == 'frozen' and bool(getattr(policy_state, 'selective_throttle', False)):
            selective_policy_blocked, selective_policy_reason = _evaluate_selective_policy_throttle(
                policy_state=policy_state,
                final_decision=final_decision,
                score=event_adjusted_score,
                threshold=effective_threshold,
                sig_data=sig_data,
                perf_governor=perf_governor,
                freshness_meta=freshness_meta,
            )
            if selective_policy_blocked:
                final_decision = 'REJECT'
                event_merge_reason = f"{event_merge_reason}; selective throttle"
                _append_decision_log(
                    db,
                    log_type='auto_runtime_guard',
                    message=f"{ticker} blocked by selective throttle during frozen mode",
                    payload={
                        'signal_id': signal_orm.id,
                        'trace_id': trace_id,
                        'instrument_id': ticker,
                        'policy': policy_state.to_meta(),
                        'reason': selective_policy_reason,
                        'score': int(event_adjusted_score),
                        'threshold': int(effective_threshold),
                        'r': float(sig_data.get('r') or 0.0),
                    },
                )

        ai_fast_path = None
        section_started = time.perf_counter()
        if ai_mode != AIMode.OFF and not selective_policy_blocked:
            from apps.worker.ai.types import AIContext
            from apps.worker.ai.router import AIProviderRouter

            ai_min_conf = int(getattr(settings, "ai_min_confidence", 55) or 55)
            ai_fast_path = evaluate_ai_fast_path(
                evaluation=evaluation,
                final_decision=final_decision,
                perf_governor=perf_governor,
                freshness_meta=freshness_meta,
            )

            if ai_fast_path is not None:
                merge_reason = f"{event_merge_reason}; {freshness_merge_reason}; AI fast-path skip: {ai_fast_path.reason}"
                merge_payload = {
                    "signal_id": signal_orm.id,
                    "instrument_id": ticker,
                    "ai_mode": ai_mode.value,
                    "de_decision": evaluation.decision.value,
                    "de_score": evaluation.score,
                    "de_has_blockers": de_has_blockers or freshness_blocked or bool(perf_governor.get('suppressed')),
                    "ai_decision": None,
                    "ai_confidence": None,
                    "ai_provider": None,
                    "ai_min_confidence": ai_min_conf,
                    "final_decision": final_decision,
                    "merge_reason": merge_reason,
                    "ai_prompt_profile": None,
                    "ai_fast_path": ai_fast_path.to_meta(),
                }
                logger.info(
                    "%s: AI fast-path skip => %s [%s]",
                    ticker,
                    final_decision,
                    ai_fast_path.reason,
                )
                _append_decision_log(
                    db,
                    log_type="ai_fast_path_skip",
                    message=f"AI skipped for {ticker}: {final_decision}",
                    payload={
                        "signal_id": signal_orm.id,
                        "trace_id": trace_id,
                        "instrument_id": ticker,
                        "ai_fast_path": ai_fast_path.to_meta(),
                        "decision": final_decision,
                    },
                )
            else:
                historical_context = HistoricalContextAnalyzer(db).analyze(
                    instrument_id=ticker,
                    side=sig_data["side"],
                    strategy_name=strategy_name,
                    de_metrics=dict(evaluation.metrics),
                    limit=4,
                )
                sentiment_sector = None
                if isinstance(symbol_profile, dict):
                    sentiment_sector = symbol_profile.get('sector') or symbol_profile.get('sector_id')
                if not sentiment_sector:
                    sentiment_sector = (get_instrument_sector_payload(ticker) or {}).get('sector')
                trader_sentiment = build_prompt_sentiment_context(
                    db,
                    instrument_id=ticker,
                    sector=sentiment_sector,
                    settings=settings,
                    max_items=3,
                )
                ai_ctx = AIContext(
                    signal_id=signal_orm.id,
                    instrument_id=ticker,
                    side=sig_data["side"],
                    entry=sig_data["entry"],
                    sl=sig_data["sl"],
                    tp=sig_data["tp"],
                    size=sig_data["size"],
                    r=sig_data["r"],
                    de_score=evaluation.score,
                    de_decision=evaluation.decision.value,
                    de_reasons=de_reasons,
                    de_metrics=dict(evaluation.metrics),
                    candles_summary=_build_candles_summary(analysis_history),
                    internet=internet_ctx,
                    historical_context=historical_context,
                    symbol_profile=symbol_profile,
                    symbol_diagnostics=symbol_diagnostics,
                    event_regime=event_meta,
                    geometry=dict((sig_data.get('meta') or {}).get('geometry_optimizer') or {}),
                    trader_sentiment=trader_sentiment,
                )

                router_config = SimpleNamespace(
                    AI_PRIMARY_PROVIDER=getattr(settings, "ai_primary_provider", None) or "deepseek",
                    AI_FALLBACK_PROVIDERS=getattr(settings, "ai_fallback_providers", None) or "deepseek,ollama,skip",
                    OLLAMA_BASE_URL=getattr(settings, "ollama_url", None) or "http://localhost:11434",
                    OLLAMA_MODEL=getattr(runtime_config, "OLLAMA_MODEL", "llama3.1:8b"),
                    CLAUDE_MODEL=getattr(runtime_config, "CLAUDE_MODEL", "claude-sonnet-4-6"),
                    OPENAI_MODEL=getattr(runtime_config, "OPENAI_MODEL", "gpt-4o"),
                    DEEPSEEK_MODEL=getattr(runtime_config, "DEEPSEEK_MODEL", "deepseek-chat"),
                    DEEPSEEK_BASE_URL=getattr(runtime_config, "DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                )
                router = AIProviderRouter(config=router_config)
                ai_result = await router.analyze(ai_ctx, ai_mode)

                # Merge decisions per ai_mode
                final_decision, merge_reason = router.merge_decisions(
                    de_decision=final_decision,
                    de_score=event_adjusted_score,
                    ai_result=ai_result,
                    ai_mode=ai_mode,
                    ai_min_confidence=ai_min_conf,
                    de_has_blockers=de_has_blockers or freshness_blocked,
                    override_policy=getattr(settings, "ai_override_policy", "promote_only") or "promote_only",
                )
                merge_payload = _build_merge_payload(
                    ticker=ticker,
                    signal_id=signal_orm.id,
                    evaluation=evaluation,
                    ai_result=ai_result,
                    final_decision=final_decision,
                    merge_reason=f"{event_merge_reason}; {freshness_merge_reason}; {merge_reason}",
                    ai_mode=ai_mode.value,
                    ai_min_confidence=ai_min_conf,
                    de_has_blockers=de_has_blockers,
                )
                ai_reason_short = ((ai_result.reasoning or '') if ai_result else '').replace('\n', ' ')[:300]
                logger.info(
                    "%s: merge de=%s(score=%s blockers=%s) ai=%s(conf=%s min=%s provider=%s) => %s [%s] reason=%s",
                    ticker,
                    evaluation.decision.value,
                    evaluation.score,
                    de_has_blockers,
                    getattr(ai_result.decision, 'value', None) if ai_result else None,
                    ai_result.confidence if ai_result else None,
                    ai_min_conf,
                    getattr(ai_result, 'provider', None) if ai_result else None,
                    final_decision,
                    f"{event_merge_reason}; {freshness_merge_reason}; {merge_reason}",
                    ai_reason_short,
                )
                _append_decision_log(
                    db,
                    log_type="ai_de_merge",
                    message=f"AI/DE merge for {ticker}: {final_decision}",
                    payload=merge_payload,
                )


                # P4-07: Log AI decision
                try:
                    from apps.worker.ai.prompts import build_user_prompt
                    ai_prompt_text = build_user_prompt(ai_ctx)
                    ai_log_record = save_ai_decision(
                        db=db,
                        signal_id=signal_orm.id,
                        instrument_id=ticker,
                        ai_result=ai_result,
                        final_decision=final_decision,
                        de_score=evaluation.score,
                        prompt_text=ai_prompt_text,
                    )
                except Exception as e:
                    logger.warning("Failed to save AI decision log: %s", e)
        decision_timing['ai_ms'] = _elapsed_ms(section_started)

        # 9. Save decision metadata
        section_started = time.perf_counter()
        signal_orm.ai_influenced = bool(ai_result is not None and ai_mode != AIMode.OFF)
        signal_orm.ai_mode_used = ai_mode.value if ai_mode != AIMode.OFF and not selective_policy_blocked else "off"
        signal_orm.ai_decision_id = ai_log_record.id if ai_log_record else None

        meta = dict(signal_orm.meta or {})
        cognitive_payload = build_cognitive_layer_payload(
            ticker=ticker,
            side=sig_data['side'],
            sig_data=sig_data,
            evaluation=evaluation,
            final_decision=final_decision,
            effective_threshold=effective_threshold,
            adaptive_plan=adaptive_plan,
            event_regime=event_meta,
            freshness_meta=freshness_meta,
            perf_governor=perf_governor,
            trader_sentiment=locals().get('trader_sentiment'),
            ai_result=ai_result,
        )
        if adaptive_plan:
            meta["adaptive_plan"] = adaptive_plan
        meta["decision"] = evaluation.model_dump(mode="json")
        meta["event_regime"] = event_meta
        meta["event_adjusted_score"] = event_adjusted_score
        meta["conviction_profile"] = conviction_profile
        meta["high_conviction_promotion"] = promotion_meta
        meta["signal_freshness"] = freshness_meta
        meta['auto_policy'] = getattr(policy_state, 'to_meta', lambda: policy_state)() if policy_state else meta.get('auto_policy')
        meta["symbol_brain"] = {
            "strategy_name": strategy_name,
            "strategy_source": (adaptive_plan or {}).get('strategy_source') if isinstance(adaptive_plan, dict) else None,
            "adaptive_plan": adaptive_plan,
            "symbol_profile": symbol_profile,
            "symbol_diagnostics": symbol_diagnostics,
            "event_regime": event_meta,
        }
        if ai_mode != AIMode.OFF:
            meta["historical_context"] = historical_context if 'historical_context' in locals() else None
            meta["symbol_profile"] = symbol_profile if 'symbol_profile' in locals() else None
            meta["symbol_diagnostics"] = symbol_diagnostics if 'symbol_diagnostics' in locals() else None
        if ai_fast_path is not None:
            meta["ai_fast_path"] = ai_fast_path.to_meta()
        if selective_policy_blocked:
            meta['pre_persist_block'] = {
                'code': 'auto_freeze_selective_throttle',
                'reason': selective_policy_reason,
                'stage': 'policy_blocked',
                'ts': int(time.time() * 1000),
            }
            meta['candidate_snapshot'] = _build_pre_persist_candidate_payload(
                ticker=ticker,
                sig_data=sig_data,
                strategy_name=(adaptive_plan or {}).get('strategy_name') or strategy_name,
                stage='policy_blocked',
                block_code='auto_freeze_selective_throttle',
                block_reason=selective_policy_reason,
            )
            cognitive_payload['status'] = 'blocked_after_reasoning'
            cognitive_payload['contradictions'] = list(dict.fromkeys([*(cognitive_payload.get('contradictions') or []), 'policy_selective_throttle']))
            operator_summary = dict(cognitive_payload.get('operator_summary') or {})
            operator_summary['blocked_after_reasoning'] = True
            operator_summary['highest_risk_axis'] = 'policy'
            cognitive_payload['operator_summary'] = operator_summary
        if ai_result:
            meta["ai_prompt_profile"] = "intraday_dynamic_v3_research_scalp"
            meta["ai_decision"] = {
                "provider": ai_result.provider,
                "decision": ai_result.decision.value,
                "confidence": ai_result.confidence,
                "reasoning": ai_result.reasoning,
                "key_factors": ai_result.key_factors,
            }
        meta["final_decision"] = final_decision
        meta['cognitive_layer'] = cognitive_payload
        review_readiness = _reconcile_review_readiness(meta.get('review_readiness'), conviction_profile)
        if review_readiness:
            meta['review_readiness'] = review_readiness
        if merge_payload:
            meta["decision_merge"] = merge_payload
        else:
            meta["decision_merge"] = {
                "pre_ai_final_decision": final_decision,
                "event_merge_reason": event_merge_reason,
                "freshness_reason": freshness_merge_reason,
                "event_adjusted_score": event_adjusted_score,
            }
        meta["ai_influenced"] = signal_orm.ai_influenced
        meta["ai_mode_used"] = signal_orm.ai_mode_used
        if signal_orm.ai_decision_id:
            meta["ai_decision_id"] = signal_orm.ai_decision_id
        signal_orm.meta = meta
        db.commit()
        db.refresh(signal_orm)

        # 10. Detailed decision logs
        _append_decision_log(
            db,
            log_type="decision_engine",
            message=f"{final_decision} {ticker} de_score={evaluation.score}",
            payload={"signal_id": signal_orm.id, "trace_id": trace_id, "de": evaluation.model_dump(mode="json"), "ai_mode": ai_mode_str, "merge": merge_payload},
        )
        _append_decision_log(
            db,
            log_type="signal_pipeline",
            message=f"Signal pipeline completed for {ticker}: {final_decision}",
            payload=_build_signal_pipeline_payload(
                ticker=ticker,
                signal_id=signal_orm.id,
                sig_data=sig_data,
                evaluation=evaluation,
                final_decision=final_decision,
                merge_payload=merge_payload,
            ),
        )

        # 11. Metrics
        record_signal(
            decision=final_decision,
            instrument=ticker,
            side=sig_data["side"],
            score=evaluation.score,
        )

        if final_decision != "TAKE" and signal_orm.status == "pending_review":
            signal_repo.update_signal_status(db, signal_orm.id, "rejected", commit=False)
            db.commit()
            db.refresh(signal_orm)

        decision_timing['finalize_ms'] = _elapsed_ms(section_started)
        context.setdefault('telemetry', {})['decision_flow_ms'] = decision_timing
        context.update({
            "signal_orm": signal_orm,
            "settings": settings,
            "meta": meta,
            "final_decision": final_decision,
            "evaluation": evaluation,
            "ai_mode_str": ai_mode_str,
            "sig_data": sig_data,
            "trace_id": trace_id,
        })
        return context

    async def _publish_and_notify(self, context: dict) -> None:
        ticker = context["ticker"]
        sig_data = context["sig_data"]
        signal_orm = context["signal_orm"]
        settings = context["settings"]
        evaluation = context["evaluation"]
        final_decision = context["final_decision"]
        meta = context["meta"]
        notify_timing: dict[str, int | bool | None] = {}
        # 12. SSE
        section_started = time.perf_counter()
        await bus.publish("signal_updated", {
            "id": signal_orm.id, "status": signal_orm.status, "meta": meta,
        })
        notify_timing['sse_publish_ms'] = _elapsed_ms(section_started)
        logger.info("%s: final=%s (DE=%s score=%d)", ticker, final_decision, evaluation.decision.value, evaluation.score)

        # 12b. Telegram notification (P6-04/P2-01)
        notify_timing['telegram_notify_ms'] = 0
        notify_timing['telegram_sent'] = None
        try:
            from core.notifications.telegram import TelegramNotifier as _Tg
            _tg = _Tg.from_settings(settings)
            if _tg:
                _sig_info = {
                    "id": signal_orm.id,
                    "instrument_id": ticker,
                    "side": sig_data["side"],
                    "entry": float(sig_data.get("entry", 0)),
                    "sl": float(sig_data.get("sl", 0)),
                    "tp": float(sig_data.get("tp", 0)),
                    "r": float(sig_data.get("r", 0)),
                    "score": evaluation.score,
                    "decision": final_decision,
                }
                section_started = time.perf_counter()
                _sent = await _tg.send_signal_created(_sig_info)
                notify_timing['telegram_notify_ms'] = _elapsed_ms(section_started)
                notify_timing['telegram_sent'] = bool(_sent)
                logger.info("%s: telegram signal_created sent=%s status=%s final=%s", ticker, _sent, signal_orm.status, final_decision)
        except Exception as exc:
            logger.warning("%s: telegram signal_created notify failed: %r", ticker, exc)
            # Telegram must never block trading
        context.setdefault('telemetry', {})['publish_notify_ms'] = notify_timing


    async def _execute_signal(self, db: Session, context: dict) -> None:
        exec_started = time.perf_counter()
        ticker = context["ticker"]
        signal_orm = context["signal_orm"]
        settings = context["settings"]
        final_decision = context["final_decision"]
        ai_mode_str = context["ai_mode_str"]
        trace_id = context["trace_id"]
        # 13. Auto-execution based on final_decision
        trade_mode = settings.trade_mode or "review"
        execution_payload = {
            "signal_id": signal_orm.id,
            "instrument_id": ticker,
            "final_decision": final_decision,
            "trade_mode": trade_mode,
            "status_before_execution": signal_orm.status,
            "ai_mode": ai_mode_str,
        }
        _append_decision_log(
            db,
            log_type="execution_intent",
            message=f"Execution intent for {ticker}: {final_decision} in {trade_mode}",
            payload={**execution_payload, "trace_id": trace_id},
        )
        if final_decision == "TAKE":
            execution_error_reason = None
            uow = SignalExecutionUnitOfWork(db, signal_id=signal_orm.id, trace_id=trace_id)
            current_settings = settings_repo.get_settings(db)
            force_paper = trade_mode == "auto_live" and prefers_paper_execution(current_settings)
            try:
                uow.mark('begin', trade_mode=trade_mode)
                if trade_mode == "auto_paper" or force_paper:
                    signal_repo.update_signal_status(db, signal_orm.id, "approved", commit=False)
                    uow.mark('signal_approved')
                    uow.commit()
                    db.refresh(signal_orm)
                    uow.mark('paper_execution_start')
                    await PaperExecutionEngine(db).execute_approved_signal(signal_orm.id)
                    uow.mark('paper_execution_done')
                elif trade_mode == "auto_live":
                    from core.config import settings as cfg
                    runtime_tbank_token = get_token("TBANK_TOKEN") or cfg.TBANK_TOKEN
                    runtime_tbank_account = get_token("TBANK_ACCOUNT_ID") or cfg.TBANK_ACCOUNT_ID
                    if runtime_tbank_token and runtime_tbank_account:
                        from core.execution.tbank import TBankExecutionEngine
                        engine = TBankExecutionEngine(db, runtime_tbank_token, runtime_tbank_account, cfg.TBANK_SANDBOX)
                        signal_repo.update_signal_status(db, signal_orm.id, "approved", commit=False)
                        uow.mark('signal_approved')
                        uow.commit()
                        db.refresh(signal_orm)
                        uow.mark('live_execution_start')
                        await engine.execute_approved_signal(signal_orm.id)
                        uow.mark('live_execution_done')
                    else:
                        execution_error_reason = 'missing_tbank_credentials'
                        logger.warning(
                            "%s: auto_live requested but TBANK runtime credentials are incomplete (token=%s account=%s)",
                            ticker,
                            bool(runtime_tbank_token),
                            bool(runtime_tbank_account),
                        )
                else:
                    uow.mark('take_without_auto_execution', trade_mode=trade_mode)
            except Exception as exc:
                execution_error_reason = f'execution_failed:{type(exc).__name__}'
                uow.mark('exception', reason=execution_error_reason)
                logger.error("%s: execution failed for signal %s", ticker, signal_orm.id, exc_info=exc)

            if execution_error_reason:
                failed_signal = signal_repo.get_signal(db, signal_orm.id)
                if failed_signal is not None and failed_signal.status in {"pending_review", "approved"}:
                    failed_signal.status = "execution_error"
                    failed_meta = dict(failed_signal.meta or {})
                    failed_meta['execution_error'] = {
                        'reason': execution_error_reason,
                        'ts': int(time.time() * 1000),
                        'trace_id': trace_id,
                        'unit_of_work': uow.to_meta(),
                    }
                    failed_signal.meta = failed_meta
                    db.commit()
                    await bus.publish('signal_updated', {'id': failed_signal.id, 'status': failed_signal.status, 'meta': failed_meta})
            else:
                current_signal = signal_repo.get_signal(db, signal_orm.id)
                if current_signal is not None:
                    current_meta = dict(current_signal.meta or {})
                    current_meta['execution_uow'] = uow.to_meta()
                    current_signal.meta = current_meta
                    db.commit()
        context.setdefault('telemetry', {})['execute_signal_ms'] = _elapsed_ms(exec_started)


    async def process(self, ticker: str, candle_history: list[dict], db: Session, adaptive_plan: dict | None = None) -> dict:
        total_started = time.perf_counter()
        telemetry: dict[str, object] = {}

        stage_started = time.perf_counter()
        context = await self._prepare_signal_context(ticker, candle_history, db, adaptive_plan)
        telemetry['prepare_context_ms'] = _elapsed_ms(stage_started)
        if context is None:
            telemetry['total_ms'] = _elapsed_ms(total_started)
            return {
                'ok': False,
                'created_signal': False,
                'outcome': 'no_signal',
                'telemetry': telemetry,
            }

        stage_started = time.perf_counter()
        context = self._apply_risk_and_sizing(db, context)
        telemetry['risk_and_sizing_ms'] = _elapsed_ms(stage_started)
        if context is None:
            telemetry['total_ms'] = _elapsed_ms(total_started)
            return {
                'ok': False,
                'created_signal': False,
                'outcome': 'blocked_pre_persist',
                'telemetry': telemetry,
            }

        pre_persist_blocked = bool(context.get('pre_persist_blocked'))

        stage_started = time.perf_counter()
        context = self._persist_signal(db, context)
        telemetry['persist_signal_ms'] = _elapsed_ms(stage_started)
        if context is None:
            telemetry['total_ms'] = _elapsed_ms(total_started)
            return {
                'ok': False,
                'created_signal': False,
                'outcome': 'persist_failed',
                'telemetry': telemetry,
            }

        if pre_persist_blocked:
            full_telemetry = dict(telemetry)
            full_telemetry['total_ms'] = _elapsed_ms(total_started)
            signal_orm = context['signal_orm']
            return {
                'ok': True,
                'created_signal': True,
                'outcome': 'blocked_pre_persist_persisted',
                'signal_id': str(signal_orm.id),
                'status': getattr(signal_orm, 'status', None),
                'final_decision': 'REJECT',
                'telemetry': full_telemetry,
            }

        stage_started = time.perf_counter()
        decision_context = context
        try:
            context = await self._run_decision_flow(db, context)
        except Exception as exc:
            logger.error("%s: decision flow crashed after persist: %s", decision_context.get('ticker'), exc, exc_info=True)
            signal_orm = decision_context.get('signal_orm')
            if signal_orm is not None:
                failed_meta = dict(signal_orm.meta or {})
                failed_meta['decision_flow_error'] = {
                    'stage': 'run_decision_flow',
                    'reason': f'{type(exc).__name__}: {exc}',
                }
                signal_orm.status = 'rejected'
                signal_orm.meta = failed_meta
                db.commit()
                db.refresh(signal_orm)
            telemetry['decision_flow_total_ms'] = _elapsed_ms(stage_started)
            telemetry['total_ms'] = _elapsed_ms(total_started)
            return {
                'ok': False,
                'created_signal': True,
                'outcome': 'decision_flow_exception',
                'telemetry': telemetry,
            }
        telemetry['decision_flow_total_ms'] = _elapsed_ms(stage_started)
        if context is None:
            signal_orm = decision_context.get('signal_orm')
            if signal_orm is not None:
                failed_meta = dict(signal_orm.meta or {})
                failed_meta.setdefault('decision_flow_error', {
                    'stage': 'run_decision_flow',
                    'reason': 'returned_none',
                })
                signal_orm.status = 'rejected'
                signal_orm.meta = failed_meta
                db.commit()
                db.refresh(signal_orm)
            telemetry['total_ms'] = _elapsed_ms(total_started)
            return {
                'ok': False,
                'created_signal': True,
                'outcome': 'decision_flow_failed',
                'telemetry': telemetry,
            }
        if context.get("halt_after_persist"):
            full_telemetry = dict(telemetry)
            full_telemetry.update(dict(context.get('telemetry') or {}))
            full_telemetry['total_ms'] = _elapsed_ms(total_started)
            return {
                'ok': True,
                'created_signal': True,
                'outcome': 'halt_after_persist',
                'signal_id': str(context['signal_orm'].id),
                'status': getattr(context['signal_orm'], 'status', None),
                'final_decision': context.get('final_decision'),
                'telemetry': full_telemetry,
            }

        stage_started = time.perf_counter()
        await self._publish_and_notify(context)
        telemetry['publish_notify_total_ms'] = _elapsed_ms(stage_started)

        stage_started = time.perf_counter()
        await self._execute_signal(db, context)
        telemetry['execute_signal_total_ms'] = _elapsed_ms(stage_started)

        full_telemetry = dict(telemetry)
        full_telemetry.update(dict(context.get('telemetry') or {}))
        full_telemetry['total_ms'] = _elapsed_ms(total_started)
        return {
            'ok': True,
            'created_signal': True,
            'outcome': 'completed',
            'signal_id': str(context['signal_orm'].id),
            'status': getattr(context['signal_orm'], 'status', None),
            'final_decision': context.get('final_decision'),
            'telemetry': full_telemetry,
        }
