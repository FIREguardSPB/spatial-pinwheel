# Sprint 4 — Sector Expansion

## Why this sprint exists
The current symbol profiles (`symbol_profiles.runtime.json`) cover only **oil & gas**, **metals & mining**, **banks**, and a few general‑purpose sectors. This limits the system’s ability to accurately analyze instruments from other important market segments (automotive, industrials, pharmaceuticals, etc.). Each sector has distinct volatility patterns, liquidity profiles, and economic drivers; a one‑size‑fits‑all analysis leads to suboptimal signals.

Sector expansion will:
- increase the number of analyzable instruments,
- improve signal quality via sector‑specific calibration,
- diversify the trading portfolio across market segments,
- reduce false positives by applying appropriate filters per sector.

## Sprint objective
Add three new high‑priority sectors to the symbol‑profile system, train sector‑aware AI models where feasible, and calibrate decision‑engine filters for each sector.

## Scope

### A. New sector definitions
1. **Automotive** (`automotive`) – Russian auto manufacturers, parts suppliers, EV‑related companies.
   - Example tickers: `TQBR:AVAZ`, `TQBR:KMAZ`, `TQBR:SVAV`, `TQBR:TGKA`, `TQBR:UNAC`.
   - Characteristics: moderate volatility, sensitive to industrial output, seasonal demand.
2. **Industrials** (`industrials`) – machinery, engineering, construction, heavy equipment.
   - Example tickers: `TQBR:CHMK`, `TQBR:KZOS`, `TQBR:LNZL`, `TQBR:MRKV`, `TQBR:MSTT`.
   - Characteristics: lower daily turnover, higher correlation with macroeconomic cycles.
3. **Pharmaceuticals** (`pharma`) – drug manufacturers, biotech, medical equipment.
   - Example tickers: `TQBR:DIAS`, `TQBR:MSNG`, `TQBR:MSRS`, `TQBR:OGKB`, `TQBR:RASP`.
   - Characteristics: defensive sector, lower beta, sensitive to regulatory news.

Each sector definition must include:
- `sector_id` (string, lower‑case).
- `display_name` (human‑readable label).
- `description` (short note about sector specifics).
- `volatility_class` (`low`, `medium`, `high`) – for ATR scaling.
- `liquidity_class` (`low`, `medium`, `high`) – for volume‑filter thresholds.
- `economic_drivers` (array of keywords, e.g., `["industrial_output", "government_contracts", "consumer_demand"]`).
- `default_filters` (optional overrides for `economic_filter_enabled`, `volume_filter_multiplier`, `correlation_threshold`).

### B. Symbol‑profile updates
1. Extend `symbol_profiles.runtime.json` with the three new sectors.
2. Assign existing second‑tier instruments to appropriate sectors (e.g., `TQBR:KMAZ` → `automotive`, `TQBR:CHMK` → `industrials`, `TQBR:DIAS` → `pharma`).
3. Add at least **5–7 new instruments per sector** that are currently missing from the watchlist but are liquid enough for paper trading.
4. Ensure backward compatibility: existing sector IDs (`oil_gas`, `metals_mining`, `banks`, `general`, `second_tier`) remain unchanged.

### C. Sector‑aware calibration
1. **Economic‑filter thresholds** – adjust `volume_filter_multiplier` per sector (e.g., industrials may need a lower multiplier due to naturally lower turnover).
2. **ATR scaling** – modify `atr_stop_soft_min` / `atr_stop_soft_max` based on sector `volatility_class`.
3. **Correlation thresholds** – tighten or loosen `correlation_threshold` depending on sector inter‑dependence.
4. **Session preferences** – some sectors may perform better in specific trading sessions (e.g., industrials in morning, pharmaceuticals in evening). Optional: add `preferred_session` hint.

### D. AI‑model adaptation
1. Extend the `Sector‑Aware AI Layer` to recognize the new sector IDs.
2. If sufficient historical data exists (≥ 30 signals per sector), trigger a **sector‑specific fine‑tuning** of the AI model (or create a lightweight adapter).
3. Update the AI prompt template to include sector‑specific context (e.g., “This is an automotive stock; consider seasonality and government subsidies.”).
4. No mandatory retraining of core ML models (`take_fill`, `trade_outcome`) – they remain cross‑sector.

### E. UI updates
1. Add the new sectors to the sector‑filter dropdown in the **SignalsPage** (if such a filter exists).
2. In the **SettingsPage**, under “Papers” tab, show sector distribution of the current watchlist.
3. Optional: add a small badge next to each instrument in the UI indicating its sector (tooltip on hover).

### F. Tests
1. Unit tests for the new sector‑definition loader.
2. Integration tests that verify sector‑specific filter overrides are applied.
3. Ensure no regression in existing sector‑aware AI logic.

## Out of scope
- Adding more than three sectors (this is a controlled expansion).
- Creating fully independent AI models per sector (fine‑tuning only if data permits).
- Changing the core sector‑routing architecture.
- Real‑time sector detection / automatic classification of new instruments (remains manual mapping).
- Modifying the ML training pipeline to be sector‑stratified (future improvement).

## Deliverables
1. Updated `symbol_profiles.runtime.json` with three new sectors and assigned instruments.
2. Backend logic to apply sector‑specific filter overrides (new module `core/services/sector_filters.py`).
3. Extended sector‑aware AI layer (update `core/ai/sector_prompt.py`).
4. UI sector‑badge component (optional) and sector‑filter updates.
5. Test suite covering new sectors.
6. Short runbook note: `docs/runbook_sector_expansion.md`.

## Acceptance criteria
Sprint is accepted only if all of the following are true:
- All existing unit/integration tests pass.
- New sectors appear in `symbol_profiles.runtime.json` with correct metadata.
- Sector‑specific filter overrides are applied when an instrument belongs to a new sector (verifiable via decision‑log).
- AI layer correctly includes sector context for automotive/industrials/pharma instruments.
- No degradation in signal‑generation performance for existing sectors (oil, metals, banks).
- At least 15 new instruments (5 per sector) are added to the watchlist and appear in the UI.
- The system continues to operate stably (health, dashboard, signals, trades endpoints return normal responses).

## Technical notes
### Symbol‑profile schema extension
The current schema is:
```json
{
  "sectors": {
    "oil_gas": { ... },
    "metals_mining": { ... },
    ...
  },
  "instruments": {
    "TQBR:SBER": { "sector": "banks", ... },
    ...
  }
}
```
Add three new entries under `sectors` and update the `instruments` mapping accordingly.

### Filter‑override precedence
When an instrument belongs to a sector that defines `default_filters`, those values should **override** the global settings **only for that instrument**. The precedence is:
1. Instrument‑specific override (if any)
2. Sector `default_filters`
3. Global settings (`settings` table)

### Backward compatibility
Existing instruments must retain their current sector assignments unless explicitly moved. The `second_tier` sector can be gradually deprecated by moving its members to more specific sectors (automotive/industrials/pharma), but this is optional.

### Data sources for new instruments
Use T‑Bank sandbox `InstrumentsService/FindInstrument` to discover missing tickers. Filter by:
- `currency` = `rub`
- `instrument_type` = `share` (or `etf` if relevant)
- `api_trade_available_flag` = `true`
- Average daily turnover > 10 M RUB (estimate)

## Key files to change
- `backend/core/storage/symbol_profiles.py` – sector definitions.
- `backend/core/services/sector_filters.py` – new module for sector‑specific overrides.
- `backend/core/ai/sector_prompt.py` – extend sector context mapping.
- `backend/core/analysis/context.py` – inject sector filters into analysis context.
- `src/features/signals/SignalsPage.tsx` – add sector filter (if missing).
- `src/features/settings/components/SectorBadge.tsx` – optional UI component.
- `backend/tests/test_sector_filters.py` – new test suite.
- `docs/runbook_sector_expansion.md` – operational guide.

## References
- Current sector definitions: `backend/core/storage/symbol_profiles.py`
- Sector‑aware AI: `backend/core/ai/sector_prompt.py`
- Filter logic: `backend/core/analysis/filters/economic.py`, `volume.py`, `correlation.py`
- T‑Bank API: `backend/core/broker/tbank/client.py`

## Success metrics
- Number of analyzable instruments increases by ≥ 15.
- Sector‑specific filter overrides are active for ≥ 80% of instruments in new sectors.
- No false‑positive signals caused by mis‑calibrated filters in new sectors.
- AI confidence scores for new‑sector signals remain within historical range.

---

*This document is the developer’s task for Sprint 4. Any questions about scope or implementation should be discussed before coding begins.*