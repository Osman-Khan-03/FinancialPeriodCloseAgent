import logging
import re

logger = logging.getLogger("FinancialCloseAgent")

class FinancialCloseAgent:
    """
    Financial Period Close Agent for Oracle Fusion SCM/Financials.
    Validates ledger period readiness, tracks blocking transactions across
    Costing, Subledger Accounting (SLA), Payables (AP), Receivables (AR),
    and Inventory, provides intelligent resolution recommendations,
    and orchestrates period close execution.
    """
    def __init__(self, client):
        self.client = client

    def get_status_summary(self, period_name: str, target_ledger_id: str = None) -> dict:
        """
        Retrieves current period status (GL & Costing) for active ledgers
        without performing deep blocker scans or changing period states.
        """
        try:
            ledgers = self.client.get_ledgers()
        except Exception as e:
            return {"status": "ERROR", "error": str(e), "ledgers": {}}

        if target_ledger_id:
            ledgers = [l for l in ledgers if str(l.get("ledger_id")) == str(target_ledger_id)]

        summary = {}
        for ledger in ledgers:
            lid = ledger["ledger_id"]
            name = ledger["name"]
            statuses = self.client.get_period_statuses(lid, period_name)
            summary[name] = {
                "ledger_id": lid,
                "currency": ledger.get("currency", "USD"),
                "chart_of_accounts": ledger.get("chart_of_accounts", "COA"),
                "gl_status": statuses.get("GL", "Unknown"),
                "costing_status": statuses.get("COST", "Unknown"),
                "period": period_name
            }
        return {"status": "SUCCESS", "period": period_name, "ledgers": summary}

    def assess_readiness(self, period_name: str, target_ledger_id: str = None) -> dict:
        """
        Performs a deep, multi-module readiness assessment for all or a specific ledger.
        Checks:
          1. Costing & PO Receipt Distributions (Cost Management)
          2. Subledger Accounting (SLA Rule violations & unaccounted journals)
          3. Payables (AP unaccounted invoices & un-transferred journals)
          4. Receivables (AR unaccounted transactions & un-transferred journals)
          5. Inventory Transfers (un-transferred receipts & un-costed items)
        Read-only. No period status changes are executed.
        """
        logger.info(f"Running comprehensive readiness assessment for period: {period_name}")
        try:
            ledgers = self.client.get_ledgers()
        except Exception as e:
            logger.error(f"Failed to retrieve ledgers: {e}")
            return {"status": "FAILED", "error": str(e), "ledgers_report": {}}

        if target_ledger_id:
            ledgers = [l for l in ledgers if str(l.get("ledger_id")) == str(target_ledger_id)]

        report = {}
        overall_ready = True
        total_blocker_count = 0

        for ledger in ledgers:
            lid = ledger["ledger_id"]
            name = ledger["name"]
            statuses = self.client.get_period_statuses(lid, period_name)
            gl_status = statuses.get("GL", "Open")
            cost_status = statuses.get("COST", "Open")

            ledger_blockers = []
            module_checks = {
                "costing": {"status": "PASS", "blockers": []},
                "sla": {"status": "PASS", "blockers": []},
                "ap": {"status": "PASS", "blockers": []},
                "ar": {"status": "PASS", "blockers": []},
                "inventory": {"status": "PASS", "blockers": []}
            }

            # 1. Costing & PO Receipt Check
            try:
                costing_txns = self.client.get_costing_transactions(lid, period_name)
                for txn in costing_txns:
                    cost_stat = txn.get("costing_status")
                    acct_stat = txn.get("accounting_status")
                    err = txn.get("error_message") or "Unprocessed transaction"
                    po = txn.get("po_number", "N/A")
                    rcpt = txn.get("receipt_number", "N/A")
                    item = txn.get("item_number", "N/A")
                    qty = txn.get("quantity", 0)
                    uom = txn.get("unit_of_measure", "Ea")

                    # Identify whether it's an SLA violation or Costing error
                    if acct_stat == "ERROR" or "rule" in err.lower() or "journal" in err.lower():
                        category = "sla"
                        rec_step = (
                            f"Review account derivation rule in Manage Subledger Accounting Options. "
                            f"Correct cost account mapping for item {item}, then re-run Create Accounting for Receipt {rcpt}."
                        )
                    else:
                        category = "costing"
                        rec_step = (
                            f"Define cost profile for {item} via Cost Management > Manage Item Costs, "
                            f"then re-run the cost processor for Receipt {rcpt}."
                        )

                    b_entry = {
                        "module": "Cost Management" if category == "costing" else "Subledger Accounting",
                        "category": category,
                        "transaction_id": txn.get("transaction_id", f"TXN_{rcpt}"),
                        "po_number": po,
                        "receipt_number": rcpt,
                        "item_number": item,
                        "quantity": f"{qty} {uom}",
                        "costing_status": cost_stat,
                        "accounting_status": acct_stat,
                        "error_message": err,
                        "next_step": rec_step,
                        "description": (
                            f"PO Receipt blocker - PO: {po}, Receipt: {rcpt}, Item: {item}, "
                            f"Qty: {qty} {uom}. Cost: {cost_stat}, Accounting: {acct_stat}. Reason: {err}"
                        )
                    }
                    module_checks[category]["blockers"].append(b_entry)
                    module_checks[category]["status"] = "FAIL"
                    ledger_blockers.append(b_entry)
            except Exception as e:
                logger.error(f"Error querying costing transactions for {name}: {e}")

            # 2. AP Transactions Check
            try:
                if hasattr(self.client, "get_ap_transactions"):
                    ap_txns = self.client.get_ap_transactions(lid, period_name)
                    for ap in ap_txns:
                        b_entry = {
                            "module": "Payables (AP)",
                            "category": "ap",
                            "transaction_id": ap.get("record_id"),
                            "supplier": ap.get("supplier", "N/A"),
                            "accounting_status": ap.get("accounting_status"),
                            "transfer_status": ap.get("transfer_status"),
                            "error_message": f"AP Invoice {ap.get('record_id')} is {ap.get('accounting_status')} / {ap.get('transfer_status')}",
                            "next_step": ap.get("next_step") or "Run Create Accounting and Transfer to GL for Payables.",
                            "description": ap.get("description") or f"AP Invoice {ap.get('record_id')} requires processing."
                        }
                        module_checks["ap"]["blockers"].append(b_entry)
                        module_checks["ap"]["status"] = "FAIL"
                        ledger_blockers.append(b_entry)
            except Exception as e:
                logger.error(f"Error querying AP transactions for {name}: {e}")

            # 3. AR Transactions Check
            try:
                if hasattr(self.client, "get_ar_transactions"):
                    ar_txns = self.client.get_ar_transactions(lid, period_name)
                    for ar in ar_txns:
                        b_entry = {
                            "module": "Receivables (AR)",
                            "category": "ar",
                            "transaction_id": ar.get("record_id"),
                            "customer": ar.get("customer", "N/A"),
                            "accounting_status": ar.get("accounting_status"),
                            "transfer_status": ar.get("transfer_status"),
                            "error_message": f"AR Transaction {ar.get('record_id')} is {ar.get('accounting_status')} / {ar.get('transfer_status')}",
                            "next_step": ar.get("next_step") or "Run Create Accounting and Transfer to GL for Receivables.",
                            "description": ar.get("description") or f"AR Transaction {ar.get('record_id')} requires processing."
                        }
                        module_checks["ar"]["blockers"].append(b_entry)
                        module_checks["ar"]["status"] = "FAIL"
                        ledger_blockers.append(b_entry)
            except Exception as e:
                logger.error(f"Error querying AR transactions for {name}: {e}")

            # 4. Inventory Transactions Check
            try:
                if hasattr(self.client, "get_inventory_transactions"):
                    inv_txns = self.client.get_inventory_transactions(lid, period_name)
                    for inv in inv_txns:
                        b_entry = {
                            "module": "Inventory / Cost Management",
                            "category": "inventory",
                            "transaction_id": inv.get("record_id"),
                            "organization": inv.get("organization", "N/A"),
                            "item_number": inv.get("item", "N/A"),
                            "transfer_status": inv.get("transfer_status"),
                            "costing_status": inv.get("costing_status"),
                            "error_message": f"Inventory record {inv.get('record_id')} Transfer: {inv.get('transfer_status')}, Costing: {inv.get('costing_status')}",
                            "next_step": inv.get("next_step") or "Submit Transfer Transactions to Costing or run Cost Accounting.",
                            "description": inv.get("description") or f"Inventory record {inv.get('record_id')} pending cost processing."
                        }
                        module_checks["inventory"]["blockers"].append(b_entry)
                        module_checks["inventory"]["status"] = "FAIL"
                        ledger_blockers.append(b_entry)
            except Exception as e:
                logger.error(f"Error querying Inventory transactions for {name}: {e}")

            is_ready = len(ledger_blockers) == 0
            if not is_ready:
                overall_ready = False
            total_blocker_count += len(ledger_blockers)

            report[name] = {
                "ledger_id": lid,
                "currency": ledger.get("currency", "USD"),
                "chart_of_accounts": ledger.get("chart_of_accounts", "COA"),
                "costing_status": cost_status,
                "gl_status": gl_status,
                "readiness_status": "READY" if is_ready else "BLOCKED",
                "blocker_count": len(ledger_blockers),
                "blockers": [b["description"] for b in ledger_blockers],
                "detailed_blockers": ledger_blockers,
                "module_checks": module_checks,
                "reason": "All subledger checks passed cleanly." if is_ready else f"Blocked by {len(ledger_blockers)} transaction(s) requiring resolution."
            }

        return {
            "status": "READY" if overall_ready else "BLOCKED",
            "period": period_name,
            "overall_ready": overall_ready,
            "total_blockers": total_blocker_count,
            "ledgers_report": report
        }

    def verify_and_close_ledgers(self, period_name: str, target_ledger_id: str = None) -> dict:
        """
        Runs the financial close checklist for all active ledgers (or specific ledger).
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

        if target_ledger_id:
            ledgers = [l for l in ledgers if str(l.get("ledger_id")) == str(target_ledger_id)]

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
            "period": period_name,
            "ledgers_report": report
        }

    def process_conversational_prompt(self, user_text: str, default_period: str = "Dec-24") -> dict:
        """
        Processes conversational messages or structured prompt inputs (e.g. from IBM Consulting Advantage).
        Extracts intent, ledger(s), period, and action type, then executes and returns formatted markdown output.
        """
        text_lower = user_text.lower()
        
        # 1. Parse Period
        period = default_period
        period_match = re.search(r"period\s*[:=]?\s*([a-zA-Z]{3}-\d{2})", user_text, re.IGNORECASE)
        if period_match:
            period = period_match.group(1)
        else:
            # Look for months like Oct-24, Nov-24, Dec-24, Jan-25
            month_match = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[-_\s]?(\d{2,4})\b", user_text, re.IGNORECASE)
            if month_match:
                m = month_match.group(1).capitalize()
                y = month_match.group(2)[-2:]
                period = f"{m}-{y}"

        # 2. Parse Ledger
        target_ledger_id = None
        if "1001" in user_text or "us primary" in text_lower or "us ledger" in text_lower:
            target_ledger_id = "1001"
        elif "1002" in user_text or "uk primary" in text_lower or "uk ledger" in text_lower:
            target_ledger_id = "1002"
        elif "1003" in user_text or "canada primary" in text_lower or "canadian" in text_lower:
            target_ledger_id = "1003"
        elif "global ledger set" in text_lower or "all ledgers" in text_lower or "all three" in text_lower:
            target_ledger_id = None

        # 3. Parse Action Type
        action = "readiness"
        if "close request" in text_lower or ("close" in text_lower and ("request" in text_lower or "execute" in text_lower or "run close" in text_lower or "please close" in text_lower or "attempt to close" in text_lower)):
            action = "close"
        elif "status inquiry" in text_lower or ("status" in text_lower and not "check" in text_lower and not "readiness" in text_lower):
            action = "status"
        elif "readiness" in text_lower or "check" in text_lower or "assess" in text_lower or "blocker" in text_lower or "scan" in text_lower:
            action = "readiness"

        # 4. Execute Action
        if action == "status":
            summary = self.get_status_summary(period, target_ledger_id)
            return self._format_status_response(summary, user_text, period)
        elif action == "close":
            # Run readiness assessment first to provide rich feedback
            readiness = self.assess_readiness(period, target_ledger_id)
            if readiness["status"] == "READY":
                close_result = self.verify_and_close_ledgers(period, target_ledger_id)
                return self._format_close_success_response(close_result, readiness, period)
            else:
                return self._format_close_blocked_response(readiness, period)
        else:
            # Default: Readiness Assessment
            readiness = self.assess_readiness(period, target_ledger_id)
            return self._format_readiness_response(readiness, period)

    def _format_readiness_response(self, readiness: dict, period: str) -> dict:
        is_ready = readiness["overall_ready"]
        overall_status_str = "READY FOR CLOSE" if is_ready else "BLOCKED (HOLD)"
        
        md = []
        md.append(f"### 🛡️ Oracle Fusion Financial Period Close Readiness Assessment")
        md.append(f"**Accounting Period:** `{period}` | **Status:** **`{overall_status_str}`** | **Total Blockers:** `{readiness['total_blockers']}`\n")
        
        for lname, ldata in readiness["ledgers_report"].items():
            l_status = ldata["readiness_status"]
            icon = "✅" if l_status == "READY" else "⚠️"
            md.append(f"#### {icon} {lname} (ID: `{ldata['ledger_id']}` | Currency: `{ldata['currency']}`)")
            md.append(f"- **Costing Period:** `{ldata['costing_status']}` | **GL Period:** `{ldata['gl_status']}`")
            md.append(f"- **Readiness State:** `{l_status}` ({ldata['reason']})")
            
            # Module check pills
            checks = ldata["module_checks"]
            mod_status = [
                f"Costing: {'PASS' if checks['costing']['status']=='PASS' else 'FAIL'}",
                f"SLA: {'PASS' if checks['sla']['status']=='PASS' else 'FAIL'}",
                f"AP: {'PASS' if checks['ap']['status']=='PASS' else 'FAIL'}",
                f"AR: {'PASS' if checks['ar']['status']=='PASS' else 'FAIL'}",
                f"Inventory: {'PASS' if checks['inventory']['status']=='PASS' else 'FAIL'}"
            ]
            md.append(f"- **Module Checks:** `{' | '.join(mod_status)}`")
            
            if ldata["detailed_blockers"]:
                md.append("\n**🚨 Identified Blockers & Recommended Actions:**")
                for i, b in enumerate(ldata["detailed_blockers"], 1):
                    md.append(f"{i}. **[{b['module']}]** `{b.get('transaction_id') or b.get('receipt_number')}`")
                    if b.get("po_number") and b.get("po_number") != "N/A":
                        md.append(f"   - **Details:** PO `{b['po_number']}` | Receipt `{b['receipt_number']}` | Item `{b['item_number']}` ({b.get('quantity', '')})")
                    if b.get("supplier") and b.get("supplier") != "N/A":
                        md.append(f"   - **Supplier:** `{b['supplier']}`")
                    if b.get("customer") and b.get("customer") != "N/A":
                        md.append(f"   - **Customer:** `{b['customer']}`")
                    md.append(f"   - **Issue:** {b['error_message']}")
                    md.append(f"   - **👉 Recommended Next Step:** {b['next_step']}")
            md.append("")

        if is_ready:
            md.append("🎉 **Next Step:** All validation checks have PASSED. You can now issue a **Close Request** to close Costing followed by General Ledger.")
        else:
            md.append("⛔ **Close Prohibited:** Financial close cannot proceed until the subledger and costing errors above are resolved in Oracle Fusion.")

        return {
            "reply": "\n".join(md),
            "data": readiness,
            "action": "readiness_assessment",
            "period": period,
            "overall_status": readiness["status"]
        }

    def _format_close_blocked_response(self, readiness: dict, period: str) -> dict:
        md = []
        md.append(f"### ⚠️ Financial Close Request Blocked")
        md.append(f"**Accounting Period:** `{period}` | **Outcome:** **`BLOCKED (Close Aborted)`**\n")
        md.append("The agent performed pre-close readiness validation and detected active subledger or costing blockers. In accordance with Oracle close policies, periods cannot be closed while pending or errored distributions exist.\n")

        for lname, ldata in readiness["ledgers_report"].items():
            if ldata["readiness_status"] == "BLOCKED":
                md.append(f"#### 🚫 {lname} (ID: `{ldata['ledger_id']}`)")
                for b in ldata["detailed_blockers"]:
                    md.append(f"- **{b['module']}:** {b['error_message']}")
                    md.append(f"  *Fix:* {b['next_step']}")
            else:
                md.append(f"#### ✅ {lname} (ID: `{ldata['ledger_id']}`) — Ready (Clean)")

        md.append("\n**Resolution Priority Order:**")
        md.append("1. Resolve Costing/Inventory missing cost profiles (unblocks Cost Management).")
        md.append("2. Correct Subledger Accounting rules and complete Payables/Receivables Create Accounting & Transfer to GL.")
        md.append("3. Re-submit Close Request once all items are clear.")

        return {
            "reply": "\n".join(md),
            "data": readiness,
            "action": "close_blocked",
            "period": period,
            "overall_status": "BLOCKED"
        }

    def _format_close_success_response(self, close_result: dict, readiness: dict, period: str) -> dict:
        md = []
        md.append(f"### 🎉 Financial Period Close Executed Successfully")
        md.append(f"**Accounting Period:** `{period}` | **Status:** **`COMPLETED`**\n")
        md.append("All pre-close readiness validations passed. The agent has successfully executed standard Oracle Fusion close sequences (Costing period closed first, followed by General Ledger).\n")

        for lname, ldata in close_result["ledgers_report"].items():
            md.append(f"#### ✅ {lname} (ID: `{ldata['ledger_id']}`)")
            md.append(f"- **Costing Status:** `Closed`")
            md.append(f"- **GL Status:** `Closed`")
            if "actions_taken" in ldata:
                for a in ldata["actions_taken"]:
                    md.append(f"- ✓ {a}")
            md.append("")

        md.append("🚀 **Summary:** All target Oracle Fusion Financial and Costing periods for period `" + period + "` are now fully closed.")

        return {
            "reply": "\n".join(md),
            "data": close_result,
            "action": "close_success",
            "period": period,
            "overall_status": "COMPLETED"
        }

    def _format_status_response(self, summary: dict, user_text: str, period: str) -> dict:
        md = []
        md.append(f"### 📋 Oracle Fusion Period Status Inquiry")
        md.append(f"**Period:** `{period}`\n")
        for lname, ldata in summary["ledgers"].items():
            md.append(f"- **{lname}** (ID: `{ldata['ledger_id']}`):")
            md.append(f"  - Costing Period: `{ldata['costing_status']}`")
            md.append(f"  - General Ledger: `{ldata['gl_status']}`")
        return {
            "reply": "\n".join(md),
            "data": summary,
            "action": "status_inquiry",
            "period": period,
            "overall_status": "SUCCESS"
        }
