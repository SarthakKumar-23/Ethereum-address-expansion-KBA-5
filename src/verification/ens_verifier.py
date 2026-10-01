import os
import time
import pandas as pd
from web3 import Web3
from dotenv import load_dotenv

# ===========================================
# CONFIGURATION
# ===========================================

load_dotenv()

CANDIDATE_FILE = "data/output/alchemy_candidates.csv"
OUTPUT_FILE = "data/output/alchemy_ens_verified.csv"

# We are testing the candidates generated from 10 seeds.
# Keep this small initially.

MAX_CANDIDATES = None

REQUEST_DELAY = 0.1

# =========================================
# VALIDATE ETH ADDRESS
# =========================================

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

# ==========================================
# MAIN
# ==========================================

def main():

    print("=" * 70)
    print("ENS IDENTITY VERIFICATION")
    print("=" * 70)
    print()

    # -----------------------------------------
    # RPC configuration
    # -----------------------------------------

    rpc_url = os.getenv("ALCHEMY_API_KEY")

    if not rpc_url:

        print(
            "ERROR: ALCHEMY_API_KEY is not set."
        )

        return

    # Alchemy key is already available, so use it
    # for Ethereum Mainnet RPC.
    rpc_url = (
        "https://eth-mainnet.g.alchemy.com/v2/" + rpc_url
    )

    print("Connecting to Ethereum Mainnet...")

    w3 = Web3(
        Web3.HTTPProvider(
            rpc_url,
            request_kwargs={
                "timeout": 30
            }
        )
    )

    if not w3.is_connected():

        print()
        print(
            "ERROR: Could not connect to Ethereum."
        )

        return

    print(
        "Ethereum Mainnet connection successful."
    )

    # -------------------------------------------
    # Load candidates
    # -------------------------------------------

    if not os.path.exists(CANDIDATE_FILE):

        print()
        print(
            f"ERROR: Candidate file not found:\n"
            f"{CANDIDATE_FILE}"
        )

        return

    df = pd.read_csv(
        CANDIDATE_FILE
    )

    if "candidate_address" not in df.columns:

        print(
            "ERROR: candidate_address column "
            "not found."
        )

        return

    addresses = []

    for value in df["candidate_address"]:

        address = str(value).strip()

        if is_valid_eth_address(address):

            addresses.append(
                Web3.to_checksum_address(address)
            )

    # Remove duplicates

    addresses = list(
        dict.fromkeys(addresses)
    )

    if MAX_CANDIDATES is not None:

        addresses = addresses[
            :MAX_CANDIDATES
        ]

    print()
    print(
        f"Candidates to test: "
        f"{len(addresses)}"
    )

    print()

    # ----------------------------------
    # ENS resolver
    # ----------------------------------

    results = []

    for position, address in enumerate(
        addresses,
        start=1
    ):

        print(
            f"{position}/{len(addresses)}"
            f"{address}"
        )

        try:

            # web3.py resolves the ENS primary name.
            ens_name = w3.ens.name(
                address
            )

        except Exception as e:

            print(
                f"ENS lookup error: {e}"
            )

            results.append({
                "address": address,
                "ens_name": "",
                "forward_resolved_address": "",
                "ens_verified": False,
                "verification_source": "ENS",
                "error": str(e),
            })

            continue

        # ------------------------------------------
        # No ENS name
        # ------------------------------------------

        if not ens_name:

            print(
                "No ENS primary name."
            )

            results.append({
                "address": address,
                "ens_name": "",
                "forward_resolved_address": "",
                "ens_verified": False,
                "verification_source": "ENS",
                "error": "",
            })

            continue

        print(
            f"ENS name: {ens_name}"
        )

        # ----------------------------------------
        # Forward resolution
        # ----------------------------------------

        try:

            resolved_address = (
                w3.ens.address(
                    ens_name
                )
            )

        except Exception as e:

            print(
                f"forward lookup error: {e}"
            )

            results.append({
                "address": address,
                "ens_name": ens_name,
                "forward_resolved_address": "",
                "ens_verified": False,
                "verification_source": "ENS",
                "error": str(e),
            })

            continue

        if resolved_address:

            resolved_address = (
                Web3.to_checksum_address(
                    resolved_address
                )
            )

        # --------------------------------------
        # Verify both directions
        # --------------------------------------

        verified = (
            resolved_address is not None
            and resolved_address.lower()
            == address.lower()
        )

        print(
            f"Forward address: "
            f"{resolved_address}"
        )

        print(
            f"ENS verified: "
            f"{verified}"
        )

        results.append({
            "address": address,
            "ens_name": ens_name,
            "forward_resolved_address": resolved_address or "",
            "ens_verified": verified,
            "verification_source": "ENS",
            "error": "",
        })

        time.sleep(
            REQUEST_DELAY
        )

    # -------------------------------------------
    # Save results
    # -------------------------------------------

    result_df = pd.DataFrame(
        results
    )

    os.makedirs(
        "data/output",
        exist_ok=True
    )

    result_df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    # -----------------------------------------
    # SUMMARY
    # -----------------------------------------
    
    total = len(result_df)

    names_found = (
        result_df["ens_name"]
        .astype(str)
        .str.strip()
        .ne("")
        .sum()
    )

    verified = (
        result_df["ens_verified"] == True
    ).sum()

    print()
    print("=" * 70)
    print("ENS VERIFICATION SUMMARY")
    print("=" * 70)

    print(
        f"Candidates tested: {total}"
    )

    print(
        f"ENS names found: {names_found}"
    )

    print(
        f"ENS relationships verified: {verified}"
    )

    print()
    print(
        f"Saved to:\n{OUTPUT_FILE}"
    )

    print()
    print("=" * 70)

if __name__ == "__main__":
    main()