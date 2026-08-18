"""
Agent-Eval-Guard: The Continuous In-Situ Evaluation & Semantic Drift CI Gate.
"""

from agenteval.core import (
    AgentEvalGuard,
    CUSUMDriftDetector,
    CryptographicEvalLedger,
    EvalReceipt,
    InSituAgentEvaluator,
    GENESIS_HASH,
)

__all__ = [
    "AgentEvalGuard",
    "CUSUMDriftDetector",
    "CryptographicEvalLedger",
    "EvalReceipt",
    "InSituAgentEvaluator",
    "GENESIS_HASH",
]

__version__ = "1.0.0"
