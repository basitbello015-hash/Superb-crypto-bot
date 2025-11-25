import os
import uuid
from typing import List, Dict
from app_state import bc

# Path to the accounts file
ACCOUNTS_FILE_PATH = "accounts/accounts.json"

# Ensure accounts directory exists on startup
os.makedirs(os.path.dirname(ACCOUNTS_FILE_PATH), exist_ok=True)

def get_accounts() -> List[Dict]:
    """Retrieve all saved accounts using BotController to ensure thread safety."""
    return bc.load_accounts()

def add_account(data: dict) -> Dict:
    """
    Add a new account and ensure the directory/file exists.
    """
    # Generate ID if not present
    if "id" not in data:
        data["id"] = str(uuid.uuid4())

    # Ensure defaults
    data.setdefault("monitoring", False)
    data.setdefault("position", "closed")

    # Ensure the file path exists
    if not os.path.exists(ACCOUNTS_FILE_PATH):
        with open(ACCOUNTS_FILE_PATH, "w") as f:
            f.write("[]")  # Empty list to initialize the file

    # Use bc to read, append, and save (it has a lock)
    with bc._file_lock:
        accounts = bc.load_accounts()
        accounts.append(data)
        bc.save_accounts(accounts)

        # VERIFICATION: Read back to ensure it was saved
        saved_accounts = bc.load_accounts()
        ids = [a.get("id") for a in saved_accounts]
        if data["id"] not in ids:
            raise Exception("Failed to persist account data to storage. Check file permissions.")

    return {"status": "added", "account": data}

def delete_account(account_id: str) -> Dict:
    """
    Delete an account by ID and handle file I/O safely.
    """
    with bc._file_lock:
        accounts = bc.load_accounts()
        initial_len = len(accounts)
        accounts = [a for a in accounts if a.get("id") != account_id]

        if len(accounts) < initial_len:
            bc.save_accounts(accounts)
            return {"status": "deleted", "id": account_id}

    return {"status": "not_found", "id": account_id}

def test_account(account_id: str) -> Dict:
    """
    Test connection for a specific account and handle file I/O safely.
    """
    accounts = bc.load_accounts()
    account = next((a for a in accounts if a.get("id") == account_id), None)

    if not account:
        return {"id": account_id, "connection": "failed", "reason": "Account not found"}

    # Use BotController's validation logic
    ok, balance, err = bc.validate_account(account)

    if ok:
        # Update the account with the latest balance/status
        with bc._file_lock:
            all_accounts = bc.load_accounts()
            for i, a in enumerate(all_accounts):
                if a.get("id") == account_id:
                    all_accounts[i]["validated"] = True
                    all_accounts[i]["balance"] = balance
                    all_accounts[i]["last_validation_error"] = None
                    break
            bc.save_accounts(all_accounts)

        return {"id": account_id, "connection": "success", "balance": balance}
    else:
        return {"id": account_id, "connection": "failed", "reason": err}
