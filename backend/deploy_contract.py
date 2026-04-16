"""
deploy_contract.py
──────────────────
Compiles FileStorage.sol using solcx and deploys it to Ganache.
Run this ONCE before starting the Flask server (if Ganache is fresh).

Usage:
    python deploy_contract.py

Requirements:
    pip install py-solc-x web3
"""

import json, os, sys
from web3 import Web3
from solcx import compile_standard, install_solc

GANACHE_URL   = os.getenv("GANACHE_URL", "http://127.0.0.1:7545")
CONTRACT_FILE = os.path.join(os.path.dirname(__file__),
                             "..", "contracts", "FileStorage.sol")
ABI_OUT       = os.path.join(os.path.dirname(__file__),
                             "contracts", "FileStorage_abi.json")
BYTECODE_OUT  = os.path.join(os.path.dirname(__file__),
                             "contracts", "FileStorage_bytecode.txt")
ADDRESS_OUT   = os.path.join(os.path.dirname(__file__),
                             "contracts", "deployed_address.txt")

def main():
    print("📦 Installing solc 0.8.20 …")
    install_solc("0.8.20")

    with open(CONTRACT_FILE) as f:
        source = f.read()

    print("🔨 Compiling FileStorage.sol …")
    compiled = compile_standard({
        "language": "Solidity",
        "sources":  {"FileStorage.sol": {"content": source}},
        "settings": {
            "outputSelection": {
                "*": {"*": ["abi", "evm.bytecode"]}
            }
        }
    }, solc_version="0.8.20")

    abi      = compiled["contracts"]["FileStorage.sol"]["FileStorage"]["abi"]
    bytecode = compiled["contracts"]["FileStorage.sol"]["FileStorage"]["evm"]["bytecode"]["object"]

    os.makedirs(os.path.dirname(ABI_OUT), exist_ok=True)
    with open(ABI_OUT,      "w") as f: json.dump(abi, f, indent=2)
    with open(BYTECODE_OUT, "w") as f: f.write(bytecode)
    print(f"✅ ABI  saved → {ABI_OUT}")
    print(f"✅ Bytecode saved → {BYTECODE_OUT}")

    print(f"\n🌐 Connecting to Ganache at {GANACHE_URL} …")
    w3 = Web3(Web3.HTTPProvider(GANACHE_URL))
    if not w3.is_connected():
        print("❌ Cannot connect to Ganache. Start it with: ganache --port 7545")
        sys.exit(1)

    account  = w3.eth.accounts[0]
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx_hash  = Contract.constructor().transact({"from": account})
    receipt  = w3.eth.wait_for_transaction_receipt(tx_hash)
    address  = receipt.contractAddress

    with open(ADDRESS_OUT, "w") as f: f.write(address)
    print(f"✅ Contract deployed at: {address}")
    print(f"✅ Address saved → {ADDRESS_OUT}")

if __name__ == "__main__":
    main()
