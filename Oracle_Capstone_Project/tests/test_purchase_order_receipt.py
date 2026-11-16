import logging
import unittest
from oracle_fusion_client import MockOracleFusionClient
from close_agent import FinancialCloseAgent

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("PO_Receipt_Test")

class TestPurchaseOrderReceiptCosting(unittest.TestCase):
    """
    Unit/integration tests targeting the Costing area of Oracle Fusion.
    Focuses on a single Purchase Order receipt costing validation test.
    """

    def test_single_purchase_order_receipt_costing_failure(self):
        """
        Scenario 1: Test with a single PO receipt having a Costing error in Oracle Fusion SCM/Costing.
        The Agent should detect the blocker, inform the user about the ledger/reason, and abort the close.
        """
        logger.info("\n=== RUNNING TEST: Single PO Receipt Costing Failure ===")
        
        # Initialize client with default scenario where Ledger 1001 has a PO costing error
        # Specifically: PO-2024-002, Receipt RC-99012 has a missing cost definition error
        client = MockOracleFusionClient(scenario_name="po_costing_hold_only")
        agent = FinancialCloseAgent(client)
        
        result = agent.verify_and_close_ledgers("Dec-24")
        
        # Verify result is BLOCKED
        self.assertEqual(result["status"], "BLOCKED")
        
        ledgers_report = result["ledgers_report"]
        us_ledger = ledgers_report["US Primary Ledger"]
        
        # Verify the ledger status is BLOCKED
        self.assertEqual(us_ledger["status"], "BLOCKED")
        self.assertIn("CN-90812", str(us_ledger["blockers"]))
        
        # Verify the exact blocker reason was found
        self.assertTrue(len(us_ledger["blockers"]) > 0)
        blocker = us_ledger["blockers"][0]
        logger.info(f"Blocker detected successfully:\n{blocker}")
        
        self.assertIn("RC-99012", blocker)
        self.assertIn("PO-2024-002", blocker)
        self.assertIn("CN-90812", blocker)
        self.assertIn("Item cost definition is missing", blocker)
        
        logger.info(">>> TEST PASSED: Agent successfully identified the specific PO receipt costing blocker and blocked the close.")

    def test_single_purchase_order_receipt_costing_resolved(self):
        """
        Scenario 2: Test after the Costing issue on the PO receipt is resolved in SCM.
        The Agent should verify everything is clear and successfully complete the financial close.
        """
        logger.info("\n=== RUNNING TEST: Single PO Receipt Costing Resolved ===")
        
        # Initialize client with 'all_clear' scenario where the PO receipt error is resolved
        client = MockOracleFusionClient(scenario_name="all_clear")
        agent = FinancialCloseAgent(client)
        
        result = agent.verify_and_close_ledgers("Dec-24")
        
        # Verify result is COMPLETED
        self.assertEqual(result["status"], "COMPLETED")
        
        ledgers_report = result["ledgers_report"]
        us_ledger = ledgers_report["US Primary Ledger"]
        
        # Verify ledger was successfully closed
        self.assertEqual(us_ledger["status"], "SUCCESS")
        self.assertEqual(us_ledger["costing_status"], "Closed")
        self.assertEqual(us_ledger["gl_status"], "Closed")
        self.assertIn("Closed Costing period.", us_ledger["actions_taken"])
        self.assertIn("Closed General Ledger period.", us_ledger["actions_taken"])
        
        logger.info(">>> TEST PASSED: Agent successfully completed the financial close after costing resolution.")

if __name__ == "__main__":
    unittest.main()
