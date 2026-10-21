# Oracle Fusion Financial Period Close Agent

An intelligent agent designed to automate and orchestrate the financial period close process in **Oracle Fusion Cloud (ERP Financials & Supply Chain Management)**.

The agent ensures that all subledgers—specifically **Cost Management (Costing)**—are fully processed, costed, and accounted before closing the general ledger (GL) and costing periods. If any issues are found (such as a pending or errored purchase-order receipt transaction), the close is paused, and the agent reports the precise blockers and their reasons to the user.

---

## 🚀 Key Features

- **Automated Period Close Validation**: Scans all active ledgers to verify GL and Costing period readiness.
- **Costing Subledger Analysis**: Targets the Oracle Fusion Costing area to ensure purchase-order receipts and cost distributions are completed.
- **Deep Blocker Resolution Insights**: Traces costing or subledger accounting (SLA) errors back to specific transactions (e.g., PO numbers, Receipt numbers, missing cost definitions) and provides descriptive error messages.
- **Automated Close Action**: Once all blockers are resolved, the agent automatically executes period-close REST operations across ledgers for SCM Costing and ERP General Ledger applications.
- **Dual Connection Modes**:
  - **Simulation Mode (Mock)**: Ships with realistic mock databases reflecting complex multi-ledger scenarios (e.g., missing item costs on PO receipts, SLA accounting violations) to demonstrate agent intelligence out-of-the-box.
  - **Live API Mode (Real)**: Integrates directly with your Oracle Fusion Cloud environment using secure standard ERP REST APIs.

---

## 🛠️ Architecture

1. **`oracle_fusion_client.py`**:
   - Defines a standard `OracleFusionClient` interface.
   - `RealOracleFusionClient`: Handles real-time HTTP requests to standard Oracle Fusion Cloud REST endpoints (e.g., `/fscmRestApp/resources/11.13.18.05/...`) using standard libraries.
   - `MockOracleFusionClient`: A comprehensive local simulator that models complex ledger configurations, costing transactions, and error scenarios.

2. **`close_agent.py`**:
   - Contains the core agent execution engine (`FinancialCloseAgent`).
   - Sequentially checks each ledger's statuses.
   - Pulls subledger blockers and extracts transaction metadata (PO, Receipt, Item, Quantity, Error message).
   - Reports on blocker hold conditions and triggers close processes if all constraints are met.

3. **`test_purchase_order_receipt.py`**:
   - Contains automated tests simulating a **single purchase-order receipt costing test** in the Oracle Fusion Costing area.
   - Validates that the agent correctly identifies a PO costing error block and successfully permits closing once the error is cleared.

4. **`app.py`**:
   - Interactive command-line console providing a user-friendly interface to test the agent across different scenarios.

---

## 📋 Requirements Fulfilled (from `requirement.txt`)

- **Oracle Fusion SCM Costing Testing**: Implemented via a targeted test suite and client mock database that tracks receiving transactions through to Cost Management.
- **Single Purchase-Order Receipt Test**: Implemented in `test_purchase_order_receipt.py` (simulating missing item costs on PO Receipt `RC-99012` under PO `PO-2024-002`).
- **Ledger Status Tracking**: Period check validation executes across multiple ledgers.
- **Blocker and Reason Notification**: The agent flags blocked ledgers and displays the exact PO, Receipt, Item details, and Oracle Fusion error messages.
- **Financial Close Completion**: Automatically executes GL/Cost close when all transactions are processed successfully.

---

## 💻 How to Run the Agent

### Prerequisites
- Python 3.x

### Run the Interactive Console
Execute the interactive console from the workspace root directory:
```bash
python app.py
```

This presents a menu where you can:
1. Run a mock simulation with multiple errors.
2. Run a mock simulation focusing on a single PO receipt costing error.
3. Run a mock simulation with an SLA unaccounted error.
4. Run an "All-Clear" simulation to see the agent successfully close the periods.
5. Connect to a live Oracle Fusion Cloud instance (requires URL, username, and password).
6. Run automated unit tests.
7. Configure credentials.

---

## 🧪 Running the Automated Tests

To execute the specific **Purchase Order Receipt Costing** test suite:

```bash
python -m unittest test_purchase_order_receipt.py
```

This runs:
- `test_single_purchase_order_receipt_costing_failure`: Verifies that a PO receipt costing error blocks the close and displays the correct reason.
- `test_single_purchase_order_receipt_costing_resolved`: Verifies that resolving the costing error allows the Close Agent to successfully close both Costing and GL periods.
