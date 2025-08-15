import json, ast, re
from typing import Iterable, Dict, List, Tuple, Any
from collections import Counter
import pandas as pd
import matplotlib.pyplot as plt


def count_valid_privacy_policies(csv_path, text_col="Policy Text"):
    """
    Count rows with a valid policy in `text_col` (default: 'Policy Text').
    Valid == does NOT contain 'no privacy policy found' or 'no privacy url found'
    (case-insensitive), and is not empty/NA.
    """
    df = pd.read_csv(csv_path, dtype=str, encoding_errors="ignore")
    s = df[text_col].fillna("")

    invalid = s.str.contains(r"no\s+privacy\s+(policy|url)\s+found", case=False, regex=True)
    valid = (~invalid) & s.str.strip().ne("")
    return int(valid.sum())

def count_privacy_url_statuses(csv_path, url_col="Privacy Policy URL"):
    """
    Count special statuses in the Privacy Policy URL column (case-insensitive):
      - DOMAIN NOT IN ENGLISH
      - DOMAIN OUTDATED
      - DOMAIN TIMED OUT
      - Not Found
      - No/Not privacy url/policy found

    Returns a dict with the counts.
    """
    df = pd.read_csv(csv_path, dtype=str, encoding_errors="ignore")
    s = df[url_col].fillna("").astype(str).str.lower()

    patterns = {
        "not_in_english": r"domain\s+not\s+in\s+english",
        "outdated": r"domain\s+outdated",
        "timed_out": r"domain\s+timed\s+out",
        "not_found": r"^\s*not\s*found\s*$",
        "no_privacy_url_found": r"\b(?:no|not)\s+privacy\s+(?:url|policy)\s+found\b",
    }

    counts = {k: 0 for k in patterns}

    for cell in s:
        for key, pat in patterns.items():
            if re.search(pat, cell):
                counts[key] += 1
                break  # assume one status per cell

    return counts

def count_links_for_successful_scrapes(csv_path, url_col="Privacy Policy URL"):
    """
    Count links ONLY for rows that are successful scrapes in `url_col`.
    A row is considered unsuccessful if the cell contains any of these
    (case-insensitive): DOMAIN NOT IN ENGLISH, DOMAIN OUTDATED,
    DOMAIN TIMED OUT, Not Found, No/Not privacy url/policy found.
    Otherwise, any http(s) links present are counted.

    Returns
    -------
    dict with:
      - num_successful_rows
      - total_links
      - per_row_counts  (pd.Series of link counts for successful rows)
    """
    df = pd.read_csv(csv_path, dtype=str, encoding_errors="ignore")
    s = df[url_col].fillna("").astype(str)

    status_terms = [
        "domain not in english",
        "domain outdated",
        "domain timed out",
        "not found",
        "no privacy url found",
        "no privacy policy found",
        "not privacy url found",   # handle possible variant
    ]

    url_pattern = re.compile(r'https?://[^\s\'"\]\),]+', re.I)

    def is_unsuccessful(cell: str) -> bool:
        t = cell.lower()
        # if it already contains a URL, treat as successful
        if url_pattern.search(cell):
            return False
        return any(term in t for term in status_terms)

    def link_count(cell: str) -> int:
        return len(url_pattern.findall(cell))

    # keep only rows that are NOT unsuccessful and that actually contain links
    mask_success = ~s.map(is_unsuccessful)
    per_row_counts = s[mask_success].map(link_count)
    per_row_counts = per_row_counts[per_row_counts > 0]

    return {
        "num_successful_rows": int(len(per_row_counts)),
        "total_links": int(per_row_counts.sum()),
        "per_row_counts": per_row_counts,  # index matches original rows
    }

def average_links_for_successful_scrapes(csv_path, url_col="Privacy Policy URL"):
    """
    Compute the average number of links for SUCCESSFUL scrapes in `url_col`.
    Unsuccessful statuses (case-insensitive): DOMAIN NOT IN ENGLISH, DOMAIN OUTDATED,
    DOMAIN TIMED OUT, Not Found, and 'No/Not privacy url/policy found'.

    Returns
    -------
    avg_links : float
        Average number of links among successful rows (0.0 if none).
    per_row_counts : pd.Series
        Link counts per successful row (index aligns with the original DataFrame).
    """
    df = pd.read_csv(csv_path, dtype=str, encoding_errors="ignore")
    s = df[url_col].fillna("").astype(str)

    status_patterns = [
        r"domain\s+not\s+in\s+english",
        r"domain\s+outdated",
        r"domain\s+timed\s+out",
        r"^\s*not\s*found\s*$",
        r"\b(?:no|not)\s+privacy\s+(?:url|policy)\s+found\b",
    ]
    status_re = re.compile("|".join(status_patterns), re.I)
    url_re = re.compile(r"https?://[^\s'\"\]\),]+", re.I)

    def link_count(cell: str) -> int:
        # Exclude rows with any failure status
        if status_re.search(cell):
            return 0

        cell = cell.strip()

        # Try to parse list-like strings: "['https://..', 'https://..']"
        try:
            val = ast.literal_eval(cell)
            if isinstance(val, list):
                return sum(1 for x in val if isinstance(x, str) and url_re.search(x))
        except Exception:
            pass

        # Fallback: count URLs directly in the string
        return len(url_re.findall(cell))

    counts = s.apply(link_count)

    # Only consider rows that actually contain links (i.e., successful scrapes)
    successful_counts = counts[counts > 0]
    avg_links = float(successful_counts.mean()) if len(successful_counts) else 0.0

    return avg_links, successful_counts


def plot_policy_word_counts(csv_path, text_col="Policy Text", save_path=None, print_stats=True):
    """
    Plot per-policy word counts for VALID policies and draw ONLY the mean line (in red).
    Valid == text does NOT contain 'No privacy policy/url found' (case-insensitive)
    and is not empty.

    Prints mean/min/max to stdout (not on the plot) and returns them.

    Returns
    -------
    dict: {"mean": float, "min": int, "max": int, "counts": pd.Series}
    """
    df = pd.read_csv(csv_path, dtype=str, encoding_errors="ignore")
    s = df[text_col].fillna("")

    # Filter invalid rows
    invalid = s.str.contains(r"no\s+privacy\s+(policy|url)\s+found", case=False, regex=True)
    valid_texts = s[~invalid & s.str.strip().ne("")]

    # Word counts
    word_counts = valid_texts.apply(lambda x: len(re.findall(r"\b\w+\b", x)))

    if word_counts.empty:
        if print_stats:
            print("No valid policies found.")
        plt.figure()
        plt.title("Privacy Policy Word Counts — no valid policies found")
        plt.xlabel("Valid policy index")
        plt.ylabel("Word count")
        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=200, bbox_inches="tight")
        plt.show()
        return {"mean": 0.0, "min": 0, "max": 0, "counts": word_counts}

    mean_wc = float(word_counts.mean())
    min_wc = int(word_counts.min())
    max_wc = int(word_counts.max())

    # Print stats (but do not draw min/max on the plot)
    if print_stats:
        print(f"Mean word count: {mean_wc:.2f}")
        print(f"Min word count:  {min_wc}")
        print(f"Max word count:  {max_wc}")

    # Plot individuals + ONLY the mean line (in red as requested)
    plt.figure()
    plt.plot(range(1, len(word_counts) + 1), word_counts.values, marker="o", linestyle="", label="Per-policy")
    plt.axhline(mean_wc, linestyle="--", linewidth=1, color="red", label=f"Mean = {mean_wc:.1f}")
    plt.title("Privacy Policy Word Counts")
    plt.xlabel("Valid policy index")
    plt.ylabel("Word count")
    plt.legend()
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.show()

    return {"mean": mean_wc, "min": min_wc, "max": max_wc, "counts": word_counts}


def count_need_review_with_valid_policy(csv_path, text_col="Policy Text", review_col="Needs Review",
                                        return_rows=False, debug=False):
    """
    One function that counts rows where:
      - Needs Review == True
      - Policy Text is VALID (not empty and does NOT contain
        'No privacy policy found' or 'No privacy url found', case-insensitive).

    Parameters
    ----------
    csv_path : str
    text_col : str  (column label; matched case-insensitively)
    review_col : str (column label; matched case-insensitively)
    return_rows : bool (if True, also return the matching DataFrame slice)
    debug : bool (if True, print quick diagnostics)

    Returns
    -------
    count : int
    (optional) rows : pd.DataFrame
    """
    df = pd.read_csv(csv_path, dtype=str, encoding_errors="ignore")

    # Resolve column names case-/space-insensitively
    def _norm(s):  # local helper, still a single public function
        return re.sub(r"\s+", " ", str(s).replace("\u00A0", " ")).strip().lower()
    colmap = { _norm(c): c for c in df.columns }
    if _norm(text_col) not in colmap or _norm(review_col) not in colmap:
        missing = [n for n in (text_col, review_col) if _norm(n) not in colmap]
        raise KeyError(f"Missing column(s): {missing}. Available: {list(df.columns)}")
    text_col = colmap[_norm(text_col)]
    review_col = colmap[_norm(review_col)]

    # VALID policy text mask
    s = df[text_col].fillna("").astype(str)
    invalid_re = re.compile(r"\bno\s+privacy\s+(?:policy|url)\s+found\b", re.I)
    valid_policy = (~s.str.contains(invalid_re)) & s.str.strip().ne("")

    # Needs Review mask: expects only True/False or 'True'/'False'
    needs_review = (
        df[review_col].astype(str).str.strip().str.lower()
          .map({"true": True, "false": False})
          .fillna(False)
    )

    mask = needs_review & valid_policy
    count = int(mask.sum())

    if debug:
        print(f"Rows total: {len(df)}")
        print(f"Valid policy texts: {int(valid_policy.sum())}")
        print(f"'Needs Review' == True: {int(needs_review.sum())}")
        print(f"Intersection: {count}")

    return (count, df.loc[mask].copy()) if return_rows else count

def summarize_policy_annotations(
    csv_path: str,
    annot_col: str = "Annotation",
    # now includes 'sharing'
    categories: Iterable[str] = ("types", "purposes", "retention", "sharing", "rights", "contact"),
    normalize: bool = True,
) -> Dict[str, Any]:
    """
    Summarize annotation values across policies (assumes CSV already filtered to valid policies).

    For each category in `categories`, returns:
      - total count of values across all policies
      - the unique values (and how many unique)
      - average number of values per policy
    """
    df = pd.read_csv(csv_path, dtype=str, encoding_errors="ignore")
    if annot_col not in df:
        raise KeyError(f"Column '{annot_col}' not found. Available columns: {list(df.columns)}")

    annotations = df[annot_col].dropna().astype(str)
    n_policies = len(annotations)

    totals = {k: 0 for k in categories}
    unique_sets = {k: set() for k in categories}

    def _norm(v: str) -> str:
        if not normalize:
            return str(v)
        return re.sub(r"\s+", " ", str(v)).strip().lower()

    for cell in annotations:
        cell = cell.strip()
        if not cell:
            continue
        # Parse JSON first; fall back to Python literal
        try:
            data = json.loads(cell)
        except Exception:
            try:
                data = ast.literal_eval(cell)
            except Exception:
                continue
        if not isinstance(data, dict):
            continue

        for key in categories:
            vals = data.get(key, [])
            if isinstance(vals, str):
                vals = [vals]
            elif not isinstance(vals, (list, tuple)):
                vals = [vals]
            cleaned = [_norm(v) for v in vals if str(v).strip() != ""]
            totals[key] += len(cleaned)
            unique_sets[key].update(cleaned)

    averages = {k: (totals[k] / n_policies if n_policies else 0.0) for k in categories}

    return {
        "n_policies": n_policies,
        "totals": totals,
        "unique": {k: sorted(unique_sets[k]) for k in categories},
        "unique_counts": {k: len(unique_sets[k]) for k in categories},
        "averages_per_policy": averages,
    }

def top_annotation_values(
    csv_path: str,
    annot_col: str = "Annotation",
    # now includes 'sharing'
    categories: Iterable[str] = ("types", "purposes", "retention", "sharing", "rights", "contact"),
    n: int = 10,
    normalize: bool = True,
) -> Dict[str, List[Tuple[str, int]]]:
    """
    For each category in `categories`, return the top-N most frequent values
    from the JSON-like `annot_col`. Assumes CSV contains only valid policies.

    Returns: {category: [(value, count), ...]}
    """
    df = pd.read_csv(csv_path, dtype=str, encoding_errors="ignore")
    if annot_col not in df:
        raise KeyError(f"Column '{annot_col}' not found. Available: {list(df.columns)}")

    def _norm(v: str) -> str:
        if not normalize:
            return str(v)
        return re.sub(r"\s+", " ", str(v)).strip().lower()

    counters: Dict[str, Counter] = {k: Counter() for k in categories}

    for cell in df[annot_col].dropna().astype(str):
        cell = cell.strip()
        if not cell:
            continue
        try:
            data: Any = json.loads(cell)
        except Exception:
            try:
                data = ast.literal_eval(cell)
            except Exception:
                continue
        if not isinstance(data, dict):
            continue

        for key in categories:
            vals = data.get(key, [])
            if isinstance(vals, str):
                vals = [vals]
            elif not isinstance(vals, (list, tuple)):
                vals = [vals]
            cleaned = [_norm(v) for v in vals if str(v).strip() != ""]
            counters[key].update(cleaned)

    result: Dict[str, List[Tuple[str, int]]] = {}
    for key, ctr in counters.items():
        items = sorted(ctr.items(), key=lambda x: (-x[1], x[0]))[:n]
        result[key] = items
    return result


if __name__ == '__main__':


    # cnt = count_valid_privacy_policies("../datasets/out-tranco/policy_scrape_output.csv")
    # print(f"Tranco: {cnt}")
    #
    cnt = count_valid_privacy_policies("../datasets/out-Alexa/policy_scrape_output.csv")
    print(f"Alexa: {cnt}")

    counts = count_privacy_url_statuses("../datasets/out-Alexa/policy_scrape_output.csv")
    print(counts)

    result = count_links_for_successful_scrapes("../datasets/out-Alexa/policy_scrape_output.csv")
    print(result["num_successful_rows"], result["total_links"])
    # print(result["per_row_counts"].head())

    avg, per_row = average_links_for_successful_scrapes("../datasets/out-Alexa/policy_scrape_output.csv")
    print("Average links per successful row:", avg)

    stats = plot_policy_word_counts(
        "../datasets/out-Alexa/policy_scrape_output.csv",
        text_col="Policy Text",
        print_stats=True
    )
    print("Returned stats:", stats)

    n = count_need_review_with_valid_policy("../datasets/out-tranco/policy_scrape_output.csv")
    print("Needs review AND valid policy:", n)

    summary = summarize_policy_annotations("../datasets/out-Alexa/policy_annotated_output.csv")
    print("Policies:", summary["n_policies"])
    print("Totals:", summary["totals"])
    print("Unique counts:", summary["unique_counts"])
    print("Averages per policy:", summary["averages_per_policy"])

    top10 = top_annotation_values("../datasets/out-Alexa/policy_annotated_output.csv")
    for cat, items in top10.items():
        print(f"\nTop {len(items)} in '{cat}':")
        for val, cnt in items:
            print(f"  {val}: {cnt}")