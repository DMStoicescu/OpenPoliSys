#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import ast
from datetime import datetime, timedelta
import re

# ─── CONFIGURATION ─────────────────────────────────────────────────────────────
INPUT_CSV        = "../hist-out-good/scrapes/policy_scrape_output-GOOD3.csv"
# INPUT_CSV        = "../datasets/out-Alexa/policy_scrape_output.csv"
SCRAPER_LOG      = "../hist-out-good/logs/scraper-GOOD3.log"
# SCRAPER_LOG      = "../datasets/out-Alexa/scraper.log"
VALIDATION_CSV   = "../datasets/performance_analysis_dataset.csv"
TS_FORMAT        = "%Y-%m-%d %H:%M:%S,%f"
# ───────────────────────────────────────────────────────────────────────────────

def parse_first_last_timestamps(log_path: str):
    """
    Parse the first and last non-blank timestamps from the log.
    """
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line for line in f if line.strip()]
    if not lines:
        raise RuntimeError("Log file is empty")
    first_ts = datetime.strptime(lines[0][:23], TS_FORMAT)
    last_ts  = datetime.strptime(lines[-1][:23], TS_FORMAT)
    return first_ts, last_ts


def format_timedelta(td: timedelta) -> str:
    """
    Convert a timedelta to a human-readable Hh Mm Ss string.
    """
    total_seconds = int(td.total_seconds())
    hrs, rem = divmod(total_seconds, 3600)
    mins, secs = divmod(rem, 60)
    return f"{hrs}h {mins}m {secs}s"


def compute_run_times():
    """
    Compute and print total scraping duration and average per entry.
    """
    start_ts, end_ts = parse_first_last_timestamps(SCRAPER_LOG)
    total = end_ts - start_ts
    print(f"Scrape started at:  {start_ts}")
    print(f"Scrape finished at: {end_ts}")
    print(f"Total run time:     {format_timedelta(total)}")

    df = pd.read_csv(INPUT_CSV)
    n_entries = len(df)
    if n_entries == 0:
        print("Warning: input CSV has no rows.")
        return

    avg_seconds = total.total_seconds() / n_entries
    avg_td = timedelta(seconds=avg_seconds)
    print(f"Entries processed:  {n_entries}")
    print(f"Average per entry:  {format_timedelta(avg_td)} (~{avg_seconds:.2f}s)")


def analyze_policies():
    """
    Compute and display policy text statistics and distributions.
    """
    df = pd.read_csv(INPUT_CSV)
    print(f"Total policies before filter: {len(df)}")
    df = df[df["Policy Text"] != "No privacy url found"].copy()
    print(f"Policies with valid text:     {len(df)}")

    df["char_count"] = df["Policy Text"].str.len()
    df["word_count"] = df["Policy Text"].str.split().str.len()

    print(f"Average characters per policy: {df['char_count'].mean():.1f}")
    print(f"Average words      per policy: {df['word_count'].mean():.1f}")
    print(f"Min characters per policy:     {df['char_count'].min()}")
    print(f"Min words      per policy:     {df['word_count'].min()}")
    print(f"Max characters per policy:     {df['char_count'].max()}")
    print(f"Max words      per policy:     {df['word_count'].max()}")

    fig, axes = plt.subplots(ncols=2, figsize=(12, 5))
    axes[0].hist(df["char_count"], bins=30, edgecolor="black")
    axes[0].set_title("Character Count Distribution")
    axes[0].set_xlabel("Characters")
    axes[0].set_ylabel("Frequency")

    axes[1].hist(df["word_count"], bins=30, edgecolor="black")
    axes[1].set_title("Word Count Distribution")
    axes[1].set_xlabel("Words")
    axes[1].set_ylabel("Frequency")

    plt.tight_layout()
    plt.show()


def compute_validation_accuracy():
    """
    Compare scraped vs manual links, report accuracy and list mismatches.
    """
    # Load data
    df_scrape = pd.read_csv(INPUT_CSV, dtype=str)
    df_valid  = pd.read_csv(VALIDATION_CSV, dtype=str)

    # Merge on domain
    merged = pd.merge(
        df_valid[["Input Domain", "Privacy Policy Validated URL"]],
        df_scrape[["Input Domain", "Privacy Policy URL"]],
        on="Input Domain", how="left"
    ).rename(columns={
        "Privacy Policy Validated URL": "manual_link",
        "Privacy Policy URL":    "scraped_link",
    })

    # Normalize manual link
    merged["manual_clean"] = merged["manual_link"].str.split("?", n=1).str[0]
    merged["manual_norm"]  = (
        merged["manual_clean"]
            .str.lower()
            .str.replace(r"^https?://(www\.)?", "", regex=True)
            .str.rstrip("/")
    )

    # Normalize scraped links
    scraped_norms = []
    for val in merged["scraped_link"]:
        # parse list literal or single string
        if isinstance(val, str) and val.startswith("["):
            try:
                lst = ast.literal_eval(val)
            except Exception:
                lst = []
        else:
            lst = [val] if isinstance(val, str) else []
        # clean each URL
        clean_list = []
        for u in lst:
            u0 = u.split("?", 1)[0].lower()
            u0 = re.sub(r"^https?://(www\.)?", "", u0)
            u0 = u0.rstrip("/")
            clean_list.append(u0)
        scraped_norms.append(clean_list)
    merged["scraped_norms"] = scraped_norms

    # Exclude outdated/N/A cases
    ignore_mask = (
            merged["manual_clean"].isin(["OUTDATED DOMAIN", "N/A not in English"])  # manual flags
            | merged["scraped_link"].str.contains(
        r"domain not in english|timed out", case=False, na=False
    )  # scraper flags
    )
    total    = len(merged)
    ignored  = ignore_mask.sum()

    # Evaluate remaining
    eval_df       = merged.loc[~ignore_mask].copy()
    eval_df["match"] = [m in s for m, s in zip(eval_df["manual_norm"], eval_df["scraped_norms"])]
    evaluated     = len(eval_df)
    correct       = int(eval_df["match"].sum())
    accuracy      = correct / evaluated if evaluated else 0.0

    # Print summary
    print(f"Total entries in validation set: {total}")
    print(f"Ignored (outdated/N/A):           {ignored}")
    print(f"Entries evaluated:                {evaluated}")
    print(f"Correct matches:                  {correct}")
    print(f"Accuracy:                         {accuracy:.2%}")

    # Print mismatches
    mismatches = eval_df.loc[~eval_df["match"]]
    if not mismatches.empty:
        print("Mismatched entries:")
        for _, row in mismatches.iterrows():
            print(
                f"{row['Input Domain']:30}  "
                f"manual={row['manual_norm']:40}  "
                f"scraped={row['scraped_norms']}"
            )

def evaluate_non_english_detection():
    """
    Reports precision/recall of non‑English detection,
    and lists false negatives (missed non‑English) excluding timeouts.
    """
    df_scrape = pd.read_csv(INPUT_CSV, dtype=str)
    df_valid  = pd.read_csv(VALIDATION_CSV, dtype=str)
    merged = pd.merge(
        df_valid[["Input Domain", "Privacy Policy Validated URL"]],
        df_scrape[["Input Domain", "Privacy Policy URL"]],
        on="Input Domain", how="left"
    ).rename(columns={
        "Privacy Policy Validated URL": "manual_link",
        "Privacy Policy URL":    "scraped_link",
    })

    # ground truth
    manual_na = merged["manual_link"].str.split("?", n=1).str[0] == "N/A not in English"
    # scraper flags
    scraper_na      = merged["scraped_link"].str.contains(r"domain not in english", case=False, na=False)
    scraper_timeout = merged["scraped_link"].str.contains(r"timed out",               case=False, na=False)

    total_flagged = scraper_na.sum()
    true_noneng   = (scraper_na & manual_na).sum()
    total_true    = manual_na.sum()

    print(f"Scraper flagged {total_flagged} domains as non-English.")
    if total_flagged:
        print(f"  Precision: {true_noneng/total_flagged:.1%} ({true_noneng}/{total_flagged})")
    print(f"True non-English domains: {total_true}")
    if total_true:
        print(f"  Recall:    {true_noneng/total_true:.1%} ({true_noneng}/{total_true})")

    # — False negatives ——————————————————————————————————————————————
    # those truly non‑English but not flagged, excluding timeouts
    fn = merged[manual_na & ~scraper_na & ~scraper_timeout]
    if not fn.empty:
        print("\nFalse negatives (missed non-English, excluding timeouts):")
        for _, row in fn.iterrows():
            print(f"- {row['Input Domain']}")
    else:
        print("\nNo false negatives (outside timeouts).")

def compute_avg_links_per_domain():
    """
    Compute the average number of privacy‑policy links returned per domain,
    excluding domains flagged as OUTDATED, timed out, or non‑English.
    """
    # 1) Load just the scraped output
    df = pd.read_csv(INPUT_CSV, dtype=str)

    # 2) Build an exclude mask on the raw 'Privacy Policy URL' field
    bad = df["Privacy Policy URL"].str.contains(
        r"OUTDATED DOMAIN|DOMAIN NOT IN ENGLISH|DOMAIN TIMED OUT",
        case=False,
        na=False
    )
    good = df.loc[~bad, "Privacy Policy URL"]

    # 3) Count links per entry
    def count_links(cell):
        if not isinstance(cell, str):
            return 0
        s = cell.strip()
        # list literal?
        if s.startswith("[") and s.endswith("]"):
            try:
                lst = ast.literal_eval(s)
                return len(lst)
            except Exception:
                return 1
        # plain single URL
        return 1

    counts = good.apply(count_links)

    # 4) Compute & print average
    avg = counts.mean() if not counts.empty else 0.0
    print(f"Average links scraped per domain: {avg:.2f}")


if __name__ == "__main__":
    print("--- SCRAPE TIMING ---")
    compute_run_times()
    print("\n --- POLICY ANALYSIS ---")
    analyze_policies()
    print("\n --- VALIDATION ACCURACY ---")
    compute_validation_accuracy()
    print("\n--- NON-ENGLISH DETECTION ---")
    evaluate_non_english_detection()
    print("\n--- AVG LINKS PER DOMAIN ---")
    compute_avg_links_per_domain()
