"""LLM-free macOS computer-use primitives."""

from .client import MacOSComputerUseClient
from .models import (
    ComputerUseOperation,
    ComputerUseReadiness,
    ComputerUseReadinessStatus,
    ComputerUseResult,
    ComputerUseStatus,
    RiskDecision,
    RiskLevel,
)
from .policy import SafetyPolicy
from .readiness import DefaultPermissionProbe, PermissionProbe

__version__ = "0.1.0"

__all__ = [
    "ComputerUseOperation",
    "ComputerUseReadiness",
    "ComputerUseReadinessStatus",
    "ComputerUseResult",
    "ComputerUseStatus",
    "DefaultPermissionProbe",
    "MacOSComputerUseClient",
    "PermissionProbe",
    "RiskDecision",
    "RiskLevel",
    "SafetyPolicy",
    "__version__",
]
