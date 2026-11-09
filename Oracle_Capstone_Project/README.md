# Oracle Fusion Financial Period Close Agent
### Autonomous ERP Financials & SCM Costing Period Close Orchestrator
**IBM Consulting Advantage | Oracle Capstone Project | Version 1.0**

---

## 📖 Executive Overview

The **Oracle Financial Period Close Agent** is an intelligent orchestration and diagnostic solution built for **IBM Consulting Advantage**. It automates, governs, and accelerates the end-to-end financial period close lifecycle across **Oracle Fusion Cloud Financials** (General Ledger, Payables, Receivables) and **Supply Chain Management** (Cost Management, Inventory Management).

### 🎯 Key Business Capabilities
- **Non-Invasive Readiness Diagnostics**: Scans all active ledgers across 5 subledger domains before any period is closed.
- **Deep Blocker Resolution**: Isolates transaction-level blockers (Purchase Orders, Receipt numbers, Item IDs, Suppliers, and SLA error codes) with exact root-cause explanations and step-by-step remediation playbooks.
- **Enforced 6-Step Closing Hierarchy**: Guarantees that upstream inventory transfers and SCM Costing periods are fully closed before the General Ledger (GL) period is closed.
- **Autonomous Close Execution**: Directly triggers standard Oracle Fusion REST API period-close transactions once all subledger constraints pass.
- **Dual Operating Modes**:
  - **Simulation Mode (Mock)**: A local ERP simulator with realistic multi-ledger datasets (missing item costs, SLA rule failures, unaccounted invoices).
  - **Live API Mode (Real)**: Direct HTTPS REST integration with your Oracle Fusion Cloud ERP instance (`/fscmRestApp/resources/11.13.18.05/...`).
- **Zero External Dependencies**: Powered entirely by the Python 3 standard library (`http.server`, `urllib`, `json`, `unittest`) for enterprise stability and security compliance.

---

## 🚀 How to Run the Application

### Prerequisites
- **Python 3.8+** installed on your system.
- No third-party packages or `pip install` commands required.

---

### Option 1: Launch the Modern Web User Interface (Recommended)

The Web UI features an interactive **IBM Consulting Advantage AI Chat**, **Period Close Cockpit / Dashboard**, **Blocker Resolution Hub**, **8-Case Test Pack Matrix Runner**, and **Oracle Fusion REST API Configuration**.

```bash
# Method A: Direct server launch
python server.py

# Method B: Launch via app.py flag
python app.py --ui
```

Once started, open your web browser and navigate to:
👉 **`http://127.0.0.1:8000/`**

---

### Option 2: Run the Interactive Command-Line Console

To use the interactive CLI terminal:

```bash
python app.py
```

This presents the interactive menu:
```text
============================================================
          ORACLE FUSION FINANCIAL PERIOD CLOSE AGENT          
============================================================
1. [MOCK] Run Close Agent - Scenario 1: Multi-Ledger Errors (US+UK)
2. [MOCK] Run Close Agent - Scenario 2: Single PO Receipt Costing Error Only
3. [MOCK] Run Close Agent - Scenario 3: UK Subledger Account Violation Only
4. [MOCK] Run Close Agent - Scenario 4: All Clear (Full Success)
5. [REAL] Connect to live Oracle Fusion ERP and Run Close Agent
6. [TEST] Run Automated Test Suite (PO Receipt & 8-Case Pack)
7. Configure Oracle Fusion API Credentials
8. [WEB UI] Launch Web Interface (IBM Consulting Advantage Cockpit)
9. Exit
============================================================
```

---

## 🖥️ Web User Interface Features

The Web UI is structured into 5 operational modules:

### 1. 💬 Agent Chat (IBM Consulting Advantage)
- **Conversational AI Interaction**: Enter natural language instructions or paste structured prompt templates.
- **1-Click Prompt Drawer**: Pre-loaded with all 9 scenario templates from [`agent_prompt_inputs.txt`](agent_prompt_inputs.txt).
- **Rich Diagnostic Output**: Real-time status badges (`READY`, `HOLD`, `COMPLETED`), formatted blocker callouts, and step-by-step resolution steps.

### 2. 📊 Period Close Cockpit / Dashboard
- **Executive KPIs**: Ledgers Monitored, Close Readiness (`READY` vs `HOLD`), Active Blockers count, and 5-Module Subledger Coverage.
- **Visual Ledger Cards**: Real-time status for **US Primary Ledger (`1001`)**, **UK Primary Ledger (`1002`)**, and **Canada Primary Ledger (`1003`)** showing GL and Costing period states.
- **Subledger Readiness Matrix**: Color-coded matrix across Costing, SLA Accounting, Payables (AP), Receivables (AR), and Inventory.
- **Action Toolbar**: Instant buttons to **Run Readiness Assessment** and **Execute Financial Period Close**.

### 3. 🔍 Subledger Blocker & Resolution Hub
- **Search & Filter**: Search by PO number, Receipt number, Item ID, Supplier, Customer, or Error message.
- **Module Filter**: Filter specifically for Cost Management, SLA, AP, AR, or Inventory blockers.
- **"Inspect & Resolve" Modal**: Deep-dive into technical root causes and exact Oracle Fusion navigation paths.

### 4. 🧪 8-Case Test Pack & Test Suite Runner
- **8-Case Synthetic Test Matrix**: Real-time visual pass/fail indicators verifying the 75% positive flag ratio (6 positive, 2 negative controls).
- **Python Unittest Suite Runner**: Runs automated test suites directly in the browser with live console streaming.

### 5. ⚙️ Oracle Fusion Connection Settings
- **Execution Mode Toggle**: Switch between **Mock Simulation Mode** and **Live Oracle Fusion REST API Mode**.
- **REST API Credentials**: Configure Host URL, Username, and API Token with real-time connection health checks.

---

## 🤖 IBM Consulting Advantage Prompt Protocol

The agent supports three core action types:

| Action Type | Operational Behavior | Scope |
|-------------|----------------------|-------|
| **READINESS CHECK** | Deep multi-module scan for blocking transactions. Read-only. No period statuses are changed. | All modules (Costing, SLA, AP, AR, Inventory) |
| **CLOSE REQUEST** | Runs the readiness check, and if all ledgers pass cleanly, autonomously executes period close (Costing &rarr; GL). | Target ledger(s) and period |
| **STATUS INQUIRY** | Reports current Open/Closed status of GL and Costing periods without scanning blockers. | Target ledger(s) and period |

### Example Structured Prompt (from `agent_prompt_inputs.txt`):
```text
Environment : Oracle Fusion Cloud Financials
Ledger      : US Primary Ledger (Ledger ID: 1001)
Period      : Dec-24
Action      : Readiness Check

There is a known issue with a PO receipt in Cost Management. Please run
the readiness assessment and report any blockers before attempting to close.
```

---

## 🏛️ Global Ledger Topology

| Ledger ID | Ledger Name | Currency | Chart of Accounts | Cost Organization / Book |
|-----------|-------------|----------|-------------------|--------------------------|
| **1001** | US Primary Ledger | USD | `US_CORP_COA` | `MFG-PLANT-01` / `US_COST_BOOK` |
| **1002** | UK Primary Ledger | GBP | `UK_CORP_COA` | `UK-PLANT-LON` / `UK_COST_BOOK` |
| **1003** | Canada Primary Ledger | CAD | `CA_CORP_COA` | `CA-PLANT-TOR` / `CA_COST_BOOK` |

---

## ⛓️ Mandatory 6-Step Period Close Hierarchy

Oracle Fusion rejects any period close attempted out of order. The agent strictly enforces:

```text
[STEP 1] Upstream Inventory Transfers
         └── Verify all inventory receipts are transferred to Cost Management (TransferStatus = 'TRANSFERRED')
[STEP 2] Cost Management Distribution & Costing
         └── Ensure all PO receipts and inventory movements are costed (CostingStatus = 'COSTED')
[STEP 3] Subledger Accounting (SLA) Journal Generation
         └── Create Accounting generates balanced journals (AccountingStatus = 'ACCOUNTED')
[STEP 4] Costing Period Close Execution
         └── Close SCM Costing period in Oracle Fusion (ApplicationId: 10078)
[STEP 5] Subledger Journal Transfer to General Ledger
         └── Push Costing, AP, and AR journals into GL open interface (TransferStatus = 'TRANSFERRED')
[STEP 6] General Ledger Period Close Execution
         └── Close ERP General Ledger period after verifying Costing is 'Closed' (ApplicationId: 101)
```

---

## 📁 Repository File Structure

| File | Description |
|------|-------------|
| **`server.py`** | Web server and REST API backend (`http.server`) binding to `127.0.0.1:8000`. |
| **`app.py`** | Interactive CLI console and entry point for launching both CLI and Web UI (`--ui`). |
| **`close_agent.py`** | Core `FinancialCloseAgent` orchestration engine and conversational prompt parser. |
| **`oracle_fusion_client.py`** | Abstract client interface with `MockOracleFusionClient` and `RealOracleFusionClient`. |
| **`mock_financial_period_close_data.txt`** | Comprehensive technical brief, 5-day close SOP runbook, and mock datasets. |
| **`agent_prompt_inputs.txt`** | Ready-to-use prompt templates for 9 standard test scenarios. |
| **`test_agent_walkthrough.txt`** | Step-by-step manual test guide mapping to all CLI and Web scenarios. |
| **`test_period_close_8_case_pack.py`** | Automated unit tests covering the 8-case synthetic period close test pack. |
| **`test_purchase_order_receipt.py`** | Unit tests for single purchase-order receipt costing hold and resolution. |
| **`web/index.html`** | Single-page Web UI application template. |
| **`web/static/style.css`** | IBM Carbon & Oracle Cloud styling design system. |
| **`web/static/app.js`** | Frontend application logic, chat rendering, and API communication. |

---

## 🧪 Running Automated Unit Tests

To run the full automated test suite:

```bash
# Discover and run all tests
python -m unittest discover -v
```

### Running Specific Test Packs:

```bash
# Run the 8-Case Period Close Test Pack (AP, AR, Inventory)
python -m unittest test_period_close_8_case_pack.py

# Run the Single Purchase Order Receipt Costing Test
python -m unittest test_purchase_order_receipt.py
```

### Expected Test Results:
- **`test_period_close_8_case_pack.py`**: 6 positive cases flagged (Cases 1-6) and 2 negative controls verified clean (Cases 7-8). Total 75% positive flag ratio.
- **`test_purchase_order_receipt.py`**: Confirms PO receipt costing error blocks the close, and error resolution permits successful full close.

---

## 🔒 Security, Compliance & Governance

- **Localhost Binding**: In accordance with IBM security standards, all server processes bind exclusively to `127.0.0.1` (never `0.0.0.0`).
- **Encrypted Transport**: Real Oracle Fusion Cloud connections enforce TLS 1.2+ HTTPS with strict certificate validation.
- **Zero Hardcoded Secrets**: Credentials are stored in `config.json` (git-ignored) and never exposed in logs or API responses.
- **Read-Only Gate**: Readiness assessments are strictly non-mutating. Period close requests require explicit confirmation before issuing state-changing REST calls.
