"""
OPSRECALL Core Package.
Provides memory management, incident reasoning, Hindsight integration,
learning engine, and evaluation framework.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .evaluation import EvaluationFramework, get_evaluation_framework
    from .hindsight_client import HindsightClientWrapper, get_hindsight_client
    from .incident_engine import IncidentEngine, get_incident_engine
    from .investigation import InvestigationEngine, get_investigation_engine
    from .learning_engine import LearningEngine, get_learning_engine
    from .llm_engine import LLMEngine, get_llm_engine
    from .memory_manager import MemoryManager, get_memory_manager

__all__ = [
    "EvaluationFramework",
    "HindsightClientWrapper",
    "IncidentEngine",
    "InvestigationEngine",
    "LLMEngine",
    "LearningEngine",
    "MemoryManager",
    "get_evaluation_framework",
    "get_hindsight_client",
    "get_incident_engine",
    "get_investigation_engine",
    "get_learning_engine",
    "get_llm_engine",
    "get_memory_manager",
]

_EXPORTS = {
    "EvaluationFramework": ("core.evaluation", "EvaluationFramework"),
    "get_evaluation_framework": ("core.evaluation", "get_evaluation_framework"),
    "HindsightClientWrapper": ("core.hindsight_client", "HindsightClientWrapper"),
    "get_hindsight_client": ("core.hindsight_client", "get_hindsight_client"),
    "IncidentEngine": ("core.incident_engine", "IncidentEngine"),
    "get_incident_engine": ("core.incident_engine", "get_incident_engine"),
    "InvestigationEngine": ("core.investigation", "InvestigationEngine"),
    "get_investigation_engine": ("core.investigation", "get_investigation_engine"),
    "LearningEngine": ("core.learning_engine", "LearningEngine"),
    "get_learning_engine": ("core.learning_engine", "get_learning_engine"),
    "LLMEngine": ("core.llm_engine", "LLMEngine"),
    "get_llm_engine": ("core.llm_engine", "get_llm_engine"),
    "MemoryManager": ("core.memory_manager", "MemoryManager"),
    "get_memory_manager": ("core.memory_manager", "get_memory_manager"),
}


def __getattr__(name: str) -> Any:
    if name in _EXPORTS:
        mod_name, attr = _EXPORTS[name]
        mod = importlib.import_module(mod_name)
        val = getattr(mod, attr)
        globals()[name] = val
        return val
    raise AttributeError(f"module 'core' has no attribute '{name}'")
