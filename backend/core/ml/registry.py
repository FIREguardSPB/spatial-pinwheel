from __future__ import annotations

from pathlib import Path
from typing import Any

from joblib import dump, load


_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_ARTIFACT_DIR = _BACKEND_ROOT / 'runtime' / 'ml_models'


def get_artifact_dir() -> Path:
    _ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    return _ARTIFACT_DIR


def artifact_path_for(run_id: str, target: str) -> Path:
    safe_target = ''.join(ch if ch.isalnum() or ch in {'_', '-'} else '_' for ch in str(target or 'model'))
    return get_artifact_dir() / f'{safe_target}_{run_id}.joblib'


def save_artifact(run_id: str, target: str, artifact: Any) -> str:
    path = artifact_path_for(run_id, target)
    dump(artifact, path)
    return str(path)


def load_artifact(path: str | None) -> Any | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return None
    return load(file_path)
