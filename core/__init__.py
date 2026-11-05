"""
OPSRECALL Core Package.
Provides memory management, incident reasoning, Hindsight integration,
learning engine, and evaluation framework.
"""

from .hindsight_client import HindsightClientWrapper, get_hindsight_client
from .incident_engine import IncidentEngine, get_incident_engine
from .memory_manager import MemoryManager, get_memory_manager
from .llm_engine import LLMEngine, get_llm_engine
from .investigation import InvestigationEngine, get_investigation_engine
from .learning_engine import LearningEngine, get_learning_engine
from .evaluation import EvaluationFramework, get_evaluation_framework

__all__ = [
    "HindsightClientWrapper",
    "get_hindsight_client",
    "IncidentEngine",
    "get_incident_engine",
    "MemoryManager",
    "get_memory_manager",
    "LLMEngine",
    "get_llm_engine",
    "InvestigationEngine",
    "get_investigation_engine",
    "LearningEngine",
    "get_learning_engine",
    "EvaluationFramework",
    "get_evaluation_framework",
]

