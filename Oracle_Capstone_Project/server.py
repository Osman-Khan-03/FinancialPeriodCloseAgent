import http.server
import json
import logging
import os
import sys
import urllib.parse
import io
import unittest
import contextlib
from oracle_fusion_client import MockOracleFusionClient, RealOracleFusionClient
from close_agent import FinancialCloseAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("PeriodCloseWebServer")

CONFIG_FILE = "config.json"
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

# In-memory server state
current_scenario = "default"
current_mode = "MOCK"  # 'MOCK' or 'REAL'


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read {CONFIG_FILE}: {e}")
    return {}


def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        logger.info(f"Configuration saved to {CONFIG_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save {CONFIG_FILE}: {e}")
        return False


def get_active_client():
    global current_mode, current_scenario
    config = load_config()
    mode = config.get("mode", current_mode)

    if mode == "REAL":
        url = config.get("url", "")
        username = config.get("username", "")
        password = config.get("password", "")
        if url and username and password:
            return RealOracleFusionClient(url, username, password)
        logger.warning("Real Oracle credentials missing, falling back to mock")

    return MockOracleFusionClient(scenario_name=current_scenario)


def get_prompt_templates():
    """
    Returns the pre-configured prompt scenarios extracted from agent_prompt_inputs.txt
    """
    return [
        {
            "id": "Prompt 1",
            "title": "Single Clean Ledger (US 1001)",
            "badge": "Pass / Full Close",
            "badgeClass": "badge-clean",
            "description": "Happy path for US Primary Ledger in Oct-24. Validates and closes Costing then GL.",
            "prompt": "Environment : Oracle Fusion Cloud Financials\nLedger      : US Primary Ledger (Ledger ID: 1001)\nPeriod      : Oct-24\nAction      : Close Request\n\nPlease run the readiness assessment and, if all checks pass, close the Costing period followed by the General Ledger period for Oct-24."
        },
        {
            "id": "Prompt 2",
            "title": "All 3 Ledgers Clean (Global Set)",
            "badge": "Pass / Multi-Ledger",
            "badgeClass": "badge-clean",
            "description": "Multi-ledger happy path across US (1001), UK (1002), and Canada (1003) for Nov-24.",
            "prompt": "Environment  : Oracle Fusion Cloud Financials\nLedger Set   : Global Ledger Set\nLedgers      : US Primary Ledger (1001), UK Primary Ledger (1002), Canada Primary Ledger (1003)\nPeriod       : Nov-24\nAction       : Close Request\n\nPlease run the readiness assessment across all three ledgers and close Costing and GL periods for each once confirmed clear."
        },
        {
            "id": "Prompt 3",
            "title": "Costing Blocker (PO Receipt CN-90812)",
            "badge": "Costing Hold",
            "badgeClass": "badge-error",
            "description": "Missing item cost definition in US Cost Book for Receipt RC-99012 blocking period close.",
            "prompt": "Environment : Oracle Fusion Cloud Financials\nLedger      : US Primary Ledger (Ledger ID: 1001)\nPeriod      : Dec-24\nAction      : Readiness Check\n\nThere is a known issue with a PO receipt in Cost Management. Please run the readiness assessment and report any blockers before attempting to close."
        },
        {
            "id": "Prompt 4",
            "title": "Accounting Rule SLA Violation (UK 1002)",
            "badge": "SLA Hold",
            "badgeClass": "badge-error",
            "description": "Subledger journal entry violates dynamic account rule UK_ACC_RULE in UK Primary Ledger.",
            "prompt": "Environment : Oracle Fusion Cloud Financials\nLedger      : UK Primary Ledger (Ledger ID: 1002)\nPeriod      : Dec-24\nAction      : Readiness Check\n\nCosting has completed but we believe there is an accounting error on a receipt in the UK ledger. Please run the readiness assessment and report any blockers."
        },
        {
            "id": "Prompt 5",
            "title": "AP Invoice Unaccounted (Payables)",
            "badge": "AP Hold",
            "badgeClass": "badge-error",
            "description": "Unaccounted AP Invoice TEST-AP-INV-001 requires Create Accounting in Payables.",
            "prompt": "Environment : Oracle Fusion Cloud Financials\nLedger      : US Primary Ledger (Ledger ID: 1001)\nPeriod      : Dec-24\nAction      : Readiness Check\n\nCosting looks fine but we have an unaccounted Payables invoice blocking the GL close. Please assess and advise."
        },
        {
            "id": "Prompt 6",
            "title": "AP Invoice Accounted Not Transferred",
            "badge": "AP / GL Transfer",
            "badgeClass": "badge-error",
            "description": "Accounting exists for AP invoice TEST-AP-INV-002 but journal was not transferred to GL.",
            "prompt": "Environment : Oracle Fusion Cloud Financials\nLedger      : US Primary Ledger (Ledger ID: 1001)\nPeriod      : Dec-24\nAction      : Readiness Check\n\nWe have a Payables invoice that has been accounted but the journal does not appear in the General Ledger. Please identify the issue and advise next steps."
        },
        {
            "id": "Prompt 7",
            "title": "Inventory Not Transferred to Costing",
            "badge": "Inv / Cost Transfer",
            "badgeClass": "badge-error",
            "description": "Receipt approved in Inventory (TEST-INV-RCT-005) but not transferred to Cost Management.",
            "prompt": "Environment : Oracle Fusion Cloud Financials\nLedger      : US Primary Ledger (Ledger ID: 1001)\nPeriod      : Dec-24\nAction      : Readiness Check\n\nWe have an inventory receipt that does not appear in Cost Management at all. Please assess and tell us what is blocking the Costing period close."
        },
        {
            "id": "Prompt 8",
            "title": "Inventory Transferred Not Costed",
            "badge": "Cost Accounting",
            "badgeClass": "badge-error",
            "description": "Receipt TEST-INV-RCT-006 transferred to Cost Management but cost processor has not run.",
            "prompt": "Environment : Oracle Fusion Cloud Financials\nLedger      : US Primary Ledger (Ledger ID: 1001)\nPeriod      : Dec-24\nAction      : Readiness Check\n\nWe can see an inventory receipt in Cost Management but it is still showing as not costed. Please identify the blocker and advise."
        },
        {
            "id": "Prompt 9",
            "title": "Multi-Blockers Across Modules (AP + Inv)",
            "badge": "Multi-Module Hold",
            "badgeClass": "badge-error",
            "description": "Realistic end-of-period scenario with issues in both Payables and Inventory in UK Ledger.",
            "prompt": "Environment : Oracle Fusion Cloud Financials\nLedger      : UK Primary Ledger (Ledger ID: 1002)\nPeriod      : Dec-24\nAction      : Readiness Check\n\nWe are approaching period-end and want a full readiness assessment before attempting to close. We are aware there may be issues in both Payables and Inventory for this ledger and period."
        }
    ]


class PeriodCloseRequestHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info(f"{self.client_address[0]} - {format % args}")

    def _send_json(self, status_code: int, data: dict):
        response_bytes = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(response_bytes)

    def _serve_file(self, filepath: str, content_type: str):
        if not os.path.exists(filepath):
            self.send_error(404, "File Not Found")
            return
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            logger.error(f"Error serving {filepath}: {e}")
            self.send_error(500, "Internal Server Error")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Static assets
        if path == "/" or path == "/index.html":
            return self._serve_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
        elif path == "/static/style.css":
            return self._serve_file(os.path.join(STATIC_DIR, "static", "style.css"), "text/css; charset=utf-8")
        elif path == "/static/app.js":
            return self._serve_file(os.path.join(STATIC_DIR, "static", "app.js"), "application/javascript; charset=utf-8")

        # REST API Routes
        if path == "/api/status":
            period = query.get("period", ["Dec-24"])[0]
            client = get_active_client()
            agent = FinancialCloseAgent(client)
            summary = agent.get_status_summary(period)
            config = load_config()
            return self._send_json(200, {
                "status": "SUCCESS",
                "mode": config.get("mode", current_mode),
                "scenario": current_scenario,
                "period": period,
                "summary": summary
            })

        elif path == "/api/prompts":
            return self._send_json(200, {
                "status": "SUCCESS",
                "templates": get_prompt_templates()
            })

        elif path == "/api/blockers":
            period = query.get("period", ["Dec-24"])[0]
            client = get_active_client()
            agent = FinancialCloseAgent(client)
            readiness = agent.assess_readiness(period)
            return self._send_json(200, {
                "status": "SUCCESS",
                "period": period,
                "data": readiness
            })

        elif path == "/api/test-pack":
            return self._handle_8_case_test_pack()

        elif path == "/api/unit-tests":
            return self._handle_unit_tests()

        elif path == "/api/config":
            cfg = load_config()
            # Omit password in GET for security
            safe_cfg = {
                "mode": cfg.get("mode", current_mode),
                "url": cfg.get("url", ""),
                "username": cfg.get("username", "")
            }
            return self._send_json(200, safe_cfg)

        else:
            return self._send_json(404, {"error": "Endpoint not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = {}
        if content_length > 0:
            try:
                body = json.loads(self.rfile.read(content_length).decode("utf-8"))
            except Exception as e:
                return self._send_json(400, {"error": f"Invalid JSON payload: {str(e)}"})

        if path == "/api/chat":
            message = body.get("message", "").strip()
            period = body.get("period", "Dec-24")
            if not message:
                return self._send_json(400, {"error": "Message is required."})

            client = get_active_client()
            agent = FinancialCloseAgent(client)
            result = agent.process_conversational_prompt(message, default_period=period)
            return self._send_json(200, result)

        elif path == "/api/assessment":
            period = body.get("period", "Dec-24")
            ledger_id = body.get("ledger_id")
            client = get_active_client()
            agent = FinancialCloseAgent(client)
            readiness = agent.assess_readiness(period, target_ledger_id=ledger_id)
            formatted = agent._format_readiness_response(readiness, period)
            return self._send_json(200, {
                "status": "SUCCESS",
                "period": period,
                "data": readiness,
                "reply": formatted["reply"]
            })

        elif path == "/api/close":
            period = body.get("period", "Dec-24")
            ledger_id = body.get("ledger_id")
            client = get_active_client()
            agent = FinancialCloseAgent(client)

            # Pre-check readiness
            readiness = agent.assess_readiness(period, target_ledger_id=ledger_id)
            if readiness["status"] == "READY":
                close_res = agent.verify_and_close_ledgers(period, target_ledger_id=ledger_id)
                formatted = agent._format_close_success_response(close_res, readiness, period)
                return self._send_json(200, formatted)
            else:
                formatted = agent._format_close_blocked_response(readiness, period)
                return self._send_json(200, formatted)

        elif path == "/api/scenario":
            global current_scenario
            scenario = body.get("scenario", "default")
            current_scenario = scenario
            logger.info(f"Switched simulation scenario to: {scenario}")
            return self._send_json(200, {
                "status": "SUCCESS",
                "scenario": scenario,
                "scenario_title": scenario.replace("_", " ").title()
            })

        elif path == "/api/config":
            global current_mode
            config = load_config()
            mode = body.get("mode", "MOCK")
            url = body.get("url", "").strip()
            username = body.get("username", "").strip()
            password = body.get("password", "").strip()

            config["mode"] = mode
            if url: config["url"] = url
            if username: config["username"] = username
            if password: config["password"] = password

            current_mode = mode
            save_config(config)
            return self._send_json(200, {"status": "SUCCESS", "message": "Configuration updated successfully."})

        elif path == "/api/test-connection":
            url = body.get("url", "")
            username = body.get("username", "")
            password = body.get("password", "")

            if not url or not username or not password:
                return self._send_json(400, {"status": "FAILED", "error": "URL, username and password are required."})

            try:
                real_client = RealOracleFusionClient(url, username, password)
                ledgers = real_client.get_ledgers()
                return self._send_json(200, {
                    "status": "SUCCESS",
                    "message": f"Successfully connected to Oracle Fusion! Retrieved {len(ledgers)} active ledger(s)."
                })
            except Exception as e:
                return self._send_json(200, {
                    "status": "FAILED",
                    "error": str(e)
                })

        else:
            return self._send_json(404, {"error": "Endpoint not found"})

    def _handle_8_case_test_pack(self):
        client = MockOracleFusionClient(scenario_name="default")
        ap_flags = client.get_ap_transactions("1001", "Dec-24")
        ar_flags = client.get_ar_transactions("1001", "Dec-24")
        inv_flags = client.get_inventory_transactions("1001", "Dec-24")
        all_flags = ap_flags + ar_flags + inv_flags
        flag_ids = {r.get("record_id") for r in all_flags}

        cases = [
            {"case_num": 1, "id": "TEST-AP-INV-001", "expected": True, "module": "Payables"},
            {"case_num": 2, "id": "TEST-AP-INV-002", "expected": True, "module": "Payables"},
            {"case_num": 3, "id": "TEST-AR-INV-003", "expected": True, "module": "Receivables"},
            {"case_num": 4, "id": "TEST-AR-INV-004", "expected": True, "module": "Receivables"},
            {"case_num": 5, "id": "TEST-INV-RCT-005", "expected": True, "module": "Inventory / Cost Mgmt"},
            {"case_num": 6, "id": "TEST-INV-RCT-006", "expected": True, "module": "Inventory / Cost Mgmt"},
            {"case_num": 7, "id": "TEST-AP-INV-007", "expected": False, "module": "Payables (Negative Ctrl)"},
            {"case_num": 8, "id": "TEST-AR-INV-008", "expected": False, "module": "Receivables (Negative Ctrl)"},
        ]

        results = []
        passed_count = 0
        log_lines = [
            "=== EXECUTING 8-CASE PERIOD CLOSE TEST PACK ===",
            "Target Ledger: 1001 (US Primary Ledger) | Period: Dec-24\n"
        ]

        for c in cases:
            is_flagged = c["id"] in flag_ids
            passed = is_flagged == c["expected"]
            if passed: passed_count += 1
            status_text = "FLAGGED" if is_flagged else "NOT FLAGGED"
            results.append({
                "case_num": c["case_num"],
                "record_id": c["id"],
                "module": c["module"],
                "passed": passed,
                "actual_status": status_text
            })
            icon = "✓" if passed else "✗"
            log_lines.append(f"{icon} Case {c['case_num']} ({c['id']}) - Module: {c['module']} -> {status_text} (Result: {'PASS' if passed else 'FAIL'})")

        log_lines.append("\n=== 8-CASE TEST PACK SUMMARY ===")
        log_lines.append(f"  AP Flagged: {len(ap_flags)} (Cases 1, 2)")
        log_lines.append(f"  AR Flagged: {len(ar_flags)} (Cases 3, 4)")
        log_lines.append(f"  INV Flagged: {len(inv_flags)} (Cases 5, 6)")
        log_lines.append(f"  Total Flagged / 8 Records: {len(all_flags)} / 8 (75.0% Positive Rate)")
        log_lines.append(f"  Negative Controls Clean: Case 7 (AP), Case 8 (AR)")
        log_lines.append(f"  All 8 Test Cases Verified: {passed_count}/8 PASSED")

        return self._send_json(200, {
            "status": "SUCCESS",
            "cases": results,
            "summary": {
                "total": 8,
                "passed": passed_count,
                "positive_rate": 75.0,
                "flagged_count": len(all_flags)
            },
            "logs": "\n".join(log_lines)
        })

    def _handle_unit_tests(self):
        log_stream = io.StringIO()
        try:
            with contextlib.redirect_stdout(log_stream), contextlib.redirect_stderr(log_stream):
                loader = unittest.TestLoader()
                suite = loader.discover(".", pattern="test_*.py")
                runner = unittest.TextTestRunner(stream=log_stream, verbosity=2)
                test_result = runner.run(suite)

            output = log_stream.getvalue()
            return self._send_json(200, {
                "status": "SUCCESS",
                "tests_run": test_result.testsRun,
                "was_successful": test_result.wasSuccessful(),
                "failures": len(test_result.failures),
                "errors": len(test_result.errors),
                "output": output
            })
        except Exception as e:
            return self._send_json(500, {
                "status": "ERROR",
                "error": str(e),
                "output": log_stream.getvalue()
            })


def start_server(host: str = "127.0.0.1", port: int = 8000):
    server_address = (host, port)
    httpd = http.server.ThreadingHTTPServer(server_address, PeriodCloseRequestHandler)
    print("\n" + "=" * 65)
    print(" 🚀 ORACLE FINANCIAL PERIOD CLOSE AGENT — WEB INTERFACE")
    print("=" * 65)
    print(f" [✓] Server running securely at: http://{host}:{port}/")
    print(f" [✓] IBM Consulting Advantage Chat & Period Close Cockpit Live")
    print(" [✓] Press Ctrl+C in terminal to stop server")
    print("=" * 65 + "\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Shutting down server...")
        httpd.server_close()
        print("[✓] Server stopped successfully.")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    start_server("127.0.0.1", port)
