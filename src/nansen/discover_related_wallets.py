import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

INPUT_FILE = "./data/input/eth_addresses.csv"

OUTPUT_FILE = "./data/output/nansen_related_wallets.csv"

CANDIDATE_FILE = "./data/output/nansen_new_candidates.csv"

CHECKPOINT_FILE = "./data/checkpoint/nansen_checkpoint.csv"

NANSEN_API_URL = (
    "https://api.nansen.ai/api/v1/"
    "profiler/address/related-wallets"
)

CHAIN = "ethereum"

# Number of related wallets requested per API page.
PER_PAGE = 100

# None = process every address.
# Example: 10 = test first 10 addresses.
MAX_ADDRESSES = 10

# Save progress every N seed addresses.
CHECKPOINT_EVERY = 1

# Small delay between requests.
REQUEST_DELAY = 0.2

# Retry temporary failures.
MAX_RETRIES = 3


# ============================================================
# ADDRESS VALIDATION
# ============================================================

def is_valid_eth_address(address):
    """
    Check whether a string looks like a valid Ethereum address.

    Ethereum addresses are:
        0x + 40 hexadecimal characters
    """

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


# ============================================================
# NANSEN API REQUEST
# ============================================================

def nansen_request(address, page):
    """
    Request one page of related wallets for an address.
    """

    api_key = os.getenv("NANSEN_API_KEY")

    if not api_key:
        raise RuntimeError(
            "NANSEN_API_KEY is not set."
        )

    headers = {
        "apiKey": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "address": address,
        "chain": CHAIN,
        "pagination": {
            "page": page,
            "per_page": PER_PAGE,
        },
    }

    for attempt in range(
        1,
        MAX_RETRIES + 1
    ):

        try:

            response = requests.post(
                NANSEN_API_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )

            # ------------------------------------------------
            # Success
            # ------------------------------------------------

            if response.status_code == 200:

                return response.json()

            # ------------------------------------------------
            # Rate limit
            # ------------------------------------------------

            if response.status_code == 429:

                wait_time = attempt * 5

                print(
                    f"Rate limited for {address}. "
                    f"Waiting {wait_time}s..."
                )

                time.sleep(wait_time)

                continue

            if response.status_code == 403:
                print("Nansen returned HTTP 403.")
                print(response.text)

                if "insufficient_credits" in response.text:
                    print("STOPPING: Nansen account has insufficient credits.")
                    return "INSUFFICIENT_CREDITS"

            # ------------------------------------------------
            # Payment / credit issue
            # ------------------------------------------------

            if response.status_code == 402:

                print(
                    "Nansen returned HTTP 402 "
                    "(payment/credit limit)."
                )

                print(
                    response.text
                )

                return None

            # ------------------------------------------------
            # Authentication
            # ------------------------------------------------

            if response.status_code == 401:

                print(
                    "Nansen returned HTTP 401."
                )

                print(
                    "Check your NANSEN_API_KEY."
                )

                return None

            # ------------------------------------------------
            # Other HTTP errors
            # ------------------------------------------------

            print(
                f"Nansen HTTP {response.status_code} "
                f"for {address}"
            )

            print(
                response.text[:500]
            )

            if attempt < MAX_RETRIES:

                wait_time = attempt * 2

                time.sleep(wait_time)

                continue

            return None

        except requests.exceptions.RequestException as e:

            print(
                f"Network error for {address}: {e}"
            )

            if attempt < MAX_RETRIES:

                wait_time = attempt * 2

                time.sleep(wait_time)

            else:

                return None

    return None


# ============================================================
# GET ALL RELATED WALLETS
# ============================================================

def get_related_wallets(address):
    """
    Retrieve all related wallets for one seed address.

    Nansen uses pagination, so we continue until
    is_last_page is True.
    """

    all_rows = []

    page = 1

    while True:

        data = nansen_request(
            address,
            page
        )

        if data == "INSUFFICIENT_CREDITS":
            return "INSUFFICIENT_CREDITS"

        # ----------------------------------------------------
        # API failed
        # ----------------------------------------------------

        if data is None:

            return None

        # ----------------------------------------------------
        # Extract data
        # ----------------------------------------------------

        rows = data.get(
            "data",
            []
        )

        pagination = data.get(
            "pagination",
            {}
        )

        # ----------------------------------------------------
        # Add rows
        # ----------------------------------------------------

        if isinstance(rows, list):

            all_rows.extend(rows)

        # ----------------------------------------------------
        # Check whether this is the last page
        # ----------------------------------------------------

        is_last_page = pagination.get(
            "is_last_page",
            True
        )

        if is_last_page:

            break

        page += 1

        # Small delay between pagination calls.
        time.sleep(
            REQUEST_DELAY
        )

    return all_rows


# ============================================================
# LOAD SEED ADDRESSES
# ============================================================

def load_seed_addresses():
    """
    Load the known 20K addresses from the input dataset.
    """

    df = pd.read_csv(
        INPUT_FILE
    )

    print(
        f"Input rows: {len(df)}"
    )

    addresses = []

    for value in df["Address"]:

        address = str(
            value
        ).strip()

        if is_valid_eth_address(
            address
        ):

            addresses.append(
                address.lower()
            )

    # Remove duplicates.
    addresses = list(
        dict.fromkeys(
            addresses
        )
    )

    print(
        f"Valid unique seed addresses: "
        f"{len(addresses)}"
    )

    return addresses


# ============================================================
# SAVE RESULTS
# ============================================================

def save_results(rows):
    """
    Save raw Nansen relationship results.
    """

    if not rows:
        return

    os.makedirs(
        "./data/output",
        exist_ok=True
    )

    df = pd.DataFrame(
        rows
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )


def save_checkpoint(processed_addresses):
    """
    Save addresses that have already been processed.
    """

    os.makedirs(
        "./data/checkpoint",
        exist_ok=True
    )

    checkpoint_df = pd.DataFrame(
        {
            "address": list(
                processed_addresses
            )
        }
    )

    checkpoint_df.to_csv(
        CHECKPOINT_FILE,
        index=False
    )


# ============================================================
# LOAD CHECKPOINT
# ============================================================

def load_checkpoint():
    """
    Load previously processed addresses.
    """

    if not os.path.exists(
        CHECKPOINT_FILE
    ):

        return set()

    try:

        df = pd.read_csv(
            CHECKPOINT_FILE
        )

        if "address" not in df.columns:

            return set()

        addresses = set(
            df["address"]
            .astype(str)
            .str.lower()
            .str.strip()
        )

        print(
            f"Checkpoint found: "
            f"{len(addresses)} addresses already processed."
        )

        return addresses

    except Exception as e:

        print(
            f"Could not load checkpoint: {e}"
        )

        return set()


# ============================================================
# LOAD PREVIOUS RESULTS
# ============================================================

def load_previous_results():
    """
    Load previously saved relationship results.
    """

    if not os.path.exists(
        OUTPUT_FILE
    ):

        return []

    try:

        df = pd.read_csv(
            OUTPUT_FILE
        )

        return df.to_dict(
            "records"
        )

    except Exception as e:

        print(
            f"Could not load previous results: {e}"
        )

        return []


# ============================================================
# CREATE UNIQUE CANDIDATE FILE
# ============================================================

def create_candidate_file(
    relationship_rows,
    seed_addresses
):
    """
    Create a deduplicated list of addresses discovered
    by Nansen that were not already in the seed dataset.
    """

    if not relationship_rows:

        return

    seed_set = set(
        address.lower()
        for address in seed_addresses
    )

    candidates = {}

    for row in relationship_rows:

        related_address = str(
            row.get(
                "related_address",
                ""
            )
        ).lower().strip()

        if not is_valid_eth_address(
            related_address
        ):
            continue

        # Already known?
        if related_address in seed_set:
            continue

        if related_address not in candidates:

            candidates[
                related_address
            ] = {
                "candidate_address":
                    related_address,

                "discovered_from":
                    row.get(
                        "seed_address",
                        ""
                    ),

                "address_label":
                    row.get(
                        "address_label",
                        ""
                    ),

                "relation":
                    row.get(
                        "relation",
                        ""
                    ),

                "transaction_hash":
                    row.get(
                        "transaction_hash",
                        ""
                    ),

                "block_timestamp":
                    row.get(
                        "block_timestamp",
                        ""
                    ),

                "chain":
                    row.get(
                        "chain",
                        ""
                    ),
            }

    candidate_df = pd.DataFrame(
        candidates.values()
    )

    os.makedirs(
        "./data/output",
        exist_ok=True
    )

    candidate_df.to_csv(
        CANDIDATE_FILE,
        index=False
    )

    print()
    print(
        f"New unique candidates: "
        f"{len(candidate_df)}"
    )

    print(
        f"Saved candidates to: "
        f"{CANDIDATE_FILE}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=" * 70
    )

    print(
        "NANSEN RELATED WALLET DISCOVERY"
    )

    print(
        "=" * 70
    )

    print()

    # --------------------------------------------------------
    # Check API key
    # --------------------------------------------------------

    if not os.getenv(
        "NANSEN_API_KEY"
    ):

        print(
            "ERROR: NANSEN_API_KEY "
            "is not set."
        )

        return

    print(
        "Nansen API key detected."
    )

    print()

    # --------------------------------------------------------
    # Load seed addresses
    # --------------------------------------------------------

    seed_addresses = load_seed_addresses()

    if MAX_ADDRESSES is not None:

        seed_addresses = seed_addresses[
            :MAX_ADDRESSES
        ]

        print(
            f"Limited to first "
            f"{MAX_ADDRESSES} addresses."
        )

    else:

        print(
            "Processing all seed addresses."
        )

    print()

    # --------------------------------------------------------
    # Load previous progress
    # --------------------------------------------------------

    processed_addresses = load_checkpoint()

    results = load_previous_results()

    print(
        f"Existing relationship rows: "
        f"{len(results)}"
    )

    print()

    # --------------------------------------------------------
    # Process every seed address
    # --------------------------------------------------------

    total = len(
        seed_addresses
    )

    for position, address in enumerate(
        seed_addresses,
        start=1
    ):

        # ----------------------------------------------------
        # Skip already processed addresses
        # ----------------------------------------------------

        if address in processed_addresses:

            continue

        print(
            "=" * 70
        )

        print(
            f"Progress: {position}/{total}"
        )

        print(
            f"Seed address: {address}"
        )

        # ----------------------------------------------------
        # Query Nansen
        # ----------------------------------------------------

        related_wallets = get_related_wallets(
            address
        )

        if related_wallets == "INSUFFICIENT_CREDITS":
            print()
            print("Nansen credits are exhausted.")
            print("Stopping the entire run.")
            break

        # ----------------------------------------------------
        # API failure
        # ----------------------------------------------------

        if related_wallets is None:

            print(
                "ERROR: Could not retrieve data."
            )

            # Do NOT mark this address as
            # processed. It can be retried
            # when the script runs again.

            continue

        print(
            f"Related wallets returned: "
            f"{len(related_wallets)}"
        )

        # ----------------------------------------------------
        # Store relationship rows
        # ----------------------------------------------------

        for wallet in related_wallets:

            results.append(
                {
                    "seed_address":
                        address,

                    "related_address":
                        wallet.get(
                            "address",
                            ""
                        ),

                    "address_label":
                        wallet.get(
                            "address_label",
                            ""
                        ),

                    "relation":
                        wallet.get(
                            "relation",
                            ""
                        ),

                    "transaction_hash":
                        wallet.get(
                            "transaction_hash",
                            ""
                        ),

                    "block_timestamp":
                        wallet.get(
                            "block_timestamp",
                            ""
                        ),

                    "order":
                        wallet.get(
                            "order",
                            ""
                        ),

                    "chain":
                        wallet.get(
                            "chain",
                            ""
                        ),
                }
            )

        # ----------------------------------------------------
        # Mark seed address as processed
        # ----------------------------------------------------

        processed_addresses.add(
            address
        )

        # ----------------------------------------------------
        # Save checkpoint
        # ----------------------------------------------------

        if (
            len(processed_addresses)
            % CHECKPOINT_EVERY
            == 0
        ):

            save_results(
                results
            )

            save_checkpoint(
                processed_addresses
            )

            print()
            print(
                "CHECKPOINT SAVED"
            )

            print(
                f"Processed: "
                f"{len(processed_addresses)}"
            )

            print(
                f"Relationship rows: "
                f"{len(results)}"
            )

        # ----------------------------------------------------
        # Delay
        # ----------------------------------------------------

        time.sleep(
            REQUEST_DELAY
        )

    # --------------------------------------------------------
    # Final save
    # --------------------------------------------------------

    save_results(
        results
    )

    save_checkpoint(
        processed_addresses
    )

    # --------------------------------------------------------
    # Candidate generation
    # --------------------------------------------------------

    create_candidate_file(
        results,
        seed_addresses
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()

    print(
        "=" * 70
    )

    print(
        "FINAL SUMMARY"
    )

    print(
        "=" * 70
    )

    print()

    print(
        f"Seed addresses: "
        f"{len(seed_addresses)}"
    )

    print(
        f"Processed addresses: "
        f"{len(processed_addresses)}"
    )

    print(
        f"Relationship rows: "
        f"{len(results)}"
    )

    if results:

        result_df = pd.DataFrame(
            results
        )

        if "relation" in result_df.columns:

            print()

            print(
                "RELATION TYPES"
            )

            print(
                result_df[
                    "relation"
                ].value_counts()
            )

        if "chain" in result_df.columns:

            print()

            print(
                "CHAINS"
            )

            print(
                result_df[
                    "chain"
                ].value_counts()
            )

    print()

    print(
        f"Relationship output:"
    )

    print(
        OUTPUT_FILE
    )

    print()

    print(
        f"Candidate output:"
    )

    print(
        CANDIDATE_FILE
    )

    print()

    print(
        "Checkpoint:"
    )

    print(
        CHECKPOINT_FILE
    )


if __name__ == "__main__":
    main()