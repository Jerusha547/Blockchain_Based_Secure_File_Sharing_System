"""
Blockchain integration using Web3.py.

Supports two modes:
  1. LOCAL  — Ganache running at GANACHE_URL (default: http://127.0.0.1:7545)
              Uses the first unlocked Ganache account; no private key needed.
  2. REMOTE — Any public EVM RPC (Sepolia, Polygon, etc.) via BLOCKCHAIN_RPC_URL.
              Requires DEPLOYER_PRIVATE_KEY env var (the account that pays gas).

Environment variables:
  GANACHE_URL           Local Ganache endpoint (default http://127.0.0.1:7545)
  BLOCKCHAIN_RPC_URL    Public RPC URL (e.g. https://sepolia.infura.io/v3/<KEY>)
                        If set, this takes priority over GANACHE_URL.
  DEPLOYER_PRIVATE_KEY  Private key (with 0x prefix) for remote deployments.
                        Required when BLOCKCHAIN_RPC_URL is set.

CONTRACT_ADDRESS is persisted to contracts/deployed_address.txt after the
first deployment so the same contract is reused across restarts.

HOW TO RUN LOCALLY WITH GANACHE:
  npm install -g ganache
  ganache --port 7545
  # Then start Flask normally — no extra env vars needed.

HOW TO DEPLOY ON RENDER / any cloud:
  Set BLOCKCHAIN_RPC_URL=https://sepolia.infura.io/v3/<YOUR_KEY>
  Set DEPLOYER_PRIVATE_KEY=0x<YOUR_PRIVATE_KEY>
  (Get a free Infura key at https://infura.io — Sepolia testnet is free)
"""

import os
import json
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

# ── Configuration ─────────────────────────────────────────────────────────────
GANACHE_URL          = os.getenv("GANACHE_URL", "http://127.0.0.1:7545")
BLOCKCHAIN_RPC_URL   = os.getenv("BLOCKCHAIN_RPC_URL", "")    # public RPC if set
DEPLOYER_PRIVATE_KEY = os.getenv("DEPLOYER_PRIVATE_KEY", "")  # needed for remote

_BASE         = os.path.dirname(__file__)
ADDRESS_FILE  = os.path.join(_BASE, "..", "contracts", "deployed_address.txt")
ABI_FILE      = os.path.join(_BASE, "..", "contracts", "FileStorage_abi.json")
BYTECODE_FILE = os.path.join(_BASE, "..", "contracts", "FileStorage_bytecode.txt")

# ── Lazy globals ──────────────────────────────────────────────────────────────
_w3       = None
_contract = None
_account  = None   # address string
_use_pkey = False  # True when signing manually (remote mode)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _rpc_url() -> str:
    return BLOCKCHAIN_RPC_URL if BLOCKCHAIN_RPC_URL else GANACHE_URL


def _connect():
    global _w3, _account, _use_pkey

    if _w3 is not None:
        return _w3, _account

    url = _rpc_url()
    _w3 = Web3(Web3.HTTPProvider(url))

    # Required for POA chains: Sepolia, Goerli, BSC, etc.
    _w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    if not _w3.is_connected():
        raise ConnectionError(
            f"Cannot connect to blockchain node at {url}.\n"
            "  Local:  make sure Ganache is running (`ganache --port 7545`)\n"
            "  Remote: check your BLOCKCHAIN_RPC_URL is correct."
        )

    if BLOCKCHAIN_RPC_URL:
        # Remote public RPC — must sign transactions manually with private key
        if not DEPLOYER_PRIVATE_KEY:
            raise EnvironmentError(
                "BLOCKCHAIN_RPC_URL is set but DEPLOYER_PRIVATE_KEY is missing.\n"
                "Add your deployer private key (with 0x prefix) as an env var on Render."
            )
        acct = _w3.eth.account.from_key(DEPLOYER_PRIVATE_KEY)
        _account  = acct.address
        _use_pkey = True
        print(f"Connected to remote RPC: {url}  |  account: {_account}")
    else:
        # Local Ganache — accounts are pre-unlocked, no private key needed
        _account  = _w3.eth.accounts[0]
        _use_pkey = False
        print(f"Connected to local Ganache: {url}  |  account: {_account}")

    return _w3, _account


def _send_transaction(fn):
    """
    Send a write transaction (Ganache unlocked account OR signed remote tx).
    Returns the transaction hash as a hex string.
    """
    w3, account = _connect()

    if not _use_pkey:
        # Ganache: account is unlocked — simple .transact()
        tx_hash = fn.transact({"from": account})
        w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    # Remote path: build → sign → send raw
    nonce = w3.eth.get_transaction_count(account, "pending")
    tx = fn.build_transaction({
        "from":     account,
        "nonce":    nonce,
        "gasPrice": w3.eth.gas_price,
        "gas":      300_000,
    })
    signed  = w3.eth.account.sign_transaction(tx, private_key=DEPLOYER_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)
    return tx_hash.hex()


def _deploy_contract(w3, abi, bytecode):
    """Deploy the FileStorage contract and return (receipt, address)."""
    account = _account
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)

    if not _use_pkey:
        tx_hash = Contract.constructor().transact({"from": account})
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    else:
        nonce = w3.eth.get_transaction_count(account, "pending")
        tx = Contract.constructor().build_transaction({
            "from":     account,
            "nonce":    nonce,
            "gasPrice": w3.eth.gas_price,
            "gas":      3_000_000,
        })
        signed  = w3.eth.account.sign_transaction(tx, private_key=DEPLOYER_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    return receipt.contractAddress


def _load_contract():
    """Load (or deploy) the FileStorage smart contract."""
    global _contract

    if _contract is not None:
        return _contract

    w3, _ = _connect()

    with open(ABI_FILE)      as f: abi      = json.load(f)
    with open(BYTECODE_FILE) as f: bytecode = f.read().strip()

    # Reuse an existing deployment
    if os.path.exists(ADDRESS_FILE):
        with open(ADDRESS_FILE) as f:
            address = f.read().strip()
        if address:
            _contract = w3.eth.contract(address=address, abi=abi)
            print(f"Reusing deployed contract at {address}")
            return _contract

    # Fresh deployment
    print("Deploying FileStorage contract ...")
    address = _deploy_contract(w3, abi, bytecode)

    os.makedirs(os.path.dirname(ADDRESS_FILE), exist_ok=True)
    with open(ADDRESS_FILE, "w") as f:
        f.write(address)

    _contract = w3.eth.contract(address=address, abi=abi)
    print(f"Contract deployed at {address}")
    return _contract


# ── Public API ────────────────────────────────────────────────────────────────

def store_hash(file_hash: str) -> str:
    """Store a SHA-256 file hash on-chain. Returns the transaction hash (hex)."""
    contract = _load_contract()
    return _send_transaction(contract.functions.storeFile(file_hash))


def get_hash(index: int) -> dict:
    """Retrieve a stored hash by index. Returns {hash, timestamp}."""
    contract       = _load_contract()
    _, account     = _connect()
    file_hash, ts  = contract.functions.getFile(account, index).call()
    return {"hash": file_hash, "timestamp": ts}


def verify_hash(file_hash: str, index: int) -> bool:
    """Check whether the given hash matches what is stored on-chain at index."""
    return get_hash(index)["hash"] == file_hash


def is_blockchain_available() -> bool:
    """Return True if the configured blockchain node is reachable."""
    try:
        w3, _ = _connect()
        return w3.is_connected()
    except Exception:
        return False
