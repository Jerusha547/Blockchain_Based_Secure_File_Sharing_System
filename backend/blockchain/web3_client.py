"""
Blockchain integration using Web3.py.

Connects to a local Ganache instance (or any EVM-compatible chain).
Deploys the FileStorage contract if not already deployed, then exposes
store_hash() and get_hash() for use by the Flask APIs.

HOW TO SET UP GANACHE (free):
  npm install -g ganache
  ganache --port 7545

CONTRACT_ADDRESS is persisted to contracts/deployed_address.txt after
the first deployment so the same contract is reused across restarts.
"""

import os
import json
from web3 import Web3

# ── Configuration ────────────────────────────────────────────────────────────
GANACHE_URL      = os.getenv("GANACHE_URL", "http://127.0.0.1:7545")
ADDRESS_FILE     = os.path.join(os.path.dirname(__file__),
                                "..", "contracts", "deployed_address.txt")
ABI_FILE         = os.path.join(os.path.dirname(__file__),
                                "..", "contracts", "FileStorage_abi.json")
BYTECODE_FILE    = os.path.join(os.path.dirname(__file__),
                                "..", "contracts", "FileStorage_bytecode.txt")

# ── Lazy global state ─────────────────────────────────────────────────────────
_w3       = None
_contract = None
_account  = None


def _connect():
    global _w3, _account
    if _w3 is None:
        _w3 = Web3(Web3.HTTPProvider(GANACHE_URL))
        if not _w3.is_connected():
            raise ConnectionError(
                f"Cannot connect to Ganache at {GANACHE_URL}. "
                "Make sure Ganache is running: `ganache --port 7545`"
            )
        _account = _w3.eth.accounts[0]
    return _w3, _account


def _load_contract():
    global _contract
    if _contract is not None:
        return _contract

    w3, account = _connect()

    with open(ABI_FILE)      as f: abi      = json.load(f)
    with open(BYTECODE_FILE) as f: bytecode = f.read().strip()

    # Reuse existing deployment if available
    if os.path.exists(ADDRESS_FILE):
        with open(ADDRESS_FILE) as f:
            address = f.read().strip()
        _contract = w3.eth.contract(address=address, abi=abi)
        return _contract

    # Fresh deploy
    Contract   = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx_hash    = Contract.constructor().transact({"from": account})
    receipt    = w3.eth.wait_for_transaction_receipt(tx_hash)
    address    = receipt.contractAddress

    os.makedirs(os.path.dirname(ADDRESS_FILE), exist_ok=True)
    with open(ADDRESS_FILE, "w") as f:
        f.write(address)

    _contract  = w3.eth.contract(address=address, abi=abi)
    print(f"✅ Contract deployed at {address}")
    return _contract


# ── Public API ────────────────────────────────────────────────────────────────

def store_hash(file_hash: str) -> str:
    """
    Store a SHA-256 file hash on-chain for the default account.
    Returns the transaction hash.
    """
    contract = _load_contract()
    w3, account = _connect()
    tx_hash = contract.functions.storeFile(file_hash).transact({"from": account})
    w3.eth.wait_for_transaction_receipt(tx_hash)
    return tx_hash.hex()


def get_hash(index: int) -> dict:
    """
    Retrieve a stored hash by index from the blockchain.
    Returns {"hash": ..., "timestamp": ...}
    """
    contract = _load_contract()
    _, account = _connect()
    file_hash, timestamp = contract.functions.getFile(account, index).call()
    return {"hash": file_hash, "timestamp": timestamp}


def verify_hash(file_hash: str, index: int) -> bool:
    """
    Check whether the given hash matches what is stored on-chain at index.
    """
    stored = get_hash(index)
    return stored["hash"] == file_hash


def is_blockchain_available() -> bool:
    """Return True if Ganache is reachable (used for health-check)."""
    try:
        w3, _ = _connect()
        return w3.is_connected()
    except Exception:
        return False
