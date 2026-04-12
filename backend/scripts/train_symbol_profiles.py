from __future__ import annotations

import argparse
import json

from core.services.symbol_adaptive import train_symbol_profile, train_symbol_profiles_bulk
from core.storage.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline trainer for per-symbol profiles.")
    parser.add_argument("--instrument", action="append", dest="instrument_ids", default=[], help="Instrument id, e.g. TQBR:SBER")
    parser.add_argument("--lookback-days", type=int, default=180)
    parser.add_argument("--timeframe", default="1m")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.instrument_ids:
            if len(args.instrument_ids) == 1:
                result = train_symbol_profile(db, args.instrument_ids[0], lookback_days=args.lookback_days, timeframe=args.timeframe, source="cli")
            else:
                result = train_symbol_profiles_bulk(db, args.instrument_ids, lookback_days=args.lookback_days, timeframe=args.timeframe, source="cli_bulk")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            raise SystemExit("At least one --instrument is required")
    finally:
        db.close()


if __name__ == "__main__":
    main()
