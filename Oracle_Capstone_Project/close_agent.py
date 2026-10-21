import logging

logger = logging.getLogger("FinancialCloseAgent")

class FinancialCloseAgent:
    """
    Financial Period Close Agent for Oracle Fusion SCM/Financials.
    Validates ledger period readiness, tracks blocking transactions,
    notifies users of costing/accounting blockers, and triggers period close.
    """
    def __init__(self, client):
        self.client = client

    def verify_and_close_ledgers(self, period_name: str) -> dict:
        """
        Runs the financial close checklist for all active ledgers.
        If all ledgers are clear, closes the costing and GL periods.
        If any ledger is blocked, reports the exact reason and transaction details.
        """
        logger.info(f"Starting period close validation for period: {period_name}")
        
        try:
            ledgers = self.client.get_ledgers()
        except Exception as e:
            logger.error(f"Failed to fetch ledgers: {e}")
            return {
                "status": "FAILED",
                "error": f"Failed to retrieve active ledgers: {str(e)}",
                "ledgers_report": {}
            }

        report = {}
        all_closed = True
        
        for ledger in ledgers:
            ledger_id = ledger["ledger_id"]
            ledger_name = ledger["name"]
            
            logger.info(f"Checking ledger: {ledger_name} (ID: {ledger_id})")
            
            # 1. Fetch current period status
            try:
                statuses = self.client.get_period_statuses(ledger_id, period_name)
            except Exception as e:
                logger.error(f"Failed to fetch period status for ledger {ledger_name}: {e}")
                report[ledger_name] = {
                    "ledger_id": ledger_id,
                    "status": "ERROR",
                    "reason": f"Could not retrieve period statuses: {str(e)}"
                }
                all_closed = False
                continue

            gl_status = statuses.get("GL", "Open")
            cost_status = statuses.get("COST", "Open")
            
            # If both are already closed, skip
            if gl_status == "Closed" and cost_status == "Closed":
                report[ledger_name] = {
                    "ledger_id": ledger_id,
                    "costing_status": "Closed",
                    "gl_status": "Closed",
                    "status": "SUCCESS",
                    "reason": "Already fully closed."
                }
                continue

            # 2. Check for costing blockers (transactions unprocessed or in error)
            blockers = []
            try:
                blockers = self.client.get_costing_transactions(ledger_id, period_name)
            except Exception as e:
                logger.error(f"Failed to check costing transactions for ledger {ledger_name}: {e}")
                report[ledger_name] = {
                    "ledger_id": ledger_id,
                    "status": "ERROR",
                    "reason": f"Could not retrieve costing transactions: {str(e)}"
                }
                all_closed = False
                continue

            # If there are costing blockers, this ledger cannot be closed!
            if blockers:
                all_closed = False
                blocker_details = []
                for b in blockers:
                    desc = (
                        f"PO Receipt blocker found - PO: {b.get('po_number')}, "
                        f"Receipt: {b.get('receipt_number')}, Item: {b.get('item_number')}, "
                        f"Qty: {b.get('quantity')} {b.get('unit_of_measure')}. "
                        f"Cost Status: {b.get('costing_status')}, "
                        f"Accounting Status: {b.get('accounting_status')}. "
                        f"Reason: {b.get('error_message') or 'Unprocessed'}"
                    )
                    blocker_details.append(desc)

                report[ledger_name] = {
                    "ledger_id": ledger_id,
                    "costing_status": cost_status,
                    "gl_status": gl_status,
                    "status": "BLOCKED",
                    "reason": f"Blocked by {len(blockers)} pending or errored transactions.",
                    "blockers": blocker_details
                }
                logger.warning(f"Ledger '{ledger_name}' is BLOCKED from closing.")
                continue

            # 3. No blockers! We can proceed with closing the periods for this ledger
            ledger_report = {
                "ledger_id": ledger_id,
                "costing_status": cost_status,
                "gl_status": gl_status,
                "status": "IN_PROGRESS",
                "actions_taken": []
            }

            # Close Costing if open
            if cost_status == "Open":
                try:
                    self.client.close_period(ledger_id, period_name, "COST")
                    ledger_report["costing_status"] = "Closed"
                    ledger_report["actions_taken"].append("Closed Costing period.")
                    logger.info(f"Successfully closed COSTING period for ledger '{ledger_name}'.")
                except Exception as e:
                    logger.error(f"Failed to close COSTING period for ledger {ledger_name}: {e}")
                    ledger_report["status"] = "FAILED"
                    ledger_report["reason"] = f"Failed to close Costing period: {str(e)}"
                    all_closed = False
                    report[ledger_name] = ledger_report
                    continue

            # Close GL if open
            if gl_status == "Open":
                try:
                    self.client.close_period(ledger_id, period_name, "GL")
                    ledger_report["gl_status"] = "Closed"
                    ledger_report["actions_taken"].append("Closed General Ledger period.")
                    logger.info(f"Successfully closed GL period for ledger '{ledger_name}'.")
                except Exception as e:
                    logger.error(f"Failed to close GL period for ledger {ledger_name}: {e}")
                    ledger_report["status"] = "FAILED"
                    ledger_report["reason"] = f"Failed to close GL period: {str(e)}"
                    all_closed = False
                    report[ledger_name] = ledger_report
                    continue

            ledger_report["status"] = "SUCCESS"
            ledger_report["reason"] = "Successfully closed all periods."
            report[ledger_name] = ledger_report

        final_status = "COMPLETED" if all_closed else "BLOCKED"
        logger.info(f"Period close validation completed with status: {final_status}")
        
        return {
            "status": final_status,
            "ledgers_report": report
        }
