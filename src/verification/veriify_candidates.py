import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

CANDIDATE_FILE = "data/output/alchemy_candidates.csv"
OUTPUT_FILE = "data/output/alchemy_verified_candidates.csv"

ETHERSCAN_API_URL = "https://api.etherscan.io/v2/api"
CHAIN_ID = 1

REQUEST_DELAY = 0.25

def is_valid_eth_address(address):
    if not isinstance(address, str):
        return False

    address = address.strip()

    if len(address) != 42:
        return False

    if not address.startswith("0x"):
        return False

    try:

        int(address[2:], 16)
        return True

    except ValueError:
        return False

def get_contract_info(address):

    api_key = os.getenv("ETHERSCAN_API_KEY")

    if not api_key:
        raise RuntimeError(
            "ETHERSCAN_API_KEY is not set."
        )

    params = {
        "chainid": CHAIN_ID,
        "module": "contract",
        "action": "getsourcecode",
        "address": address,
        "apikey": api_key,
    }

    try:
        response = requests.get(
            ETHERSCAN_API_URL,
            params=params,
            timeout=30,
        )
    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}")
        return None

    if response.status_code != 200:
        print(
            f"Etherscan HTTP {response.status_code}"
            f"for {address}"
        )
        return None

    try:

        return response.json()
    except ValueError:
        print(f"invalid JSON response for {address}")
        return None

def verify_address(address):
    result = get_contract_info(address)

    if result is None:
        return {
            "address": address,
            "verification_status": "API_ERROR",
            "contract_name": "",
            "proxy": "",
            "implementation": "",
            "similar_match": "",
            "identity_evidence": "",
        }

    data = result.get('result', [])

    if not isinstance(data, list) or not data:
        return {
            "address": address,
            "verification_status": "NOT_FOUND",
            "contract_name": "",
            "proxy": "",
            "implementation": "",
            "similar_match": "",
            "identity_evidence": "",
        }

    contract = data[0]

    contract_name = str(
        contract.get("ContractName", "")
    ).strip()

    source_code = str(
        contract.get("SourceCode", "")
    ).strip()

    proxy = str(
        contract.get("Proxy", "")
    ).strip()

    implementation = str(
        contract.get("Implementation", "")
    ).strip()

    similar_match = str(
        contract.get("SimilarMatch", "")
    ).strip()

    if source_code:
        verification_status = "VERIFIED_CONTRACT"
        identity_evidence = contract_name
    else:
        verification_status = "UNVERIFIED_OR_NOT_CONTRACT"
        identity_evidence = ""

    return {
        "address": address,
        "verification_status": verification_status,
        "contract_name": contract_name,
        "proxy": proxy,
        "implementation": implementation,
        "similar_match": similar_match,
        "identity_evidence": identity_evidence,
    }

def main():

    print("=" * 70)
    print("VERIFY ALCHEMY CANDIDATES WITH ETHERSCAN")
    print("=" * 70)
    print()

    if not os.getenv("ETHERSCAN_API_KEY"):
        print("ERROR: ETHERSCAN_API_KEY is not set.")
        return

    if not os.path.exists(CANDIDATE_FILE):
        print(
            f"ERROR: Candidate file not found:\n"
            f"{CANDIDATE_FILE}"
        )
        print()
        print(
            "Run discover_candidates.py first."
        )
        return

    df = pd.read_csv(CANDIDATE_FILE)

    if "candidate_address" not in df.columns:
        print(
            "ERROR: candidate_address column not found."
        )
        return

    addresses = []

    for value in df["candidate_address"]:

        address = str(value).strip().lower()

        if is_valid_eth_address(address):
            addresses.append(address)

    addresses = list(dict.fromkeys(addresses))

    print(
        f"Candidate addresses to verify: "
        f"{len(addresses)}"
    )

    print()

    results = []

    for position, address in enumerate(
        addresses,
        start=1
    ):

        print(
            f"{position}/{len(addresses)}"
            f"{address}"
        )

        result = verify_address(address)

        results.append(result)

        print(
            f"  ->{result['verification_status']}"
        )

        if result["contract_name"]:
            print(
                f"  -> Contract: "
                f"{result['contract_name']}"
            )

        time.sleep(REQUEST_DELAY)

    result_df = pd.DataFrame(results)

    os.makedirs(
        "data/output",
        exist_ok=True
    )

    result_df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print()
    print("=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    print()

    print(
        result_df[
            "verification_status"
        ].value_counts()
    )

    print()
    print(
        f"Saved to:\n{OUTPUT_FILE}"
    )

if __name__ == "__main__":
    main()

