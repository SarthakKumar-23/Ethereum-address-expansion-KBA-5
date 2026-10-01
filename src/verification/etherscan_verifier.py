import os
import requests
import pandas as pd
from dotenv import load_dotenv

# =====================================
# CONFIGURATION
# =====================================

load_dotenv()

INPUT_FILE = "data/input/eth_addresses.csv"

ETHERSCAN_API_URL = "https://api.etherscan.io/v2/api"

CHAIN_ID = 1

# =====================================
# ADDRESS VALIDATION
# =====================================

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

# ============================================
# ETHERSCAN REQUEST
# ============================================

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

        print()
        print("NETWORK ERROR:")
        print(e)

        return None

    print()
    print(
        f"HTTP status: {response.status_code}"
    )

    if response.status_code != 200:

        print()
        print("Etherscan request failed.")
        print(response.text[:2000])

        return None

    try:

        result = response.json()

    except ValueError:

        print()
        print(
            "Could not parse Etherscan response."
        )

        return None

    return result

# ============================================
# INTERNET CONTRACT RESULT
# ============================================

def interpret_contract_info(result):

    if result is None:
        return None

    status = str(
        result.get("status", "")
    )

    message = str(
        result.get("message", "")
    )

    data = result.get(
        "result",
        []
    )

    # Ethereum normally returns a list
    if not isinstance(data, list) or not data:

        return {
            "verification_status": "NOT_FOUND",
            "contract_name": "",
            "proxy": "",
            "implementation": "",
            "similar_match": "",
            "source_available": False,
            "raw_result": data,
            "api_status": status,
            "api_message": message,
        }

    contract = data[0]

    contract_name = str(
        contract.get(
            "ContractName",
            ""
        )
    ).strip()

    source_code = str(
        contract.get(
            "SourceCode",
            ""
        )
    ).strip()

    proxy = str(
        contract.get(
            "proxy",
            ""
        )
    ).strip()

    implementation = str(
        contract.get(
            "Implementation",
            ""
        )
    ).strip()

    similar_match = str(
        contract.get(
            "SimilarMatch",
            ""
        )
    ).strip()

    # SourceCode being populated is our basic
    # contract-verification indicator.

    if source_code:

        verification_status = "VERIFIED"

    else:

        verification_status = "UNVERIFIED_OR_NOT_CONTRACT"

    return {
        "verification_status": verification_status,
        "contract_name": contract_name,
        "proxy": proxy,
        "implementation": implementation,
        "similar_match": similar_match,
        "source_available": bool(source_code),
        "raw_result": contract,
        "api_status": status,
        "api_message": message,
    }

# =============================================
# TEST ONE ADDRESS
# =============================================

def main():

    print("=" * 70)
    print("ETHERSCAN IDENTITY VERIFICATION TEST")
    print("=" * 70)
    print()

    api_key = os.getenv(
        "ETHERSCAN_API_KEY"
    )

    if not api_key:

        print(
            "ERROR: ETHERSCAN_API_KEY is not set."
        )

        return

    print(
        "Etherscan API key detected."
    )

    # --------------------------------------------------------
    # Load seed dataset
    # --------------------------------------------------------

    df = pd.read_csv(
        INPUT_FILE
    )

    print()
    print(
        f"Total seed rows: {len(df)}"
    )

    # First address only
    address = (
        str(df.iloc[0]["Address"])
        .strip()
        .lower()
    )

    print()
    print(
        f"Test address: {address}"
    )

    if not is_valid_eth_address(address):

        print()
        print(
            "ERROR: Invalid Ethereum address."
        )

        return

    # --------------------------------------------------------
    # Query Etherscan
    # --------------------------------------------------------

    print()
    print(
        "Querying Etherscan..."
    )

    result = get_contract_info(
        address
    )

    if result is None:

        print()
        print(
            "Could not retrieve Etherscan data."
        )

        return

    # --------------------------------------------------------
    # Interpret response
    # --------------------------------------------------------

    info = interpret_contract_info(
        result
    )

    if info is None:

        print()
        print(
            "Could not interpret Etherscan response."
        )

        return

    # --------------------------------------------------------
    # Display evidence
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("IDENTITY EVIDENCE")
    print("=" * 70)

    print()
    print(
        f"Address:              {address}"
    )

    print(
        f"Verification status:  "
        f"{info['verification_status']}"
    )

    print(
        f"Contract name:        "
        f"{info['contract_name']}"
    )

    print(
        f"Proxy:                "
        f"{info['proxy']}"
    )

    print(
        f"Implementation:       "
        f"{info['implementation']}"
    )

    print(
        f"Similar Match:        "
        f"{info['similar_match']}"
    )

    print(
        f"Source available:     "
        f"{info['source_available']}"
    )

    print(
        f"API status:           "
        f"{info['api_status']}"
    )

    print(
        f"API message:          "
        f"{info['api_message']}"
    )

    print()
    print("=" * 70)
    print("TEST COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()