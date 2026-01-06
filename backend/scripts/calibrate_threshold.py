import sys
import os
import numpy as np
from sqlalchemy import create_engine, select, desc
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.append(os.getcwd())

from core.storage.models import Signal, Settings
from core.config import settings as app_settings


def calibrate():
    """
    Calculate recommended decision_threshold based on target Take Rates.
    Algorithm:
    1. Fetch recent signals that passed Hard Rejects (Score > 0).
    2. Calculate Quantiles.
    """
    print("Connecting to DB...")
    # Setup DB
    engine = create_engine(app_settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Fetch recent signals
    # We filter score > 0 as proxy for "Passed Hard Rejects"
    query = select(Signal).where(Signal.score > 0).order_by(desc(Signal.created_at)).limit(1000)
    signals = session.execute(query).scalars().all()

    if not signals:
        print("No eligible signals found (Score > 0). Cannot calibrate.")
        return

    scores = [s.score for s in signals]  # s.score is now score_pct (0-100)
    count = len(scores)
    print(f"Found {count} eligible signals (Hard Pass).")
    print(f"Score Pct -> Min: {min(scores)}, Max: {max(scores)}, Avg: {np.mean(scores):.1f}%")

    # Calculate Thresholds for Target Take Rates
    # Take Rate q means top q% of scores.
    # Threshold = (1-q) quantile.

    print("\n--- Calibration (Strictness) ---")
    targets = [0.20, 0.30, 0.40]  # 20%, 30%, 40% Take Rate

    for q in targets:
        # np.quantile uses 0..1 per slide.
        # We want top q, so we want the value greater than (1-q) of data.
        t_val = np.quantile(scores, 1.0 - q)
        print(f"Target Take Rate {int(q*100)}% -> Threshold: {int(t_val)}%")

    print("\nTo apply, update 'decision_threshold' in Settings.")

    # Optional: Current Setting
    current_settings = session.query(Settings).first()
    if current_settings:
        print(f"\nCurrent Setting: {current_settings.decision_threshold}")

    session.close()


if __name__ == "__main__":
    calibrate()
