import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

INPUT_FILE = "data/input/eth_addresses.csv"
RAW_OUTPUT = "data/output/alchemy_relationship.csv"
CANDIDATE_OUTPUT = "data/output/alchemy_candidates.csv"

MAX_ADDRESSES = 10
ALCHEMY_URL = "https://eth-mainnet.g.alchemy.com/v2/" + os.getenv("ALCHEMY_API_KEY")

def get_transfers(address, direction):
    payload = {
        "jsonrpc":"2.0",
        "id":1,
        "method":"alchemy_getAssetTransfers",
        "params":[{
            "fromBlock":"0x0",
            "toBlock":"latest",
            "category":["external","erc20","erc721","erc1155"],
            "withMetadata":True,
            "excludeZeroValue":False,
            "maxcount":"0x32",
            "fromAddress":address if direction=="out" else None,
            "toAddress": address if direction=="in" else None
        }]
    }

    payload["params"][0] = {k:v for k,v in payload["params"][0].items() if v is not None}

    r = requests.post(ALCHEMY_URL, json=payload, timeout=30)
    if r.status_code != 200:
        return []

    data = r.json()
    return data.get("result", {}).get("transfers", [])

def main():
    df = pd.read_csv(INPUT_FILE)
    seeds = df["Address"].drop_duplicates().head(MAX_ADDRESSES).str.lower()

    raw_rows = []
    candidate_set = set()

    for i, seed in enumerate(seeds, start=1):
        print(f"{i}/{len(seeds)} : {seed}")

        outgoing = get_transfers(seed, "out")
        incoming = get_transfers(seed, "in")

        for tx in outgoing + incoming:
            sender = tx.get("from", "").lower()
            receiver = tx.get("to", "").lower()

            candidate = receiver if sender == seed else sender

            raw_rows.append({
                "seed_address": seed,
                "candidate_address": candidate,
                "direction": "outgoing" if sender == seed else "incoming",
                "asset": tx.get("asset"),
                "value": tx.get("value"),
                "hash": tx.get("hash"),
                "block_time": tx.get("metadata", {}).get("blockTimestamp")
            })

            if candidate and candidate != seed:
                candidate_set.add(candidate)

        time.sleep(0.2)

    raw_df = pd.DataFrame(raw_rows)
    raw_df.to_csv(RAW_OUTPUT, index=False)

    candidate_df = pd.DataFrame({
        "candidate_address": sorted(candidate_set)
    })
    candidate_df.to_csv(CANDIDATE_OUTPUT, index=False)

    print("\n=== SUMMARY ===")
    print(f"Seed addresses: {len(seeds)}")
    print(f"Relationships: {len(raw_df)}")
    print(f"Unique candidates: {len(candidate_df)}")
    print(f"Saved: {CANDIDATE_OUTPUT}")

if __name__ == "__main__":
    main()