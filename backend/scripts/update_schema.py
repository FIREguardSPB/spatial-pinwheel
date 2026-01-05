from core.storage.session import engine
from sqlalchemy import text, inspect

def safe_migrate_settings():
    print("Migrating Settings table schema (SAFE)...")
    
    # 1. Define expected columns and their defaults/types
    # For SQLite, we add columns if missing.
    # Note: SQLite ALTER TABLE ADD COLUMN support is limited but works for simple types.
    
    new_columns = [
        ("atr_stop_hard_min", "REAL DEFAULT 0.6"),
        ("atr_stop_hard_max", "REAL DEFAULT 2.5"),
        ("atr_stop_soft_min", "REAL DEFAULT 0.8"),
        ("atr_stop_soft_max", "REAL DEFAULT 2.0"),
        ("rr_min", "REAL DEFAULT 1.5"),
        ("decision_threshold", "INTEGER DEFAULT 70"),
        ("w_regime", "INTEGER DEFAULT 20"),
        ("w_volatility", "INTEGER DEFAULT 15"),
        ("w_momentum", "INTEGER DEFAULT 15"),
        ("w_levels", "INTEGER DEFAULT 20"),
        ("w_costs", "INTEGER DEFAULT 15"),
        ("w_liquidity", "INTEGER DEFAULT 5")
    ]
    
    with engine.connect() as conn:
        inspector = inspect(conn)
        existing_columns = [c['name'] for c in inspector.get_columns("settings")]
        
        for col_name, col_def in new_columns:
            if col_name not in existing_columns:
                print(f"Adding column: {col_name}")
                try:
                    conn.execute(text(f"ALTER TABLE settings ADD COLUMN {col_name} {col_def}"))
                    conn.commit()
                except Exception as e:
                    print(f"Error adding {col_name}: {e}")
            else:
                print(f"Column {col_name} exists.")
                
    print("Migration complete.")

if __name__ == "__main__":
    safe_migrate_settings()
