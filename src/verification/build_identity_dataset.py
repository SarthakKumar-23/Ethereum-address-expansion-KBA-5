import os
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

CANDIDATE_FILE = "data/output/alchemy_candidates.csv"
ETHERSCAN_FILE = "data/output/alchemy_verified_candidates.csv"
ENS_FILE = "data/output/alchemy_ens_verified.csv"

OUTPUT_FILE = "data/output/alchemy_identity_evidence.csv"


# ============================================================
# LOAD FILE SAFELY
# ============================================================

def load_csv(path):

    if not os.path.exists(path):

        print(f"ERROR: File not found: {path}")

        return None

    df = pd.read_csv(path)

    print(
        f"Loaded {len(df)} rows from {path}"
    )

    return df


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("BUILD IDENTITY EVIDENCE DATASET")
    print("=" * 70)
    print()

    # --------------------------------------------------------
    # Load datasets
    # --------------------------------------------------------

    candidates = load_csv(
        CANDIDATE_FILE
    )

    etherscan = load_csv(
        ETHERSCAN_FILE
    )

    ens = load_csv(
        ENS_FILE
    )

    if (
        candidates is None
        or etherscan is None
        or ens is None
    ):
        return

    # --------------------------------------------------------
    # Validate required columns
    # --------------------------------------------------------

    if "candidate_address" not in candidates.columns:

        print(
            "ERROR: candidate_address missing "
            "from candidate dataset."
        )

        return

    if "address" not in etherscan.columns:

        print(
            "ERROR: address missing "
            "from Etherscan dataset."
        )

        return

    if "address" not in ens.columns:

        print(
            "ERROR: address missing "
            "from ENS dataset."
        )

        return

    # --------------------------------------------------------
    # Normalize addresses
    # --------------------------------------------------------

    candidates["candidate_address"] = (
        candidates["candidate_address"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    etherscan["address"] = (
        etherscan["address"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    ens["address"] = (
        ens["address"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    # --------------------------------------------------------
    # Remove duplicate candidate rows
    # --------------------------------------------------------

    candidates = candidates.drop_duplicates(
        subset=["candidate_address"]
    )

    etherscan = etherscan.drop_duplicates(
        subset=["address"]
    )

    ens = ens.drop_duplicates(
        subset=["address"]
    )

    print()
    print(
        f"Unique candidates: {len(candidates)}"
    )

    # --------------------------------------------------------
    # Select Etherscan evidence
    # --------------------------------------------------------

    etherscan_columns = [
        "address",
        "verification_status",
        "contract_name",
        "proxy",
        "implementation",
        "similar_match",
        "identity_evidence",
    ]

    etherscan_columns = [
        column
        for column in etherscan_columns
        if column in etherscan.columns
    ]

    etherscan_evidence = etherscan[
        etherscan_columns
    ].copy()

    # --------------------------------------------------------
    # Select ENS evidence
    # --------------------------------------------------------

    ens_columns = [
        "address",
        "ens_name",
        "forward_resolved_address",
        "ens_verified",
        "verification_source",
        "error",
    ]

    ens_columns = [
        column
        for column in ens_columns
        if column in ens.columns
    ]

    ens_evidence = ens[
        ens_columns
    ].copy()

    # Rename ENS source column so it doesn't conflict
    if "verification_source" in ens_evidence.columns:

        ens_evidence = ens_evidence.rename(
            columns={
                "verification_source":
                    "ens_verification_source"
            }
        )

    # --------------------------------------------------------
    # Merge Etherscan evidence
    # --------------------------------------------------------

    result = candidates.merge(
        etherscan_evidence,
        left_on="candidate_address",
        right_on="address",
        how="left",
    )

    # Remove duplicate address column
    if "address" in result.columns:

        result = result.drop(
            columns=["address"]
        )

    # --------------------------------------------------------
    # Merge ENS evidence
    # --------------------------------------------------------

    result = result.merge(
        ens_evidence,
        left_on="candidate_address",
        right_on="address",
        how="left",
    )

    if "address" in result.columns:

        result = result.drop(
            columns=["address"]
        )

    # --------------------------------------------------------
    # Normalize verification values
    # --------------------------------------------------------

    result["etherscan_verified"] = (
        result[
            "verification_status"
        ]
        .fillna("")
        .eq("VERIFIED_CONTRACT")
    )

    result["ens_verified"] = (
        result[
            "ens_verified"
        ]
        .fillna(False)
        .astype(bool)
    )

    # --------------------------------------------------------
    # Determine evidence sources
    # --------------------------------------------------------

    def determine_sources(row):

        sources = []

        if row["etherscan_verified"]:

            sources.append("Etherscan")

        if row["ens_verified"]:

            sources.append("ENS")

        if not sources:

            return ""

        return ";".join(sources)

    result["identity_evidence_sources"] = (
        result.apply(
            determine_sources,
            axis=1
        )
    )

    # --------------------------------------------------------
    # Determine evidence category
    # --------------------------------------------------------

    def determine_category(row):

        etherscan = row[
            "etherscan_verified"
        ]

        ens = row[
            "ens_verified"
        ]

        if etherscan and ens:

            return "MULTIPLE_SOURCES"

        if etherscan:

            return "ETHERSCAN_ONLY"

        if ens:

            return "ENS_ONLY"

        return "NO_IDENTITY_EVIDENCE"

    result["identity_evidence_category"] = (
        result.apply(
            determine_category,
            axis=1
        )
    )

    # --------------------------------------------------------
    # Identity name
    # --------------------------------------------------------

    def determine_identity(row):

        ens_name = str(
            row.get(
                "ens_name",
                ""
            )
        ).strip()

        contract_name = str(
            row.get(
                "contract_name",
                ""
            )
        ).strip()

        if ens_name and row["ens_verified"]:

            return ens_name

        if (
            contract_name
            and row["etherscan_verified"]
        ):

            return contract_name

        return ""

    result["identity"] = (
        result.apply(
            determine_identity,
            axis=1
        )
    )

    # --------------------------------------------------------
    # Identity type
    # --------------------------------------------------------

    def determine_identity_type(row):

        if row["ens_verified"]:

            return "ENS_NAME"

        if row["etherscan_verified"]:

            return "VERIFIED_CONTRACT"

        return ""

    result["identity_type"] = (
        result.apply(
            determine_identity_type,
            axis=1
        )
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    os.makedirs(
        "data/output",
        exist_ok=True
    )

    result.to_csv(
        OUTPUT_FILE,
        index=False
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    total = len(result)

    etherscan_count = (
        result["etherscan_verified"]
        .sum()
    )

    ens_count = (
        result["ens_verified"]
        .sum()
    )

    multiple_count = (
        (
            result[
                "identity_evidence_category"
            ]
            == "MULTIPLE_SOURCES"
        )
        .sum()
    )

    etherscan_only = (
        (
            result[
                "identity_evidence_category"
            ]
            == "ETHERSCAN_ONLY"
        )
        .sum()
    )

    ens_only = (
        (
            result[
                "identity_evidence_category"
            ]
            == "ENS_ONLY"
        )
        .sum()
    )

    no_evidence = (
        (
            result[
                "identity_evidence_category"
            ]
            == "NO_IDENTITY_EVIDENCE"
        )
        .sum()
    )

    print()
    print("=" * 70)
    print("IDENTITY EVIDENCE SUMMARY")
    print("=" * 70)
    print()

    print(
        f"Unique candidates:       {total}"
    )

    print(
        f"Etherscan verified:      {etherscan_count}"
    )

    print(
        f"ENS verified:             {ens_count}"
    )

    print(
        f"Multiple sources:        {multiple_count}"
    )

    print(
        f"Etherscan only:          {etherscan_only}"
    )

    print(
        f"ENS only:                 {ens_only}"
    )

    print(
        f"No identity evidence:    {no_evidence}"
    )

    print()
    print(
        f"Saved to:\n{OUTPUT_FILE}"
    )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()