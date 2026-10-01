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

OUTPUT_FILE = "./data/output/bitquery_relationships.csv"
CANDIDATE_FILE = "./data/output/bitquery_new_candidates.csv"
CHECKPOINT_FILE = "./data/checkpoint/bitquery_checkpoint.csv"
REPORT_FILE = "./reports/bitquery_test_report.txt"

BITQUERY_API_URL = "https://streaming.bitquery.io/graphql"

CHAIN = "eth"

# IMPORTANT:
# Start with 10 addresses.
# Later change this to None to process the full dataset.
MAX_ADDRESSES = None

# Maximum number of transfer records requested per seed address.
RESULT_LIMIT = 100

REQUEST_DELAY = 0.2
MAX_RETRIES = 3


# ============================================================
# GRAPHQL QUERY
# ============================================================

QUERY = """
query ($address: String!, $limit: Int!) {

  EVM(
    network: eth
    dataset: realtime
  ) {

    Transfers(

      where: {

        any: [

          {
            Transfer: {
              Sender: {
                is: $address
              }
            }
          }

          {
            Transfer: {
              Receiver: {
                is: $address
              }
            }
          }

        ]

        Transfer: {
          Success: true
        }

      }

      limit: {
        count: $limit
      }

      orderBy: {
        descending: Block_Time
      }

    ) {

      Block {
        Number
        Time
      }

      Transaction {
        Hash
        From
        To
        Index
      }

      Transfer {
        Amount
        AmountInUSD
        Sender
        Receiver
        Type

        Currency {
          Name
          Symbol
          SmartContract
          Native
        }
      }

    }

  }

}
"""


# ============================================================
# ADDRESS VALIDATION
# ============================================================

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


# ============================================================
# LOAD SEED ADDRESSES
# ============================================================

def load_seed_addresses():

    df = pd.read_csv(INPUT_FILE)

    print(f"Input rows: {len(df)}")

    addresses = []

    for value in df["Address"]:

        address = str(value).strip().lower()

        if is_valid_eth_address(address):
            addresses.append(address)

    # Remove duplicates while preserving order
    addresses = list(dict.fromkeys(addresses))

    print(f"Valid unique seed addresses: {len(addresses)}")

    if MAX_ADDRESSES is not None:

        addresses = addresses[:MAX_ADDRESSES]

        print(
            f"Testing first {MAX_ADDRESSES} seed addresses."
        )

    else:

        print("Processing ALL seed addresses.")

    return addresses


# ============================================================
# BITQUERY REQUEST
# ============================================================

def query_bitquery(address):

    token = os.getenv("BITQUERY_API_KEY")

    if not token:
        raise RuntimeError(
            "BITQUERY_API_KEY is not set."
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "query": QUERY,
        "variables": {
            "address": address,
            "limit": RESULT_LIMIT,
        },
    }

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            response = requests.post(
                BITQUERY_API_URL,
                headers=headers,
                json=payload,
                timeout=60,
            )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            if response.status_code == 200:

                result = response.json()

                if "errors" in result:

                    print()
                    print("Bitquery GraphQL error:")
                    print(result["errors"])

                    return None

                return result

            # ------------------------------------------------
            # AUTHENTICATION
            # ------------------------------------------------

            if response.status_code == 401:

                print()
                print("ERROR: Bitquery returned HTTP 401.")
                print("Check BITQUERY_API_KEY.")

                return None

            # ------------------------------------------------
            # PLAN / ACCESS ERROR
            # ------------------------------------------------

            if response.status_code == 403:

                print()
                print("ERROR: Bitquery returned HTTP 403.")
                print(response.text[:2000])

                if "restricted" in response.text.lower():
                    print()
                    print(
                        "The current Bitquery plan does not "
                        "allow this dataset."
                    )

                return None

            # ------------------------------------------------
            # RATE LIMIT
            # ------------------------------------------------

            if response.status_code == 429:

                wait_time = attempt * 5

                print(
                    f"Rate limited. Waiting {wait_time}s..."
                )

                time.sleep(wait_time)

                continue

            # ------------------------------------------------
            # OTHER HTTP ERROR
            # ------------------------------------------------

            print(
                f"Bitquery HTTP {response.status_code}"
            )

            print(response.text[:1000])

            if attempt < MAX_RETRIES:

                time.sleep(attempt * 2)

            else:

                return None

        except requests.exceptions.RequestException as e:

            print()
            print(f"Network error: {e}")

            if attempt < MAX_RETRIES:

                time.sleep(attempt * 2)

            else:

                return None

    return None


# ============================================================
# EXTRACT TRANSFERS
# ============================================================

def get_transfers(address):

    result = query_bitquery(address)

    if result is None:
        return None

    try:

        transfers = (
            result
            .get("data", {})
            .get("EVM", {})
            .get("Transfers", [])
        )

        if not isinstance(transfers, list):
            return []

        return transfers

    except Exception as e:

        print(
            f"Could not parse Bitquery response: {e}"
        )

        return None


# ============================================================
# CHECKPOINT
# ============================================================

def load_checkpoint():

    if not os.path.exists(CHECKPOINT_FILE):
        return set()

    try:

        df = pd.read_csv(CHECKPOINT_FILE)

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


def save_checkpoint(processed_addresses):

    os.makedirs(
        "./data/checkpoint",
        exist_ok=True
    )

    df = pd.DataFrame({
        "address": sorted(processed_addresses)
    })

    df.to_csv(
        CHECKPOINT_FILE,
        index=False
    )


# ============================================================
# PREVIOUS RESULTS
# ============================================================

def load_previous_results():

    if not os.path.exists(OUTPUT_FILE):
        return []

    try:

        df = pd.read_csv(OUTPUT_FILE)

        return df.to_dict("records")

    except Exception as e:

        print(
            f"Could not load previous results: {e}"
        )

        return []


# ============================================================
# SAVE RELATIONSHIPS
# ============================================================

def save_relationships(rows):

    os.makedirs(
        "./data/output",
        exist_ok=True
    )

    if not rows:
        return

    df = pd.DataFrame(rows)

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )


# ============================================================
# CREATE CANDIDATE FILE
# ============================================================

def create_candidate_file(
    relationship_rows,
    seed_addresses
):

    seed_set = {
        address.lower()
        for address in seed_addresses
    }

    candidates = {}

    for row in relationship_rows:

        seed_address = (
            str(row.get("seed_address", ""))
            .lower()
            .strip()
        )

        sender = (
            str(row.get("sender", ""))
            .lower()
            .strip()
        )

        receiver = (
            str(row.get("receiver", ""))
            .lower()
            .strip()
        )

        # Determine the other side of the transfer
        if sender == seed_address:

            candidate = receiver
            relationship = "outgoing"

        elif receiver == seed_address:

            candidate = sender
            relationship = "incoming"

        else:

            # Unexpected record
            continue

        if not is_valid_eth_address(candidate):
            continue

        # Remove addresses already in our seed dataset
        if candidate in seed_set:
            continue

        if candidate not in candidates:

            candidates[candidate] = {
                "candidate_address": candidate,
                "discovered_from": seed_address,
                "relationship": relationship,
                "address_label": "",
                "currency_name": row.get(
                    "currency_name",
                    ""
                ),
                "currency_symbol": row.get(
                    "currency_symbol",
                    ""
                ),
                "currency_contract": row.get(
                    "currency_contract",
                    ""
                ),
                "block_time": row.get(
                    "block_time",
                    ""
                ),
                "transaction_hash": row.get(
                    "transaction_hash",
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
        f"New unique candidate addresses: "
        f"{len(candidate_df)}"
    )

    print(
        f"Saved candidates to: "
        f"{CANDIDATE_FILE}"
    )


# ============================================================
# CREATE REPORT
# ============================================================

def create_report(
    seed_addresses,
    processed_addresses,
    relationship_rows
):

    os.makedirs(
        "./reports",
        exist_ok=True
    )

    unique_candidates = set()

    seed_set = {
        address.lower()
        for address in seed_addresses
    }

    for row in relationship_rows:

        seed = (
            str(row.get("seed_address", ""))
            .lower()
            .strip()
        )

        sender = (
            str(row.get("sender", ""))
            .lower()
            .strip()
        )

        receiver = (
            str(row.get("receiver", ""))
            .lower()
            .strip()
        )

        if sender == seed:

            candidate = receiver

        elif receiver == seed:

            candidate = sender

        else:

            continue

        if (
            is_valid_eth_address(candidate)
            and candidate not in seed_set
        ):

            unique_candidates.add(candidate)

    report_lines = [

        "=" * 70,
        "BITQUERY ADDRESS EXPANSION TEST REPORT",
        "=" * 70,
        "",
        "Objective:",
        (
            "Evaluate Bitquery as an indexed-data alternative "
            "for expanding the existing Ethereum address dataset."
        ),
        "",
        "Data source:",
        "Existing eth_addresses.csv seed dataset.",
        "",
        "Bitquery dataset:",
        "realtime",
        "",
        "Important limitation:",
        (
            "The current Bitquery account does not have access "
            "to the archive dataset. Therefore this experiment "
            "evaluates recent realtime activity only and does "
            "not represent complete historical Ethereum activity."
        ),
        "",
        "TEST RESULTS",
        "-" * 70,
        f"Seed addresses selected: {len(seed_addresses)}",
        f"Addresses processed: {len(processed_addresses)}",
        f"Relationship rows collected: {len(relationship_rows)}",
        f"Unique new candidate addresses: {len(unique_candidates)}",
        "",
        "OUTPUT FILES",
        "-" * 70,
        f"Relationships: {OUTPUT_FILE}",
        f"Candidates:    {CANDIDATE_FILE}",
        f"Checkpoint:    {CHECKPOINT_FILE}",
        "",
        "Interpretation:",
        (
            "Candidate addresses represent counterparties observed "
            "in Bitquery transfer records and are not automatically "
            "verified identities. Further validation is required."
        ),
        "",
        "=" * 70,
    ]

    with open(
        REPORT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "\n".join(report_lines)
        )

    print()
    print(
        f"Report saved to: {REPORT_FILE}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("BITQUERY ADDRESS EXPANSION")
    print("=" * 70)
    print()

    if not os.getenv("BITQUERY_API_KEY"):

        print(
            "ERROR: BITQUERY_API_KEY is not set."
        )

        return

    print("Bitquery API token detected.")
    print()

    seed_addresses = load_seed_addresses()

    print()

    processed_addresses = load_checkpoint()

    relationship_rows = load_previous_results()

    print(
        f"Existing relationship rows: "
        f"{len(relationship_rows)}"
    )

    print()

    total = len(seed_addresses)

    for position, address in enumerate(
        seed_addresses,
        start=1
    ):

        if address in processed_addresses:
            continue

        print("=" * 70)

        print(
            f"Progress: {position}/{total}"
        )

        print(
            f"Seed address: {address}"
        )

        transfers = get_transfers(address)

        # ----------------------------------------------------
        # API ERROR
        # ----------------------------------------------------

        if transfers is None:

            print(
                "ERROR: Could not retrieve data."
            )

            continue

        print(
            f"Transfers returned: {len(transfers)}"
        )

        # ----------------------------------------------------
        # PROCESS TRANSFERS
        # ----------------------------------------------------

        for transfer in transfers:

            block = transfer.get(
                "Block",
                {}
            )

            transaction = transfer.get(
                "Transaction",
                {}
            )

            transfer_data = transfer.get(
                "Transfer",
                {}
            )

            currency = transfer_data.get(
                "Currency",
                {}
            )

            relationship_rows.append({

                "seed_address":
                    address,

                "sender":
                    transfer_data.get(
                        "Sender",
                        ""
                    ),

                "receiver":
                    transfer_data.get(
                        "Receiver",
                        ""
                    ),

                "amount":
                    transfer_data.get(
                        "Amount",
                        ""
                    ),

                "amount_usd":
                    transfer_data.get(
                        "AmountInUSD",
                        ""
                    ),

                "transfer_type":
                    transfer_data.get(
                        "Type",
                        ""
                    ),

                "currency_name":
                    currency.get(
                        "Name",
                        ""
                    ),

                "currency_symbol":
                    currency.get(
                        "Symbol",
                        ""
                    ),

                "currency_contract":
                    currency.get(
                        "SmartContract",
                        ""
                    ),

                "currency_native":
                    currency.get(
                        "Native",
                        ""
                    ),

                "transaction_hash":
                    transaction.get(
                        "Hash",
                        ""
                    ),

                "transaction_from":
                    transaction.get(
                        "From",
                        ""
                    ),

                "transaction_to":
                    transaction.get(
                        "To",
                        ""
                    ),

                "transaction_index":
                    transaction.get(
                        "Index",
                        ""
                    ),

                "block_number":
                    block.get(
                        "Number",
                        ""
                    ),

                "block_time":
                    block.get(
                        "Time",
                        ""
                    ),
            })

        # ----------------------------------------------------
        # MARK ADDRESS AS PROCESSED
        # ----------------------------------------------------

        processed_addresses.add(address)

        # Save after every address during testing
        save_relationships(
            relationship_rows
        )

        save_checkpoint(
            processed_addresses
        )

        print(
            f"Checkpoint saved. "
            f"Processed: "
            f"{len(processed_addresses)}"
        )

        time.sleep(
            REQUEST_DELAY
        )

    # ========================================================
    # FINAL OUTPUT
    # ========================================================

    save_relationships(
        relationship_rows
    )

    save_checkpoint(
        processed_addresses
    )

    create_candidate_file(
        relationship_rows,
        seed_addresses
    )

    create_report(
        seed_addresses,
        processed_addresses,
        relationship_rows
    )

    print()
    print("=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
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
        f"{len(relationship_rows)}"
    )

    print()
    print(
        "Relationship output:"
    )

    print(
        OUTPUT_FILE
    )

    print()
    print(
        "Candidate output:"
    )

    print(
        CANDIDATE_FILE
    )

    print()
    print(
        "Report:"
    )

    print(
        REPORT_FILE
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