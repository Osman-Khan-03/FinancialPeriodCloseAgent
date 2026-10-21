import json
import logging
from abc import ABC, abstractmethod
import urllib.request
import urllib.error

logger = logging.getLogger("OracleFusionClient")

class OracleFusionClient(ABC):
    """
    Abstract interface for communicating with Oracle Fusion Cloud.
    Supports fetching ledgers, period statuses, costing transactions, and closing periods.
    Also exposes AP/AR subledger accounting status and inventory transfer status queries.
    """
    @abstractmethod
    def get_ledgers(self):
        """Fetch list of active ledgers."""
        pass

    @abstractmethod
    def get_period_statuses(self, ledger_id: str, period_name: str):
        """Fetch GL and Costing period status for a ledger and period."""
        pass

    @abstractmethod
    def get_costing_transactions(self, ledger_id: str, period_name: str):
        """Fetch costing/receiving transactions for a ledger and period."""
        pass

    @abstractmethod
    def close_period(self, ledger_id: str, period_name: str, application: str) -> bool:
        """Attempt to close a period for a specific application (GL or COST)."""
        pass

    @abstractmethod
    def get_ap_transactions(self, ledger_id: str, period_name: str):
        """
        Return AP invoices that are unaccounted or accounted-but-not-transferred to GL.
        Each record must include at minimum:
          record_id, module, period, accounting_status, transfer_status, next_step
        """
        pass

    @abstractmethod
    def get_ar_transactions(self, ledger_id: str, period_name: str):
        """
        Return AR invoices that are unaccounted or accounted-but-not-transferred to GL.
        Same shape as AP records.
        """
        pass

    @abstractmethod
    def get_inventory_transactions(self, ledger_id: str, period_name: str):
        """
        Return inventory transactions that are not yet transferred to Cost Management,
        or transferred but not yet costed (where the configuration exposes that state).
        Each record must include:
          record_id, module, period, transfer_status, costing_status, next_step
        """
        pass


class RealOracleFusionClient(OracleFusionClient):
    """
    Real Oracle Fusion Cloud client connecting to the ERP REST APIs.
    Uses standard library urllib for security and dependency-free stability.
    """
    def __init__(self, base_url: str, username: str, password_token: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password_token = password_token
        # Create standard basic authorization header
        import base64
        auth_str = f"{username}:{password_token}"
        encoded_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        self.headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def _make_request(self, endpoint: str, method: str = "GET", data: dict = None) -> dict:
        url = f"{self.base_url}/{endpoint}"
        logger.debug(f"Making {method} request to {url}")
        
        req_data = None
        if data:
            req_data = json.dumps(data).encode("utf-8")
            
        req = urllib.request.Request(url, data=req_data, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            logger.error(f"HTTP Error {e.code}: {error_body}")
            raise Exception(f"Oracle Fusion API Error {e.code}: {error_body}")
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            raise Exception(f"Connection to Oracle Fusion failed: {str(e)}")

    def get_ledgers(self):
        # Oracle standard Ledger REST endpoint
        # GET /fscmRestApp/resources/11.13.18.05/ledgers
        endpoint = "fscmRestApp/resources/11.13.18.05/ledgers?onlyData=true"
        response = self._make_request(endpoint)
        return response.get("items", [])

    def get_period_statuses(self, ledger_id: str, period_name: str):
        # Standard General Ledger and Subledger period status endpoint
        # For General Ledger (ApplicationId 101)
        gl_endpoint = f"fscmRestApp/resources/11.13.18.05/ledgerPeriods?q=LedgerId={ledger_id} and PeriodName='{period_name}' and ApplicationId=101&onlyData=true"
        # For Costing (ApplicationId 10078 / Cost Management)
        cost_endpoint = f"fscmRestApp/resources/11.13.18.05/ledgerPeriods?q=LedgerId={ledger_id} and PeriodName='{period_name}' and ApplicationId=10078&onlyData=true"
        
        gl_status = "Never Opened"
        cost_status = "Never Opened"
        
        try:
            gl_resp = self._make_request(gl_endpoint)
            items = gl_resp.get("items", [])
            if items:
                gl_status = items[0].get("ClosingStatus", "Open")
        except Exception as e:
            logger.warning(f"Could not fetch GL period status: {e}")
            
        try:
            cost_resp = self._make_request(cost_endpoint)
            items = cost_resp.get("items", [])
            if items:
                cost_status = items[0].get("ClosingStatus", "Open")
        except Exception as e:
            logger.warning(f"Could not fetch Costing period status: {e}")
            
        return {
            "GL": gl_status,
            "COST": cost_status
        }

    def get_costing_transactions(self, ledger_id: str, period_name: str):
        # Queries Costing transactions (subledger) that are unprocessed or have costing/accounting errors
        # REST API endpoint for cost distributions/transactions
        endpoint = f"fscmRestApp/resources/11.13.18.05/costTransactions?q=LedgerId={ledger_id} and PeriodName='{period_name}' and (CostingStatus='ERROR' or AccountingStatus='ERROR' or CostingStatus='UNPROCESSED' or AccountingStatus='NOT_ACCOUNTED')&onlyData=true"
        try:
            response = self._make_request(endpoint)
            return response.get("items", [])
        except Exception as e:
            logger.error(f"Failed to query costing transactions: {e}")
            return []

    def close_period(self, ledger_id: str, period_name: str, application: str) -> bool:
        app_id = 101 if application == "GL" else 10078
        endpoint = f"fscmRestApp/resources/11.13.18.05/ledgerPeriods"

        payload = {
            "LedgerId": int(ledger_id),
            "PeriodName": period_name,
            "ApplicationId": app_id,
            "ClosingStatus": "Closed"
        }
        logger.info(f"Triggering Period Close REST Action for ledger {ledger_id}, period {period_name}, app {application}")
        try:
            self._make_request(endpoint, method="POST", data=payload)
            return True
        except Exception as e:
            logger.error(f"Failed to close period via REST API: {e}")
            raise Exception(f"Failed to close period: {str(e)}")

    def get_ap_transactions(self, ledger_id: str, period_name: str):
        # AP: unaccounted invoices (AccountingStatus != ACCOUNTED)
        # AP: accounted but not transferred to GL (TransferToGLStatus != TRANSFERRED)
        ap_endpoint = (
            f"fscmRestApp/resources/11.13.18.05/apInvoices"
            f"?q=LedgerId={ledger_id} and PeriodName='{period_name}'"
            f" and (AccountingStatus!='ACCOUNTED' or TransferToGLStatus!='TRANSFERRED')"
            f"&onlyData=true"
        )
        try:
            response = self._make_request(ap_endpoint)
            return response.get("items", [])
        except Exception as e:
            logger.error(f"Failed to query AP transactions: {e}")
            return []

    def get_ar_transactions(self, ledger_id: str, period_name: str):
        # AR: same conditions — unaccounted or not transferred to GL
        ar_endpoint = (
            f"fscmRestApp/resources/11.13.18.05/arTransactions"
            f"?q=LedgerId={ledger_id} and PeriodName='{period_name}'"
            f" and (AccountingStatus!='ACCOUNTED' or TransferToGLStatus!='TRANSFERRED')"
            f"&onlyData=true"
        )
        try:
            response = self._make_request(ar_endpoint)
            return response.get("items", [])
        except Exception as e:
            logger.error(f"Failed to query AR transactions: {e}")
            return []

    def get_inventory_transactions(self, ledger_id: str, period_name: str):
        # Inventory: not transferred to Cost Management, or transferred but not yet costed
        inv_endpoint = (
            f"fscmRestApp/resources/11.13.18.05/inventoryTransactions"
            f"?q=LedgerId={ledger_id} and PeriodName='{period_name}'"
            f" and (TransferToCostMgmtStatus!='TRANSFERRED' or CostingStatus='NOT_COSTED')"
            f"&onlyData=true"
        )
        try:
            response = self._make_request(inv_endpoint)
            return response.get("items", [])
        except Exception as e:
            logger.error(f"Failed to query inventory transactions: {e}")
            return []


class MockOracleFusionClient(OracleFusionClient):
    """
    Mock Oracle Fusion client that simulates a real ERP environment.
    Contains complex realistic scenarios, specifically highlighting purchase order receipts in costing.
    Also contains an 8-case test-pack dataset covering AP, AR and Inventory unaccounted /
    not-transferred / not-costed states for period-close validation testing.
    """
    def __init__(self, scenario_name: str = "default"):
        self.scenario_name = scenario_name
        self._init_mock_data()

    def _init_mock_data(self):
        # 1. Ledgers list
        self.ledgers = [
            {"ledger_id": "1001", "name": "US Primary Ledger", "currency": "USD", "chart_of_accounts": "US_COA"},
            {"ledger_id": "1002", "name": "UK Primary Ledger", "currency": "GBP", "chart_of_accounts": "UK_COA"},
            {"ledger_id": "1003", "name": "Canada Primary Ledger", "currency": "CAD", "chart_of_accounts": "CA_COA"}
        ]

        # 2. Period Statuses (GL & COST) for period 'Dec-24'
        self.period_statuses = {
            "1001": {"GL": "Open", "COST": "Open"},
            "1002": {"GL": "Open", "COST": "Open"},
            "1003": {"GL": "Open", "COST": "Open"}
        }

        # 3. Costing / PO Receipt Transactions
        self.transactions = {
            "1001": [
                {
                    "transaction_id": "TXN_COST_001",
                    "po_number": "PO-2024-001",
                    "receipt_number": "RC-99011",
                    "item_number": "AS54888",
                    "quantity": 100,
                    "unit_of_measure": "Ea",
                    "costing_status": "COSTED",
                    "accounting_status": "ACCOUNTED",
                    "error_message": None
                },
                {
                    "transaction_id": "TXN_COST_002",
                    "po_number": "PO-2024-002",
                    "receipt_number": "RC-99012",
                    "item_number": "CN-90812",
                    "quantity": 50,
                    "unit_of_measure": "Box",
                    "costing_status": "ERROR",
                    "accounting_status": "NOT_ACCOUNTED",
                    "error_message": "Item cost definition is missing for item 'CN-90812' in US Cost Book."
                }
            ],
            "1002": [
                {
                    "transaction_id": "TXN_COST_101",
                    "po_number": "PO-2024-003",
                    "receipt_number": "RC-99013",
                    "item_number": "AS54888",
                    "quantity": 10,
                    "unit_of_measure": "Ea",
                    "costing_status": "COSTED",
                    "accounting_status": "ERROR",
                    "error_message": "Subledger Journal Entry violates dynamic account combination rule 'UK_ACC_RULE'."
                }
            ],
            "1003": [
                {
                    "transaction_id": "TXN_COST_201",
                    "po_number": "PO-2024-004",
                    "receipt_number": "RC-99014",
                    "item_number": "CAD-ITEM-01",
                    "quantity": 25,
                    "unit_of_measure": "Kg",
                    "costing_status": "COSTED",
                    "accounting_status": "ACCOUNTED",
                    "error_message": None
                }
            ]
        }

        # ------------------------------------------------------------------ #
        # 4. AP transactions for the 8-case test pack (ledger 1001, Dec-24)   #
        # ------------------------------------------------------------------ #
        # CASE 1 – AP invoice, unaccounted (accounting not yet created)
        # CASE 2 – AP invoice, accounted but not yet transferred to GL
        # CASE 7 – AP invoice, fully processed (negative control – must NOT flag)
        self.ap_transactions = {
            "1001": [
                {
                    "record_id": "TEST-AP-INV-001",
                    "module": "Payables",
                    "period": "Dec-24",
                    "supplier": "TEST-SUPPLIER-OMEGA",
                    "description": "TEST_PACK_2024-12_OWNER:QA Period-Close Case-1",
                    "accounting_status": "NOT_ACCOUNTED",
                    "transfer_status": "NOT_TRANSFERRED",
                    "next_step": "Run Create Accounting for this invoice (accounting not yet created).",
                },
                {
                    "record_id": "TEST-AP-INV-002",
                    "module": "Payables",
                    "period": "Dec-24",
                    "supplier": "TEST-SUPPLIER-OMEGA",
                    "description": "TEST_PACK_2024-12_OWNER:QA Period-Close Case-2",
                    "accounting_status": "ACCOUNTED",
                    "transfer_status": "NOT_TRANSFERRED",
                    "next_step": "Run Transfer Journal Entries to GL for this invoice.",
                },
                {
                    "record_id": "TEST-AP-INV-007",
                    "module": "Payables",
                    "period": "Dec-24",
                    "supplier": "TEST-SUPPLIER-OMEGA",
                    "description": "TEST_PACK_2024-12_OWNER:QA Period-Close Case-7",
                    "accounting_status": "ACCOUNTED",
                    "transfer_status": "TRANSFERRED",
                    "next_step": None,
                },
            ]
        }

        # ------------------------------------------------------------------ #
        # 5. AR transactions for the 8-case test pack (ledger 1001, Dec-24)   #
        # ------------------------------------------------------------------ #
        # CASE 3 – AR invoice, unaccounted
        # CASE 4 – AR invoice, accounted but not transferred to GL
        # CASE 8 – AR invoice, fully processed (negative control – must NOT flag)
        self.ar_transactions = {
            "1001": [
                {
                    "record_id": "TEST-AR-INV-003",
                    "module": "Receivables",
                    "period": "Dec-24",
                    "customer": "TEST-CUSTOMER-ALPHA",
                    "description": "TEST_PACK_2024-12_OWNER:QA Period-Close Case-3",
                    "accounting_status": "NOT_ACCOUNTED",
                    "transfer_status": "NOT_TRANSFERRED",
                    "next_step": "Run Create Accounting for this transaction (accounting not yet created).",
                },
                {
                    "record_id": "TEST-AR-INV-004",
                    "module": "Receivables",
                    "period": "Dec-24",
                    "customer": "TEST-CUSTOMER-ALPHA",
                    "description": "TEST_PACK_2024-12_OWNER:QA Period-Close Case-4",
                    "accounting_status": "ACCOUNTED",
                    "transfer_status": "NOT_TRANSFERRED",
                    "next_step": "Run Transfer Journal Entries to GL for this transaction.",
                },
                {
                    "record_id": "TEST-AR-INV-008",
                    "module": "Receivables",
                    "period": "Dec-24",
                    "customer": "TEST-CUSTOMER-ALPHA",
                    "description": "TEST_PACK_2024-12_OWNER:QA Period-Close Case-8",
                    "accounting_status": "ACCOUNTED",
                    "transfer_status": "TRANSFERRED",
                    "next_step": None,
                },
            ]
        }

        # ------------------------------------------------------------------ #
        # 6. Inventory transactions for the 8-case test pack                  #
        # ------------------------------------------------------------------ #
        # CASE 5 – Receipt approved, NOT yet transferred to Cost Management
        # CASE 6 – Receipt transferred to Cost Management but NOT yet costed
        # (Cases 7 & 8 negative controls are covered in AP/AR tables above)
        self.inventory_transactions = {
            "1001": [
                {
                    "record_id": "TEST-INV-RCT-005",
                    "module": "Inventory / Cost Management",
                    "period": "Dec-24",
                    "organization": "TEST-ORG-M1",
                    "item": "TEST-ITEM-XZ100",
                    "description": "TEST_PACK_2024-12_OWNER:QA Period-Close Case-5",
                    "transfer_status": "NOT_TRANSFERRED",
                    "costing_status": "NOT_COSTED",
                    "next_step": (
                        "Transfer inventory transaction to Cost Management "
                        "(cost processor has not yet picked up this receipt)."
                    ),
                },
                {
                    "record_id": "TEST-INV-RCT-006",
                    "module": "Inventory / Cost Management",
                    "period": "Dec-24",
                    "organization": "TEST-ORG-M1",
                    "item": "TEST-ITEM-XZ100",
                    "description": "TEST_PACK_2024-12_OWNER:QA Period-Close Case-6",
                    "transfer_status": "TRANSFERRED",
                    "costing_status": "NOT_COSTED",
                    "next_step": (
                        "Cost this transaction in Cost Management "
                        "(transferred but cost processor has not completed costing)."
                    ),
                },
            ]
        }

        # Adapt mock database based on the active scenario
        if self.scenario_name == "all_clear":
            # Fix all costing errors
            for ledger_id in self.transactions:
                for txn in self.transactions[ledger_id]:
                    txn["costing_status"] = "COSTED"
                    txn["accounting_status"] = "ACCOUNTED"
                    txn["error_message"] = None
        elif self.scenario_name == "po_costing_hold_only":
            # Only Ledger 1001 has errors, ledger 1002 is cleared
            self.transactions["1002"][0]["accounting_status"] = "ACCOUNTED"
            self.transactions["1002"][0]["error_message"] = None
        elif self.scenario_name == "unaccounted_hold_only":
            # Only Ledger 1002 has errors, ledger 1001 is cleared
            self.transactions["1001"][1]["costing_status"] = "COSTED"
            self.transactions["1001"][1]["accounting_status"] = "ACCOUNTED"
            self.transactions["1001"][1]["error_message"] = None

    def get_ledgers(self):
        return self.ledgers

    def get_period_statuses(self, ledger_id: str, period_name: str):
        if period_name != "Dec-24":
            return {"GL": "Closed", "COST": "Closed"}
        return self.period_statuses.get(ledger_id, {"GL": "Never Opened", "COST": "Never Opened"})

    def get_costing_transactions(self, ledger_id: str, period_name: str):
        if period_name != "Dec-24":
            return []

        txns = self.transactions.get(ledger_id, [])
        blockers = []
        for t in txns:
            if t["costing_status"] in ["ERROR", "UNPROCESSED"] or t["accounting_status"] in ["ERROR", "NOT_ACCOUNTED"]:
                blockers.append(t)
        return blockers

    def close_period(self, ledger_id: str, period_name: str, application: str) -> bool:
        if period_name != "Dec-Dec-24" and period_name != "Dec-24":
            raise Exception("Cannot close periods other than 'Dec-24' in mock environment.")

        blockers = self.get_costing_transactions(ledger_id, period_name)
        if application == "COST" and blockers:
            raise Exception(f"Cannot close costing period: {len(blockers)} unprocessed or errored transactions exist.")

        if application == "GL":
            stat = self.get_period_statuses(ledger_id, period_name)
            if stat.get("COST") != "Closed":
                raise Exception(f"Cannot close GL period: Costing period must be closed first.")

        if ledger_id in self.period_statuses:
            self.period_statuses[ledger_id][application] = "Closed"
            return True
        return False

    def get_ap_transactions(self, ledger_id: str, period_name: str):
        if period_name != "Dec-24":
            return []
        records = self.ap_transactions.get(ledger_id, [])
        flags = []
        for r in records:
            if r["accounting_status"] != "ACCOUNTED" or r["transfer_status"] != "TRANSFERRED":
                flags.append(r)
        return flags

    def get_ar_transactions(self, ledger_id: str, period_name: str):
        if period_name != "Dec-24":
            return []
        records = self.ar_transactions.get(ledger_id, [])
        flags = []
        for r in records:
            if r["accounting_status"] != "ACCOUNTED" or r["transfer_status"] != "TRANSFERRED":
                flags.append(r)
        return flags

    def get_inventory_transactions(self, ledger_id: str, period_name: str):
        if period_name != "Dec-24":
            return []
        records = self.inventory_transactions.get(ledger_id, [])
        flags = []
        for r in records:
            if r["transfer_status"] != "TRANSFERRED" or r["costing_status"] == "NOT_COSTED":
                flags.append(r)
        return flags
