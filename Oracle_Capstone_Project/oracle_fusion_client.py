import copy
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod

logger = logging.getLogger("OracleFusionClient")

REST_ROOT = "/fscmRestApp/resources/11.13.18.05"


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
    Oracle Fusion Cloud client connecting to the ERP REST APIs.
    Uses standard library urllib for security and dependency-free stability.

    Oracle returns collections as {"items": [...], "count", "hasMore", "limit", "offset"}
    with Oracle-style PascalCase attributes. This class pages through those collections
    and normalises each item to the snake_case shape consumed by the close agent.
    """
    PAGE_SIZE = 100

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

    # ------------------------------------------------------------------ #
    # HTTP layer                                                          #
    # ------------------------------------------------------------------ #
    def _build_url(self, endpoint: str) -> str:
        """Percent-encode the query string (q= filters contain spaces and quotes)."""
        path, sep, query = endpoint.partition("?")
        if sep:
            query = urllib.parse.quote(query, safe="=&'()!")
            return f"{self.base_url}/{path}?{query}"
        return f"{self.base_url}/{path}"

    def _make_request(self, endpoint: str, method: str = "GET", data: dict = None) -> dict:
        url = self._build_url(endpoint)
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

    def _get_items(self, endpoint: str) -> list:
        """GET a collection resource, following Oracle's limit/offset/hasMore paging."""
        items = []
        offset = 0
        while True:
            sep = "&" if "?" in endpoint else "?"
            page = self._make_request(f"{endpoint}{sep}limit={self.PAGE_SIZE}&offset={offset}")
            batch = page.get("items", [])
            items.extend(batch)
            if not page.get("hasMore") or not batch:
                return items
            offset += len(batch)

    # ------------------------------------------------------------------ #
    # Oracle item -> agent record normalisation                           #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _norm_ledger(i: dict) -> dict:
        return {
            "ledger_id": str(i.get("LedgerId")),
            "name": i.get("Name"),
            "currency": i.get("CurrencyCode"),
            "chart_of_accounts": i.get("ChartOfAccountsName"),
        }

    @staticmethod
    def _norm_costing(i: dict) -> dict:
        return {
            "transaction_id": i.get("CostTransactionNumber"),
            "po_number": i.get("PurchaseOrderNumber"),
            "receipt_number": i.get("ReceiptNumber"),
            "item_number": i.get("ItemNumber"),
            "quantity": i.get("Quantity"),
            "unit_of_measure": i.get("UnitOfMeasure"),
            "costing_status": i.get("CostingStatus"),
            "accounting_status": i.get("AccountingStatus"),
            "error_message": i.get("ErrorMessage"),
        }

    @staticmethod
    def _subledger_next_step(accounting_status: str, transfer_status: str, noun: str):
        if accounting_status != "ACCOUNTED":
            return f"Run Create Accounting for this {noun} (accounting not yet created)."
        if transfer_status != "TRANSFERRED":
            return f"Run Transfer Journal Entries to GL for this {noun}."
        return None

    @classmethod
    def _norm_ap(cls, i: dict) -> dict:
        acct, xfer = i.get("AccountingStatus"), i.get("TransferToGLStatus")
        return {
            "record_id": i.get("InvoiceNumber"),
            "module": "Payables",
            "period": i.get("PeriodName"),
            "supplier": i.get("Supplier"),
            "description": i.get("Description"),
            "accounting_status": acct,
            "transfer_status": xfer,
            "next_step": cls._subledger_next_step(acct, xfer, "invoice"),
        }

    @classmethod
    def _norm_ar(cls, i: dict) -> dict:
        acct, xfer = i.get("AccountingStatus"), i.get("TransferToGLStatus")
        return {
            "record_id": i.get("TransactionNumber"),
            "module": "Receivables",
            "period": i.get("PeriodName"),
            "customer": i.get("BillToCustomerName"),
            "description": i.get("Description"),
            "accounting_status": acct,
            "transfer_status": xfer,
            "next_step": cls._subledger_next_step(acct, xfer, "transaction"),
        }

    @staticmethod
    def _norm_inventory(i: dict) -> dict:
        xfer, costing = i.get("TransferToCostMgmtStatus"), i.get("CostingStatus")
        if xfer != "TRANSFERRED":
            next_step = ("Transfer inventory transaction to Cost Management "
                         "(cost processor has not yet picked up this receipt).")
        elif costing == "NOT_COSTED":
            next_step = ("Cost this transaction in Cost Management "
                         "(transferred but cost processor has not completed costing).")
        else:
            next_step = None
        return {
            "record_id": i.get("TransactionNumber"),
            "module": "Inventory / Cost Management",
            "period": i.get("PeriodName"),
            "organization": i.get("OrganizationCode"),
            "item": i.get("ItemNumber"),
            "description": i.get("Description"),
            "transfer_status": xfer,
            "costing_status": costing,
            "next_step": next_step,
        }

    # ------------------------------------------------------------------ #
    # OracleFusionClient interface                                        #
    # ------------------------------------------------------------------ #
    def get_ledgers(self):
        # GET /fscmRestApp/resources/11.13.18.05/ledgers
        endpoint = "fscmRestApp/resources/11.13.18.05/ledgers?onlyData=true"
        return [self._norm_ledger(i) for i in self._get_items(endpoint)]

    def get_period_statuses(self, ledger_id: str, period_name: str):
        # For General Ledger (ApplicationId 101)
        gl_endpoint = f"fscmRestApp/resources/11.13.18.05/ledgerPeriods?q=LedgerId={ledger_id} and PeriodName='{period_name}' and ApplicationId=101&onlyData=true"
        # For Costing (ApplicationId 10078 / Cost Management)
        cost_endpoint = f"fscmRestApp/resources/11.13.18.05/ledgerPeriods?q=LedgerId={ledger_id} and PeriodName='{period_name}' and ApplicationId=10078&onlyData=true"

        gl_status = "Never Opened"
        cost_status = "Never Opened"

        try:
            items = self._get_items(gl_endpoint)
            if items:
                gl_status = items[0].get("ClosingStatus", "Open")
        except Exception as e:
            logger.warning(f"Could not fetch GL period status: {e}")

        try:
            items = self._get_items(cost_endpoint)
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
        endpoint = f"fscmRestApp/resources/11.13.18.05/costTransactions?q=LedgerId={ledger_id} and PeriodName='{period_name}' and (CostingStatus='ERROR' or AccountingStatus='ERROR' or CostingStatus='UNPROCESSED' or AccountingStatus='NOT_ACCOUNTED')&onlyData=true"
        try:
            return [self._norm_costing(i) for i in self._get_items(endpoint)]
        except Exception as e:
            logger.error(f"Failed to query costing transactions: {e}")
            return []

    def close_period(self, ledger_id: str, period_name: str, application: str) -> bool:
        app_id = 101 if application == "GL" else 10078
        endpoint = "fscmRestApp/resources/11.13.18.05/ledgerPeriods"

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
            return [self._norm_ap(i) for i in self._get_items(ap_endpoint)]
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
            return [self._norm_ar(i) for i in self._get_items(ar_endpoint)]
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
            return [self._norm_inventory(i) for i in self._get_items(inv_endpoint)]
        except Exception as e:
            logger.error(f"Failed to query inventory transactions: {e}")
            return []


# ---------------------------------------------------------------------- #
# Mock Oracle Fusion REST server (transport-level)                        #
# ---------------------------------------------------------------------- #
MOCK_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_oracle_data")
MOCK_RESOURCES = (
    "ledgers", "ledgerPeriods", "costTransactions",
    "apInvoices", "arTransactions", "inventoryTransactions",
)

_TOKEN_RE = re.compile(
    r"\s*(?:(?P<lp>\()|(?P<rp>\))|(?P<ne>!=)|(?P<eq>=)"
    r"|'(?P<str>(?:[^']|'')*)'|(?P<num>-?\d+(?:\.\d+)?)|(?P<word>[A-Za-z_][A-Za-z0-9_]*))"
)


class _MockHttpError(Exception):
    def __init__(self, code: int, title: str):
        super().__init__(title)
        self.code = code
        self.title = title


def _tokenize_filter(q: str) -> list:
    tokens, pos = [], 0
    while pos < len(q):
        if not q[pos:].strip():
            break
        m = _TOKEN_RE.match(q, pos)
        if not m:
            raise _MockHttpError(400, f"Invalid q filter near: {q[pos:pos + 20]!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind == "str":
            tokens.append(("lit", m.group("str").replace("''", "'")))
        elif kind == "num":
            text = m.group("num")
            tokens.append(("lit", float(text) if "." in text else int(text)))
        elif kind == "word":
            word = m.group("word")
            if word.lower() in ("and", "or"):
                tokens.append((word.lower(), None))
            else:
                tokens.append(("field", word))
        else:
            tokens.append((kind, None))
    return tokens


def _parse_filter(q: str):
    """Parse an Oracle REST q= filter (=, !=, and, or, parentheses) into a predicate."""
    tokens = _tokenize_filter(q)
    idx = 0

    def peek():
        return tokens[idx][0] if idx < len(tokens) else None

    def take(kind):
        nonlocal idx
        if peek() != kind:
            raise _MockHttpError(400, "Invalid q filter syntax")
        tok = tokens[idx]
        idx += 1
        return tok[1]

    def parse_or():
        left = parse_and()
        while peek() == "or":
            take("or")
            right = parse_and()
            left = (lambda a, b: lambda row: a(row) or b(row))(left, right)
        return left

    def parse_and():
        left = parse_term()
        while peek() == "and":
            take("and")
            right = parse_term()
            left = (lambda a, b: lambda row: a(row) and b(row))(left, right)
        return left

    def parse_term():
        if peek() == "lp":
            take("lp")
            inner = parse_or()
            take("rp")
            return inner
        field = take("field")
        op = "eq" if peek() == "eq" else "ne"
        take(op)
        value = take("lit")

        def predicate(row):
            if field not in row:
                raise _MockHttpError(400, f"Unknown attribute in q filter: {field}")
            equal = row[field] == value
            return equal if op == "eq" else not equal
        return predicate

    if not tokens:
        return lambda row: True
    predicate = parse_or()
    if idx != len(tokens):
        raise _MockHttpError(400, "Invalid q filter syntax")
    return predicate


class MockOracleFusionClient(RealOracleFusionClient):
    """
    Mock Oracle Fusion environment. It reuses RealOracleFusionClient unchanged (URL
    building, q= filters, limit/offset paging, item normalisation) and only replaces
    the HTTP transport with an in-process server that answers from Oracle-shaped JSON
    fixtures in ./mock_oracle_data ({"items": [...], "count", "hasMore", "limit",
    "offset"}). The fixtures contain Oracle attributes (LedgerId, PeriodName,
    ClosingStatus, CostingStatus, TransferToGLStatus, ...), exactly as REST returns them.

    Scenarios (Dec-24 costing data): "default", "all_clear",
    "po_costing_hold_only", "unaccounted_hold_only".
    """
    DEFAULT_LIMIT = 25

    def __init__(self, scenario_name: str = "default"):
        # Intentionally no super().__init__(): no credentials are needed for the mock.
        self.base_url = "https://mock-oracle-fusion.invalid"
        self.headers = {}
        self.scenario_name = scenario_name
        self._load_fixtures()
        self._apply_scenario()

    def _load_fixtures(self):
        self._store = {}
        for name in MOCK_RESOURCES:
            with open(os.path.join(MOCK_DATA_DIR, f"{name}.json"), "r", encoding="utf-8") as f:
                self._store[name] = copy.deepcopy(json.load(f)["items"])

    def _apply_scenario(self):
        cost = {
            i["CostTransactionNumber"]: i
            for i in self._store["costTransactions"] if i["PeriodName"] == "Dec-24"
        }

        def resolve(item):
            item["CostingStatus"] = "COSTED"
            item["AccountingStatus"] = "ACCOUNTED"
            item["ErrorMessage"] = None

        if self.scenario_name == "all_clear":
            for item in cost.values():
                resolve(item)
        elif self.scenario_name == "po_costing_hold_only":
            # Only Ledger 1001 has errors, ledger 1002 is cleared
            resolve(cost["TXN_COST_101"])
        elif self.scenario_name == "unaccounted_hold_only":
            # Only Ledger 1002 has errors, ledger 1001 is cleared
            resolve(cost["TXN_COST_002"])

    # -- transport ---------------------------------------------------------
    def _make_request(self, endpoint: str, method: str = "GET", data: dict = None) -> dict:
        url = self._build_url(endpoint)
        logger.debug(f"[mock] {method} {url}")
        try:
            return self._dispatch(url, method, data)
        except _MockHttpError as e:
            body = json.dumps({"title": e.title, "status": str(e.code)})
            logger.error(f"HTTP Error {e.code}: {body}")
            raise Exception(f"Oracle Fusion API Error {e.code}: {body}")

    def _dispatch(self, url: str, method: str, data: dict) -> dict:
        parsed = urllib.parse.urlsplit(url)
        prefix = REST_ROOT + "/"
        if not parsed.path.startswith(prefix):
            raise _MockHttpError(404, "Resource not found")
        resource = parsed.path[len(prefix):]
        if resource not in self._store:
            raise _MockHttpError(404, f"Resource not found: {resource}")
        params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

        if method == "GET":
            return self._get_collection(resource, params)
        if method == "POST" and resource == "ledgerPeriods":
            return self._post_ledger_period(data or {})
        raise _MockHttpError(405, "Method not allowed")

    def _get_collection(self, resource: str, params: dict) -> dict:
        predicate = _parse_filter(params.get("q", [""])[0])
        try:
            limit = int(params.get("limit", [self.DEFAULT_LIMIT])[0])
            offset = int(params.get("offset", [0])[0])
        except ValueError:
            raise _MockHttpError(400, "limit and offset must be integers")
        if limit < 1 or offset < 0:
            raise _MockHttpError(400, "Invalid limit or offset")

        matches = [row for row in self._store[resource] if predicate(row)]
        page = copy.deepcopy(matches[offset:offset + limit])
        return {
            "items": page,
            "count": len(page),
            "hasMore": offset + limit < len(matches),
            "limit": limit,
            "offset": offset,
        }

    def _post_ledger_period(self, payload: dict) -> dict:
        required = ("LedgerId", "PeriodName", "ApplicationId", "ClosingStatus")
        if any(k not in payload for k in required):
            raise _MockHttpError(400, "Missing required attributes")

        def matching(app_id):
            return next((p for p in self._store["ledgerPeriods"]
                         if p["LedgerId"] == payload["LedgerId"]
                         and p["PeriodName"] == payload["PeriodName"]
                         and p["ApplicationId"] == app_id), None)

        period = matching(payload["ApplicationId"])
        if period is None:
            raise _MockHttpError(404, f"Cannot close unrecognized period '{payload['PeriodName']}' in mock environment.")

        if payload["ApplicationId"] == 10078:
            blockers = [i for i in self._store["costTransactions"]
                        if i["LedgerId"] == payload["LedgerId"]
                        and i["PeriodName"] == payload["PeriodName"]
                        and (i["CostingStatus"] in ("ERROR", "UNPROCESSED")
                             or i["AccountingStatus"] in ("ERROR", "NOT_ACCOUNTED"))]
            if blockers:
                raise _MockHttpError(
                    400, f"Cannot close costing period: {len(blockers)} unprocessed or errored transactions exist.")
        elif payload["ApplicationId"] == 101:
            cost_period = matching(10078)
            if cost_period is None or cost_period["ClosingStatus"] != "Closed":
                raise _MockHttpError(400, "Cannot close GL period: Costing period must be closed first.")

        period["ClosingStatus"] = payload["ClosingStatus"]
        return copy.deepcopy(period)
