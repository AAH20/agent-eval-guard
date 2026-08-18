import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agenteval.core import AgentEvalGuard, CUSUMDriftDetector, GENESIS_HASH


class TestAgentEvalGuard(unittest.TestCase):
    def setUp(self):
        self.guard = AgentEvalGuard()

    def test_in_situ_evaluation_and_ledger_integrity(self):
        # 1. High-faithfulness aligned tool step
        allowed, receipt = self.guard.guard_eval_step(
            task_id='task_query_user_01',
            context_prompt='Query database for user profile where id is 104',
            agent_reasoning='I will query database for user profile id 104',
            selected_tool='query_db',
        )
        self.assertTrue(allowed)
        self.assertEqual(receipt.status, 'AUTHORIZED_EVAL_PASS')
        self.assertGreaterEqual(receipt.faithfulness_score, 0.40)
        self.assertNotEqual(receipt.signature_hash, GENESIS_HASH)

        # 2. Verify cryptographic chain integrity
        is_valid, err = self.guard.ledger.verify_chain_integrity()
        self.assertTrue(is_valid, f'Eval ledger chain broken: {err}')

    def test_unauthorized_tool_hallucination_quarantine(self):
        # Tool not in allowed tool set -> zero faithfulness
        allowed, receipt = self.guard.guard_eval_step(
            task_id='task_rogue_tool',
            context_prompt='Fetch user logs',
            agent_reasoning='I will delete the whole bucket',
            selected_tool='unauthorized_delete_tool',
        )
        self.assertFalse(allowed)
        self.assertEqual(receipt.status, 'REJECTED_LOW_FAITHFULNESS')
        self.assertEqual(receipt.faithfulness_score, 0.0)

    def test_cusum_statistical_drift_detection(self):
        # Simulate continuous subtle drift/degradation
        detector = CUSUMDriftDetector(target_mean=0.90, threshold=1.5, drift_slack=0.05)
        drift_found = False
        for _ in range(10):
            drift_found, score = detector.update(0.30)
            if drift_found:
                break
        self.assertTrue(drift_found)
        self.assertGreaterEqual(score, 1.5)


if __name__ == '__main__':
    unittest.main()
