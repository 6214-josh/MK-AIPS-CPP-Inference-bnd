from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any


def get_backend_root() -> Path:
    """
    Backend root = contains app/main.py.
    This is based on the loaded Python module path, not browser URL and not frontend path.
    """
    return Path(__file__).resolve().parents[2]


def get_project_root() -> Path:
    """
    Project root is normally the parent of backend root.

    Override:
      AIPS_PROJECT_ROOT=C:/Users/solno/OneDrive/Desktop/MINKIN/optimize

    Useful when AIPS_Launcher is placed inside backend, or when there are multiple backend-like folders.
    """
    configured = os.getenv("AIPS_PROJECT_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    backend_root = get_backend_root()
    return backend_root.parent


def get_model_dir() -> Path:
    """
    Model directory.

    Default:
      <backend_root>/models

    Override:
      AIPS_MODEL_DIR=C:/Users/solno/OneDrive/Desktop/MINKIN/optimize/MK-APIS-backend-optimize-main/models

    This prevents accidentally reading another project's models when multiple AIPS backends exist.
    """
    configured = os.getenv("AIPS_MODEL_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    return get_backend_root() / "models"


def get_tools_dir() -> Path:
    return get_backend_root() / "tools" / "model_optimization"


def get_runtime_path_info() -> Dict[str, Any]:
    backend_root = get_backend_root()
    project_root = get_project_root()
    model_dir = get_model_dir()

    return {
        "cwd": str(Path.cwd()),
        "backend_root": str(backend_root),
        "project_root": str(project_root),
        "model_dir": str(model_dir),
        "env_aips_project_root": os.getenv("AIPS_PROJECT_ROOT"),
        "env_aips_model_dir": os.getenv("AIPS_MODEL_DIR"),
        "main_py": str(backend_root / "app" / "main.py"),
        "note": (
            "model_dir is backend-relative unless AIPS_MODEL_DIR is set. "
            "If browser shows inference-cpp/bnd/models, the running FastAPI backend is inference-cpp/bnd or AIPS_MODEL_DIR points there."
        ),
    }
