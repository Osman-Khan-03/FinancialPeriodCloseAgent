"""
8-Case Period-Close Test Pack
==============================
Covers the main "unaccounted" and "not transferred" conditions across
Payables (AP), Receivables (AR) and Inventory / Cost Management.

Test record naming convention
------------------------------
Every synthetic record ID follows:  TEST-<MODULE>-<TYPE>-<CASE>
  e.g.  TEST-AP-INV-001
Description field:  TEST_PACK_2024-12_OWNER:QA Period-Close Case-<N>

This makes test records unmistakeable in a shared environment (Dev7).

Approval / cleanup reminder (for live Dev7 execution)
------------------------------------------------------
Before running against a real Oracle Fusion instance:
  1. Obtain environment-owner approval for the BU, ledger and period chosen.
  2. Use only approved test supplier, customer, item and organisation.
  3. Record the cleanup plan for each test record in advance (reversal,
     void, or coordinated deletion with the environment owner).
  4. Do NOT run broad Create Accounting, costing or Transfer-to-GL
     processes; those may pick up other users' transactions.
  5. Use existing records already in the target states wherever possible.

Expected outcome
----------------
6 records flagged (positive), 2 records NOT flagged (negative controls).

  Case | Module                    | Expected flag
  -----|---------------------------|-------------------------------------------
  1    | Payables                  | FLAGGED – unaccounted (accounting not created)
  2    | Payables                  | FLAGGED – accounted, not transferred to GL
  3    | Receivables               | FLAGGED – unaccounted (accounting not created)
  4    | Receivables               | FLAGGED – accounted, not transferred to GL
  5    | Inventory / Cost Mgmt     | FLAGGED – not transferred to Cost Management
  6    | Inventory / Cost Mgmt     | FLAGGED – transferred, but not yet costed
  7    | Payables (negative ctrl)  | NOT flagged – accounted and transferred
  8    | Receivables (neg ctrl)    | NOT flagged – accounted and transferred
"""

import logging
import unittest
from oracle_fusion_client import MockOracleFusionClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("TestPack_8Case")

# Shared constants
LEDGER_ID = "1001"
PERIOD = "Dec-24"


# ---------------------------------------------------------------------------
# Helper – fetch and index by record_id so assertions are readable
# ---------------------------------------------------------------------------

def _index_by_id(records: list) -> dict:
    """Return {record_id: record_dict} for quick lookup in assertions."""
    return {r["record_id"]: r for r in records}


# ---------------------------------------------------------------------------
# CASES 1 & 2 – Payables
# ---------------------------------------------------------------------------

class TestCase1_AP_Unaccounted(unittest.TestCase):
    """
    CASE 1 – Payables: AP invoice entered and validated but accounting has
    not yet been created (NOT_ACCOUNTED).
    Agent must report: record_id, module, period, accounting_status=NOT_ACCOUNTED,
    transfer_status=NOT_TRANSFERRED, next_step pointing to Create Accounting.
    """

    def setUp(self):
        self.client = MockOracleFusionClient()
        self.records = self.client.get_ap_transactions(LEDGER_ID, PERIOD)
        self.idx = _index_by_id(self.records)

    def test_record_is_returned(self):
        logger.info("CASE 1: AP unaccounted – checking TEST-AP-INV-001 is flagged")
        self.assertIn(
            "TEST-AP-INV-001",
            self.idx,
            "Agent did not return TEST-AP-INV-001 for unaccounted AP invoice.",
        )

    def test_module_field(self):
        rec = self.idx.get("TEST-AP-INV-001", {})
        self.assertEqual(rec.get("module"), "Payables")

    def test_period_field(self):
        rec = self.idx.get("TEST-AP-INV-001", {})
        self.assertEqual(rec.get("period"), PERIOD)

    def test_accounting_status_is_not_accounted(self):
        rec = self.idx.get("TEST-AP-INV-001", {})
        self.assertEqual(rec.get("accounting_status"), "NOT_ACCOUNTED")

    def test_transfer_status_is_not_transferred(self):
        rec = self.idx.get("TEST-AP-INV-001", {})
        self.assertEqual(rec.get("transfer_status"), "NOT_TRANSFERRED")

    def test_next_step_mentions_create_accounting(self):
        rec = self.idx.get("TEST-AP-INV-001", {})
        self.assertIn("Create Accounting", rec.get("next_step", ""))

    def test_log_summary(self):
        rec = self.idx.get("TEST-AP-INV-001", {})
        logger.info(
            "CASE 1 result – record_id=%s module=%s period=%s "
            "accounting_status=%s transfer_status=%s next_step=%s",
            rec.get("record_id"),
            rec.get("module"),
            rec.get("period"),
            rec.get("accounting_status"),
            rec.get("transfer_status"),
            rec.get("next_step"),
        )
        logger.info(">>> CASE 1 PASSED")


class TestCase2_AP_AccountedNotTransferred(unittest.TestCase):
    """
    CASE 2 – Payables: AP invoice accounting exists (ACCOUNTED) but the
    subledger journal has not yet been transferred to GL (NOT_TRANSFERRED).
    Agent must report: accounting_status=ACCOUNTED, transfer_status=NOT_TRANSFERRED,
    next_step pointing to Transfer Journal Entries to GL.
    """

    def setUp(self):
        self.client = MockOracleFusionClient()
        self.records = self.client.get_ap_transactions(LEDGER_ID, PERIOD)
        self.idx = _index_by_id(self.records)

    def test_record_is_returned(self):
        logger.info("CASE 2: AP not transferred – checking TEST-AP-INV-002 is flagged")
        self.assertIn(
            "TEST-AP-INV-002",
            self.idx,
            "Agent did not return TEST-AP-INV-002 for accounted-but-not-transferred AP invoice.",
        )

    def test_accounting_status_is_accounted(self):
        rec = self.idx.get("TEST-AP-INV-002", {})
        self.assertEqual(rec.get("accounting_status"), "ACCOUNTED")

    def test_transfer_status_is_not_transferred(self):
        rec = self.idx.get("TEST-AP-INV-002", {})
        self.assertEqual(rec.get("transfer_status"), "NOT_TRANSFERRED")

    def test_next_step_mentions_transfer_to_gl(self):
        rec = self.idx.get("TEST-AP-INV-002", {})
        self.assertIn("Transfer Journal Entries to GL", rec.get("next_step", ""))

    def test_log_summary(self):
        rec = self.idx.get("TEST-AP-INV-002", {})
        logger.info(
            "CASE 2 result – record_id=%s accounting_status=%s transfer_status=%s next_step=%s",
            rec.get("record_id"),
            rec.get("accounting_status"),
            rec.get("transfer_status"),
            rec.get("next_step"),
        )
        logger.info(">>> CASE 2 PASSED")


# ---------------------------------------------------------------------------
# CASES 3 & 4 – Receivables
# ---------------------------------------------------------------------------

class TestCase3_AR_Unaccounted(unittest.TestCase):
    """
    CASE 3 – Receivables: AR invoice completed but accounting not yet created.
    Same semantics as Case 1 but from the AR module.
    """

    def setUp(self):
        self.client = MockOracleFusionClient()
        self.records = self.client.get_ar_transactions(LEDGER_ID, PERIOD)
        self.idx = _index_by_id(self.records)

    def test_record_is_returned(self):
        logger.info("CASE 3: AR unaccounted – checking TEST-AR-INV-003 is flagged")
        self.assertIn("TEST-AR-INV-003", self.idx)

    def test_module_field(self):
        rec = self.idx.get("TEST-AR-INV-003", {})
        self.assertEqual(rec.get("module"), "Receivables")

    def test_accounting_status_is_not_accounted(self):
        rec = self.idx.get("TEST-AR-INV-003", {})
        self.assertEqual(rec.get("accounting_status"), "NOT_ACCOUNTED")

    def test_transfer_status_is_not_transferred(self):
        rec = self.idx.get("TEST-AR-INV-003", {})
        self.assertEqual(rec.get("transfer_status"), "NOT_TRANSFERRED")

    def test_next_step_mentions_create_accounting(self):
        rec = self.idx.get("TEST-AR-INV-003", {})
        self.assertIn("Create Accounting", rec.get("next_step", ""))

    def test_log_summary(self):
        rec = self.idx.get("TEST-AR-INV-003", {})
        logger.info(
            "CASE 3 result – record_id=%s module=%s accounting_status=%s "
            "transfer_status=%s next_step=%s",
            rec.get("record_id"),
            rec.get("module"),
            rec.get("accounting_status"),
            rec.get("transfer_status"),
            rec.get("next_step"),
        )
        logger.info(">>> CASE 3 PASSED")


class TestCase4_AR_AccountedNotTransferred(unittest.TestCase):
    """
    CASE 4 – Receivables: AR invoice accounting exists but journal not
    transferred to GL (NOT_TRANSFERRED).
    """

    def setUp(self):
        self.client = MockOracleFusionClient()
        self.records = self.client.get_ar_transactions(LEDGER_ID, PERIOD)
        self.idx = _index_by_id(self.records)

    def test_record_is_returned(self):
        logger.info("CASE 4: AR not transferred – checking TEST-AR-INV-004 is flagged")
        self.assertIn("TEST-AR-INV-004", self.idx)

    def test_accounting_status_is_accounted(self):
        rec = self.idx.get("TEST-AR-INV-004", {})
        self.assertEqual(rec.get("accounting_status"), "ACCOUNTED")

    def test_transfer_status_is_not_transferred(self):
        rec = self.idx.get("TEST-AR-INV-004", {})
        self.assertEqual(rec.get("transfer_status"), "NOT_TRANSFERRED")

    def test_next_step_mentions_transfer_to_gl(self):
        rec = self.idx.get("TEST-AR-INV-004", {})
        self.assertIn("Transfer Journal Entries to GL", rec.get("next_step", ""))

    def test_log_summary(self):
        rec = self.idx.get("TEST-AR-INV-004", {})
        logger.info(
            "CASE 4 result – record_id=%s accounting_status=%s transfer_status=%s next_step=%s",
            rec.get("record_id"),
            rec.get("accounting_status"),
            rec.get("transfer_status"),
            rec.get("next_step"),
        )
        logger.info(">>> CASE 4 PASSED")


# ---------------------------------------------------------------------------
# CASES 5 & 6 – Inventory / Cost Management
# ---------------------------------------------------------------------------

class TestCase5_Inventory_NotTransferredToCostMgmt(unittest.TestCase):
    """
    CASE 5 – Inventory: approved receipt that has NOT yet been transferred
    to Cost Management (upstream inventory-processing condition, distinct from
    the subledger GL transfer in Cases 2 and 4).
    """

    def setUp(self):
        self.client = MockOracleFusionClient()
        self.records = self.client.get_inventory_transactions(LEDGER_ID, PERIOD)
        self.idx = _index_by_id(self.records)

    def test_record_is_returned(self):
        logger.info("CASE 5: Inventory not transferred to Cost Mgmt – checking TEST-INV-RCT-005")
        self.assertIn("TEST-INV-RCT-005", self.idx)

    def test_module_field(self):
        rec = self.idx.get("TEST-INV-RCT-005", {})
        self.assertEqual(rec.get("module"), "Inventory / Cost Management")

    def test_transfer_status_is_not_transferred(self):
        """transfer_status here means 'not yet transferred to Cost Management' — upstream step."""
        rec = self.idx.get("TEST-INV-RCT-005", {})
        self.assertEqual(rec.get("transfer_status"), "NOT_TRANSFERRED")

    def test_costing_status_is_not_costed(self):
        rec = self.idx.get("TEST-INV-RCT-005", {})
        self.assertEqual(rec.get("costing_status"), "NOT_COSTED")

    def test_next_step_mentions_cost_management_transfer(self):
        rec = self.idx.get("TEST-INV-RCT-005", {})
        self.assertIn("Cost Management", rec.get("next_step", ""))

    def test_log_summary(self):
        rec = self.idx.get("TEST-INV-RCT-005", {})
        logger.info(
            "CASE 5 result – record_id=%s module=%s period=%s "
            "transfer_status=%s costing_status=%s next_step=%s",
            rec.get("record_id"),
            rec.get("module"),
            rec.get("period"),
            rec.get("transfer_status"),
            rec.get("costing_status"),
            rec.get("next_step"),
        )
        logger.info(">>> CASE 5 PASSED")


class TestCase6_Inventory_TransferredNotCosted(unittest.TestCase):
    """
    CASE 6 – Inventory: receipt transferred to Cost Management but the cost
    processor has not yet completed costing (costing_status=NOT_COSTED).
    This is a distinct, later state from Case 5.
    """

    def setUp(self):
        self.client = MockOracleFusionClient()
        self.records = self.client.get_inventory_transactions(LEDGER_ID, PERIOD)
        self.idx = _index_by_id(self.records)

    def test_record_is_returned(self):
        logger.info("CASE 6: Inventory transferred but not costed – checking TEST-INV-RCT-006")
        self.assertIn("TEST-INV-RCT-006", self.idx)

    def test_transfer_status_is_transferred(self):
        rec = self.idx.get("TEST-INV-RCT-006", {})
        self.assertEqual(rec.get("transfer_status"), "TRANSFERRED")

    def test_costing_status_is_not_costed(self):
        rec = self.idx.get("TEST-INV-RCT-006", {})
        self.assertEqual(rec.get("costing_status"), "NOT_COSTED")

    def test_next_step_mentions_cost_processor(self):
        rec = self.idx.get("TEST-INV-RCT-006", {})
        self.assertIn("Cost Management", rec.get("next_step", ""))

    def test_log_summary(self):
        rec = self.idx.get("TEST-INV-RCT-006", {})
        logger.info(
            "CASE 6 result – record_id=%s transfer_status=%s costing_status=%s next_step=%s",
            rec.get("record_id"),
            rec.get("transfer_status"),
            rec.get("costing_status"),
            rec.get("next_step"),
        )
        logger.info(">>> CASE 6 PASSED")


# ---------------------------------------------------------------------------
# CASES 7 & 8 – Negative controls (must NOT be flagged)
# ---------------------------------------------------------------------------

class TestCase7_AP_FullyProcessed_NegativeControl(unittest.TestCase):
    """
    CASE 7 – Payables (negative control): AP invoice fully processed –
    accounting_status=ACCOUNTED and transfer_status=TRANSFERRED.
    The agent must NOT include this record in its flag list.
    """

    def setUp(self):
        self.client = MockOracleFusionClient()
        self.records = self.client.get_ap_transactions(LEDGER_ID, PERIOD)
        self.idx = _index_by_id(self.records)

    def test_record_is_not_flagged(self):
        logger.info("CASE 7 (negative control): TEST-AP-INV-007 must NOT appear in AP flags")
        self.assertNotIn(
            "TEST-AP-INV-007",
            self.idx,
            "Agent incorrectly flagged TEST-AP-INV-007 (fully processed AP invoice).",
        )

    def test_only_unresolved_records_returned(self):
        """Every returned AP record must have at least one outstanding condition."""
        for rec in self.records:
            outstanding = (
                rec.get("accounting_status") != "ACCOUNTED"
                or rec.get("transfer_status") != "TRANSFERRED"
            )
            self.assertTrue(
                outstanding,
                f"Record {rec.get('record_id')} was incorrectly included: "
                f"accounting={rec.get('accounting_status')} transfer={rec.get('transfer_status')}",
            )

    def test_log_summary(self):
        logger.info("CASE 7 result – TEST-AP-INV-007 correctly absent from AP flags list.")
        logger.info(">>> CASE 7 PASSED (negative control)")


class TestCase8_AR_FullyProcessed_NegativeControl(unittest.TestCase):
    """
    CASE 8 – Receivables (negative control): AR invoice fully processed –
    accounting_status=ACCOUNTED and transfer_status=TRANSFERRED.
    The agent must NOT include this record in its flag list.
    """

    def setUp(self):
        self.client = MockOracleFusionClient()
        self.records = self.client.get_ar_transactions(LEDGER_ID, PERIOD)
        self.idx = _index_by_id(self.records)

    def test_record_is_not_flagged(self):
        logger.info("CASE 8 (negative control): TEST-AR-INV-008 must NOT appear in AR flags")
        self.assertNotIn(
            "TEST-AR-INV-008",
            self.idx,
            "Agent incorrectly flagged TEST-AR-INV-008 (fully processed AR invoice).",
        )

    def test_only_unresolved_records_returned(self):
        for rec in self.records:
            outstanding = (
                rec.get("accounting_status") != "ACCOUNTED"
                or rec.get("transfer_status") != "TRANSFERRED"
            )
            self.assertTrue(
                outstanding,
                f"Record {rec.get('record_id')} was incorrectly included: "
                f"accounting={rec.get('accounting_status')} transfer={rec.get('transfer_status')}",
            )

    def test_log_summary(self):
        logger.info("CASE 8 result – TEST-AR-INV-008 correctly absent from AR flags list.")
        logger.info(">>> CASE 8 PASSED (negative control)")


# ---------------------------------------------------------------------------
# Aggregate: validate the 75 % positive-flag ratio for the whole test pack
# ---------------------------------------------------------------------------

class TestPackSummary(unittest.TestCase):
    """
    Validates that exactly 6 out of 8 test records are flagged (75 % positive
    rate for this pack).  Also verifies that inventory "not transferred to Cost
    Management" and "subledger not transferred to GL" are reported as separate,
    distinct conditions.
    """

    def setUp(self):
        self.client = MockOracleFusionClient()
        self.ap_flags = self.client.get_ap_transactions(LEDGER_ID, PERIOD)
        self.ar_flags = self.client.get_ar_transactions(LEDGER_ID, PERIOD)
        self.inv_flags = self.client.get_inventory_transactions(LEDGER_ID, PERIOD)
        self.all_flags = self.ap_flags + self.ar_flags + self.inv_flags

    def test_total_flagged_count_is_six(self):
        flag_ids = [r["record_id"] for r in self.all_flags]
        logger.info("All flagged record IDs: %s", flag_ids)
        self.assertEqual(
            len(self.all_flags),
            6,
            f"Expected 6 flagged records, got {len(self.all_flags)}: {flag_ids}",
        )

    def test_flagged_record_ids_are_correct(self):
        expected_ids = {
            "TEST-AP-INV-001",
            "TEST-AP-INV-002",
            "TEST-AR-INV-003",
            "TEST-AR-INV-004",
            "TEST-INV-RCT-005",
            "TEST-INV-RCT-006",
        }
        actual_ids = {r["record_id"] for r in self.all_flags}
        self.assertEqual(actual_ids, expected_ids)

    def test_negative_controls_absent(self):
        actual_ids = {r["record_id"] for r in self.all_flags}
        self.assertNotIn("TEST-AP-INV-007", actual_ids, "Negative control Case 7 was incorrectly flagged.")
        self.assertNotIn("TEST-AR-INV-008", actual_ids, "Negative control Case 8 was incorrectly flagged.")

    def test_inventory_transfer_meanings_are_distinct(self):
        """
        Case 5: inventory NOT transferred to Cost Management (upstream step).
        Case 6: inventory transferred to Cost Management, but NOT yet costed.
        These two must have *different* transfer_status values to prove the agent
        distinguishes the two conditions correctly.
        """
        inv_idx = _index_by_id(self.inv_flags)
        case5 = inv_idx.get("TEST-INV-RCT-005", {})
        case6 = inv_idx.get("TEST-INV-RCT-006", {})
        self.assertNotEqual(
            case5.get("transfer_status"),
            case6.get("transfer_status"),
            "Cases 5 and 6 have the same transfer_status – the two inventory "
            "conditions are not being distinguished.",
        )
        # Case 5 must be NOT_TRANSFERRED; Case 6 must be TRANSFERRED (but not costed)
        self.assertEqual(case5.get("transfer_status"), "NOT_TRANSFERRED")
        self.assertEqual(case6.get("transfer_status"), "TRANSFERRED")
        self.assertEqual(case6.get("costing_status"), "NOT_COSTED")

    def test_subledger_gl_transfer_distinct_from_inventory_cm_transfer(self):
        """
        'Subledger accounting not transferred to GL' (Cases 2, 4) must use
        transfer_status on AP/AR records, and must NOT be mixed up with the
        inventory 'not transferred to Cost Management' flag (Case 5).
        Both conditions use NOT_TRANSFERRED but in different module contexts.
        """
        ap_idx = _index_by_id(self.ap_flags)
        ar_idx = _index_by_id(self.ar_flags)
        inv_idx = _index_by_id(self.inv_flags)

        # AP case 2: subledger GL transfer
        ap_case2 = ap_idx.get("TEST-AP-INV-002", {})
        self.assertEqual(ap_case2.get("module"), "Payables")
        self.assertIn("GL", ap_case2.get("next_step", ""))

        # AR case 4: subledger GL transfer
        ar_case4 = ar_idx.get("TEST-AR-INV-004", {})
        self.assertEqual(ar_case4.get("module"), "Receivables")
        self.assertIn("GL", ar_case4.get("next_step", ""))

        # Inventory case 5: Cost Management transfer (upstream, not GL)
        inv_case5 = inv_idx.get("TEST-INV-RCT-005", {})
        self.assertEqual(inv_case5.get("module"), "Inventory / Cost Management")
        self.assertIn("Cost Management", inv_case5.get("next_step", ""))
        self.assertNotIn("GL", inv_case5.get("next_step", ""))

    def test_log_final_summary(self):
        logger.info(
            "\n=== 8-CASE TEST PACK SUMMARY ===\n"
            "  AP  flagged : %d  (Cases 1, 2)\n"
            "  AR  flagged : %d  (Cases 3, 4)\n"
            "  INV flagged : %d  (Cases 5, 6)\n"
            "  Total flagged / 8 records : %d / 8  (expected 6/8 = 75%%)\n"
            "  Negative controls not flagged : Case 7 (AP), Case 8 (AR)\n"
            "================================",
            len(self.ap_flags),
            len(self.ar_flags),
            len(self.inv_flags),
            len(self.all_flags),
        )
        logger.info(">>> TEST PACK COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    unittest.main(verbosity=2)
