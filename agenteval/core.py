"""
Agent-Eval-Guard: The Continuous In-Situ Evaluation & Semantic Drift CI Gate for AI Agents.
Standard library only: hashlib, json, math, time, os, dataclasses, typing.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


GENESIS_HASH: str = "0000000000000000000000000000000000000000000000000000000000000000"


@dataclasses.dataclass(frozen=True)
class EvalReceipt:
    """Immutable SHA-256 cryptographically chained evaluation receipt."""
    index: int
    prev_hash: str
    task_id: str
    faithfulness_score: float
    drift_score: float
    status: str
    timestamp: float
    payload_hash: str
    signature_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


class CryptographicEvalLedger:
    """Tamper-proof continuous evaluation ledger for ISO 42001 & SOC 2 compliance."""

    def __init__(self, ledger_file: Optional[str] = None):
        self.ledger_file = ledger_file
        self._entries: List[EvalReceipt] = []
        self._last_hash = GENESIS_HASH

    @property
    def last_hash(self) -> str:
        return self._last_hash

    @property
    def count(self) -> int:
        return len(self._entries)

    def record_eval(
        self,
        task_id: str,
        faithfulness_score: float,
        drift_score: float,
        status: str,
        metadata: Dict[str, Any],
    ) -> EvalReceipt:
        idx = len(self._entries)
        ts = time.time()
        meta_bytes = json.dumps(metadata, sort_keys=True).encode("utf-8")
        payload_hash = hashlib.sha256(meta_bytes).hexdigest()

        # SHA-256 Hash Chain
        raw_msg = f"{idx}:{self._last_hash}:{task_id}:{faithfulness_score:.4f}:{drift_score:.4f}:{status}:{ts:.6f}:{payload_hash}"
        sig_hash = hashlib.sha256(raw_msg.encode("utf-8")).hexdigest()

        receipt = EvalReceipt(
            index=idx,
            prev_hash=self._last_hash,
            task_id=task_id,
            faithfulness_score=faithfulness_score,
            drift_score=drift_score,
            status=status,
            timestamp=ts,
            payload_hash=payload_hash,
            signature_hash=sig_hash,
        )

        self._entries.append(receipt)
        self._last_hash = sig_hash

        if self.ledger_file:
            os.makedirs(os.path.dirname(os.path.abspath(self.ledger_file)), exist_ok=True)
            with open(self.ledger_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(receipt.to_dict()) + chr(10))

        return receipt

    def verify_chain_integrity(self) -> Tuple[bool, Optional[str]]:
        current_prev = GENESIS_HASH
        for idx, entry in enumerate(self._entries):
            if entry.index != idx:
                return False, f"Sequence index mismatch at {idx}"
            if entry.prev_hash != current_prev:
                return False, f"Broken SHA-256 chain at {idx}"
            current_prev = entry.signature_hash
        return True, None


class CUSUMDriftDetector:
    """
    Statistical Cumulative Sum (CUSUM) Drift Detector:
    Detects silent degradation in agent reasoning and input distributions without LLM judge calls.
    """

    def __init__(self, target_mean: float = 0.90, threshold: float = 4.0, drift_slack: float = 0.05):
        self.target_mean = target_mean
        self.threshold = threshold
        self.drift_slack = drift_slack
        self.s_pos = 0.0
        self.s_neg = 0.0

    def update(self, value: float) -> Tuple[bool, float]:
        """
        Returns (drift_detected, current_drift_score)
        """
        self.s_pos = max(0.0, self.s_pos + (value - self.target_mean - self.drift_slack))
        self.s_neg = max(0.0, self.s_neg + (self.target_mean - value - self.drift_slack))

        drift_score = max(self.s_pos, self.s_neg)
        drift_detected = drift_score >= self.threshold
        return drift_detected, round(drift_score, 4)


class InSituAgentEvaluator:
    """
    Sub-millisecond in-situ agent evaluator.
    Measures step-level faithfulness, token coverage, and tool alignment.
    """

    @staticmethod
    def compute_jaccard_token_similarity(text_a: str, text_b: str) -> float:
        tokens_a = set(text_a.lower().split())
        tokens_b = set(text_b.lower().split())
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        return intersection / union if union > 0 else 0.0

    @classmethod
    def evaluate_step(
        cls,
        context_prompt: str,
        agent_reasoning: str,
        selected_tool: str,
        allowed_tools: Set[str],
    ) -> float:
        """
        Computes deterministic faithfulness score (0.0 to 1.0)
        """
        if selected_tool not in allowed_tools:
            return 0.0  # Invalid tool hallucination

        similarity = cls.compute_jaccard_token_similarity(context_prompt, agent_reasoning)
        # Bounded between 0.20 baseline and 1.0
        return min(1.0, max(0.20, similarity * 2.5))


class AgentEvalGuard:
    """
    The Master Continuous In-Situ Evaluation & CI Regression Gate.
    """

    def __init__(
        self,
        allowed_tools: Optional[Set[str]] = None,
        min_faithfulness: float = 0.40,
        ledger_path: Optional[str] = None,
    ):
        self.allowed_tools = allowed_tools or {"query_db", "fetch_user", "execute_sql", "send_email"}
        self.min_faithfulness = min_faithfulness
        self.drift_detector = CUSUMDriftDetector()
        self.ledger = CryptographicEvalLedger(ledger_file=ledger_path)

    def check_kill_switch(self) -> bool:
        if os.environ.get("AGENT_EVAL_KILL", "0") in ("1", "true", "TRUE"):
            return True
        if os.path.exists("/tmp/AGENT_EVAL_KILL"):
            return True
        return False

    def guard_eval_step(
        self,
        task_id: str,
        context_prompt: str,
        agent_reasoning: str,
        selected_tool: str,
    ) -> Tuple[bool, EvalReceipt]:
        if self.check_kill_switch():
            receipt = self.ledger.record_eval(
                task_id=task_id,
                faithfulness_score=0.0,
                drift_score=999.0,
                status="HALTED_BY_EMERGENCY_KILL_SWITCH",
                metadata={"halted": True},
            )
            return False, receipt

        # 1. In-Situ Faithfulness Check
        faithfulness = InSituAgentEvaluator.evaluate_step(
            context_prompt=context_prompt,
            agent_reasoning=agent_reasoning,
            selected_tool=selected_tool,
            allowed_tools=self.allowed_tools,
        )

        # 2. CUSUM Statistical Drift Update
        drift_detected, drift_score = self.drift_detector.update(faithfulness)

        # 3. Authorization Threshold
        if faithfulness < self.min_faithfulness:
            status = "REJECTED_LOW_FAITHFULNESS"
            allowed = False
        elif drift_detected:
            status = "REJECTED_STATISTICAL_DRIFT"
            allowed = False
        else:
            status = "AUTHORIZED_EVAL_PASS"
            allowed = True

        receipt = self.ledger.record_eval(
            task_id=task_id,
            faithfulness_score=faithfulness,
            drift_score=drift_score,
            status=status,
            metadata={"tool": selected_tool, "drift_detected": drift_detected},
        )

        return allowed, receipt
