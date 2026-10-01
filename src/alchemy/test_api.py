import os
import requests
import pandas as pd
from dotenv import load_dotenv


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

INPUT_FILE = "data/input/eth_addresses.csv"

ALCHEMY_API_URL = (
    "https://eth-mainnet.g.alchemy.com/v2/"
)


# ============================================================
# ALchemy request
# ============================================================

def alchemy_request(api_key, params):

    url = ALCHEMY_API_URL + api_key

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "alchemy_getAssetTransfers",
        "params": [params],
    }

    try:

        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=60,
        )

    except requests.exceptions.RequestException as e:

        print()
        print("NETWORK ERROR:")
        print(e)

        return None

    print()
    print(f"HTTP status: {response.status_code}")

    if response.status_code != 200:

        print()
        print("Alchemy request failed:")
        print(response.text[:2000])

        return None

    try:

        result = response.json()

    except ValueError:

        print()
        print("Could not parse Alchemy response.")

        return None

    if "error" in result:

        print()
        print("ALCHEMY API ERROR:")
        print(result["error"])

        return None

    return result.get("result", {})


# ============================================================
# GET TRANSFERS
# ============================================================

def get_transfers(api_key, address, direction):

    params = {
        "fromBlock": "0x0",
        "toBlock": "latest",

        "category": [
            "external",
            "internal",
            "erc20",
            "erc721",
            "erc1155",
        ],

        "excludeZeroValue": False,

        "withMetadata": True,

        "maxCount": "0x64",
    }

    if direction == "outgoing":

        params["fromAddress"] = address

    elif direction == "incoming":

        params["toAddress"] = address

    else:

        raise ValueError(
            "direction must be outgoing or incoming"
        )

    print()
    print(
        f"Querying {direction} transfers..."
    )

    result = alchemy_request(
        api_key,
        params
    )

    if result is None:
        return None

    transfers = result.get(
        "transfers",
        []
    )

    page_key = result.get(
        "pageKey"
    )

    print(
        f"Transfers returned: "
        f"{len(transfers)}"
    )

    if page_key:

        print(
            "Additional pages are available."
        )

        print(
            "For this first test, "
            "we will not paginate further."
        )

    return transfers


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("ALCHEMY API TEST")
    print("=" * 70)
    print()

    api_key = os.getenv(
        "ALCHEMY_API_KEY"
    )

    if not api_key:

        print(
            "ERROR: ALCHEMY_API_KEY is not set."
        )

        return

    print(
        "Alchemy API key detected."
    )

    # --------------------------------------------------------
    # Load dataset
    # --------------------------------------------------------

    df = pd.read_csv(
        INPUT_FILE
    )

    print()
    print(
        f"Total seed rows: {len(df)}"
    )

    # --------------------------------------------------------
    # First address only
    # --------------------------------------------------------

    address = (
        str(df.iloc[0]["Address"])
        .strip()
        .lower()
    )

    print()
    print(
        f"Test address: {address}"
    )

    # --------------------------------------------------------
    # OUTGOING
    # --------------------------------------------------------

    outgoing = get_transfers(
        api_key,
        address,
        "outgoing"
    )

    # --------------------------------------------------------
    # INCOMING
    # --------------------------------------------------------

    incoming = get_transfers(
        api_key,
        address,
        "incoming"
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    outgoing_count = (
        len(outgoing)
        if outgoing is not None
        else 0
    )

    incoming_count = (
        len(incoming)
        if incoming is not None
        else 0
    )

    print()
    print("=" * 70)
    print("TRANSFER SUMMARY")
    print("=" * 70)

    print()
    print(
        f"Outgoing transfers: "
        f"{outgoing_count}"
    )

    print(
        f"Incoming transfers: "
        f"{incoming_count}"
    )

    # --------------------------------------------------------
    # Display sample transfers
    # --------------------------------------------------------

    all_transfers = []

    if outgoing:
        all_transfers.extend(outgoing)

    if incoming:
        all_transfers.extend(incoming)

    if not all_transfers:

        print()
        print(
            "No transfers returned."
        )

        return

    print()
    print("-" * 70)
    print("SAMPLE TRANSFERS")
    print("-" * 70)

    for transfer in all_transfers[:10]:

        print()

        print(
            f"Block:    "
            f"{transfer.get('blockNum', '')}"
        )

        print(
            f"Hash:     "
            f"{transfer.get('hash', '')}"
        )

        print(
            f"From:     "
            f"{transfer.get('from', '')}"
        )

        print(
            f"To:       "
            f"{transfer.get('to', '')}"
        )

        print(
            f"Value:    "
            f"{transfer.get('value', '')}"
        )

        print(
            f"Asset:    "
            f"{transfer.get('asset', '')}"
        )

        print(
            f"Category: "
            f"{transfer.get('category', '')}"
        )

        metadata = transfer.get(
            "metadata",
            {}
        )

        if metadata:

            print(
                f"Block time: "
                f"{metadata.get('blockTimestamp', '')}"
            )

    print()
    print("=" * 70)
    print("ALCHEMY TEST COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()