import urllib.request
import json
import os
import logging

logger = logging.getLogger("ICA_Client")

ENDPOINT = "https://api.servicesessentials.ibm.com/v1/assistants/chat/completions"

def get_ica_credentials():
    """Loads credentials from config.json or system environment variables."""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
                return {
                    "api_key": cfg.get("ica_developer_api_key"),
                    "assistant_id": cfg.get("ica_assistant_id", "da47853a-dca5-402d-bdb9-923a0284aa24")
                }
        except Exception as e:
            logger.warning(f"Could not read credentials from config.json: {e}")
            
    # Fallback to system environment variables for production security
    return {
        "api_key": os.environ.get("ICA_DEVELOPER_API_KEY"),
        "assistant_id": os.environ.get("ICA_ASSISTANT_ID", "da47853a-dca5-402d-bdb9-923a0284aa24")
    }

def get_assistant_reply(user_message: str) -> str:
    """
    Sends the user message to the IBM Consulting Advantage Assistant API
    and returns the assistant's text response.
    """
    creds = get_ica_credentials()
    if not creds["api_key"]:
        logger.error("ICA_DEVELOPER_API_KEY is missing!")
        return None

    # Construct the exact request body requested by ICA API
    payload = {
        "model": creds["assistant_id"],
        "messages": [
            {
                "role": "user",
                "content": user_message
            }
        ]
    }
    
    headers = {
        "Authorization": f"Bearer {creds['api_key']}",
        "Content-Type": "application/json"
    }
    
    try:
        req = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            res_body = json.loads(response.read().decode("utf-8"))
            
            # Extract the response text from the completion
            # (Matches standard Chat Completion payload structure: choices[0].message.content)
            choices = res_body.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
                
    except Exception as e:
        logger.error(f"Error calling IBM Consulting Advantage API: {e}")
        return None
