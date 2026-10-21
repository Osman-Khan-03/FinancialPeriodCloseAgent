import json
import os
import sys
import logging
from oracle_fusion_client import MockOracleFusionClient, RealOracleFusionClient
from close_agent import FinancialCloseAgent

# Configure structured standard out logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("PeriodCloseCLI")

CONFIG_FILE = "config.json"

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
        print(f"[+] Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Failed to save {CONFIG_FILE}: {e}")

def run_agent_workflow(client, period="Dec-24"):
    agent = FinancialCloseAgent(client)
    print("\n" + "="*60)
    print(f" RUNNING PERIOD CLOSE AGENT FOR PERIOD: {period} ")
    print("="*60)
    
    result = agent.verify_and_close_ledgers(period)
    
    print("\n" + "="*20 + " AGENT SUMMARY REPORT " + "="*20)
    print(f"Overall Status: {result['status']}")
    print("="*62)
    
    for ledger_name, r in result["ledgers_report"].items():
        print(f"\nLedger: {ledger_name}")
        print(f"  ID: {r.get('ledger_id')}")
        print(f"  Costing Period: {r.get('costing_status', 'N/A')}")
        print(f"  GL Period:      {r.get('gl_status', 'N/A')}")
        print(f"  Ledger Close Status: {r.get('status')}")
        print(f"  Message/Reason:      {r.get('reason', '')}")
        
        if "blockers" in r and r["blockers"]:
            print("  Blockers Found:")
            for b in r["blockers"]:
                print(f"    - {b}")
        if "actions_taken" in r and r["actions_taken"]:
            print("  Actions Taken:")
            for a in r["actions_taken"]:
                print(f"    ✓ {a}")
                
    print("\n" + "="*62)
    
    if result["status"] == "COMPLETED":
        print("\n🎉 SUCCESS: All Oracle Fusion Financial and Costing periods have been successfully validated and closed!")
    else:
        print("\n⚠️  HOLD: Financial Close is blocked. Please resolve the subledger and costing issues highlighted above.")

def main_menu():
    config = load_config()
    
    while True:
        print("\n" + "#"*60)
        print("          ORACLE FUSION FINANCIAL PERIOD CLOSE AGENT          ")
        print("#"*60)
        print("1. [MOCK] Run Close Agent - Scenario 1: Multi-Ledger Errors (PO Receipt Costing + Subledger Account Rules)")
        print("2. [MOCK] Run Close Agent - Scenario 2: Single PO Receipt Costing Error Only")
        print("3. [MOCK] Run Close Agent - Scenario 3: UK Subledger Account Violation Only")
        print("4. [MOCK] Run Close Agent - Scenario 4: All Clear (Financial Close Completes Successfully)")
        print("5. [REAL] Connect to live Oracle Fusion ERP and Run Close Agent")
        print("6. [TEST] Run Automated Test Suite (Single PO Receipt Costing Test)")
        print("7. Configure Oracle Fusion API Credentials")
        print("8. Exit")
        print("#"*60)
        
        choice = input("Enter your selection (1-8): ").strip()
        
        if choice == "1":
            print("\n[info] Initiating Close Agent under Multi-Ledger Errors simulation...")
            client = MockOracleFusionClient(scenario_name="default")
            run_agent_workflow(client)
            
        elif choice == "2":
            print("\n[info] Initiating Close Agent under Single PO Receipt Costing Error simulation...")
            client = MockOracleFusionClient(scenario_name="po_costing_hold_only")
            run_agent_workflow(client)
            
        elif choice == "3":
            print("\n[info] Initiating Close Agent under UK Subledger Account Rule violation simulation...")
            client = MockOracleFusionClient(scenario_name="unaccounted_hold_only")
            run_agent_workflow(client)
            
        elif choice == "4":
            print("\n[info] Initiating Close Agent under All-Clear (Fully costed and accounted) simulation...")
            client = MockOracleFusionClient(scenario_name="all_clear")
            run_agent_workflow(client)
            
        elif choice == "5":
            if not config.get("url") or not config.get("username") or not config.get("password"):
                print("\n[!] Error: API Credentials not configured. Please choose Option 7 first.")
                continue
            
            print(f"\n[info] Initializing Live Connection to: {config['url']}")
            client = RealOracleFusionClient(config["url"], config["username"], config["password"])
            period = input("Enter Oracle Period Name (e.g., Dec-24): ").strip()
            if not period:
                period = "Dec-24"
            run_agent_workflow(client, period)
            
        elif choice == "6":
            print("\n[info] Running automated test suite for Costing purchase order receipt tests...")
            import unittest
            suite = unittest.TestLoader().discover('.', pattern="test_*.py")
            unittest.TextTestRunner(verbosity=2).run(suite)
            
        elif choice == "7":
            print("\n" + "-"*40)
            print(" CONFIGURE ORACLE FUSION REST API ")
            print("-"*40)
            url = input(f"Oracle Fusion Host URL [{config.get('url', 'https://example-fusion.oraclecloud.com')}]: ").strip() or config.get("url", "https://example-fusion.oraclecloud.com")
            username = input(f"Username [{config.get('username', 'scm_close_agent')}]: ").strip() or config.get("username", "scm_close_agent")
            password = input("Password / API Token: ").strip() or config.get("password", "")
            
            config = {"url": url, "username": username, "password": password}
            save_config(config)
            
        elif choice == "8":
            print("\nExiting Oracle Fusion Period Close Agent. Goodbye!")
            sys.exit(0)
        else:
            print("\n[!] Invalid selection. Please enter a number from 1 to 8.")

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user. Exiting.")
        sys.exit(0)
