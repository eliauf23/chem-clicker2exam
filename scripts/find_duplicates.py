#!/usr/bin/env python
import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_summary(summary_path: str) -> dict:
    with open(summary_path, "r", encoding="utf-8") as f:
        return json.load(f)


def analyze_duplicates(summary: dict):
    """
    summary["page_usage"] looks like:
      {
        "12": ["T5-Q3-C0:Q", "T5-Q3-C0:S"],
        "13": ["T5-Q4-C0:Q"],
        ...
      }

    We treat the base ID "T5-Q3-C0" as the question identity and
    consider it a duplicate if it appears on >1 distinct *question* page.
    """

    raw_page_usage = summary.get("page_usage", {})

    # normalize keys to ints
    page_usage = {int(k): v for k, v in raw_page_usage.items()}

    # base_id -> set(question_pages), set(solution_pages)
    q_pages_map = defaultdict(set)
    s_pages_map = defaultdict(set)

    for page, entries in page_usage.items():
        for entry in entries:
            # entry is like "T5-Q12-C0:Q" or "T5-Q12-C0:S"
            if ":" in entry:
                base_id, kind = entry.split(":", 1)
            else:
                base_id, kind = entry, "?"

            if kind == "Q":
                q_pages_map[base_id].add(page)
            elif kind == "S":
                s_pages_map[base_id].add(page)
            else:
                # unknown kind, just ignore or track if you want
                pass

    all_ids = set(q_pages_map.keys()) | set(s_pages_map.keys())

    # Duplicate definition: appears on more than one distinct question page
    duplicates = {
        base_id
        for base_id, pages in q_pages_map.items()
        if len(pages) > 1
    }

    return {
        "all_ids": all_ids,
        "q_pages_map": q_pages_map,
        "s_pages_map": s_pages_map,
        "duplicates": duplicates,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Analyze duplicate questions using allclickerslides_summary.json"
    )
    parser.add_argument(
        "summary_json",
        help="Path to allclickerslides_summary.json",
    )
    args = parser.parse_args()

    summary = load_summary(args.summary_json)
    result = analyze_duplicates(summary)

    all_ids = result["all_ids"]
    q_pages_map = result["q_pages_map"]
    s_pages_map = result["s_pages_map"]
    duplicates = result["duplicates"]

    print(f"Summary file: {Path(args.summary_json).name}")
    print(f"Total unique question IDs (T*-Q*-C*): {len(all_ids)}")
    print(f"Question IDs with duplicates (Q appears on >1 page): {len(duplicates)}")

    if not duplicates:
        print("\nNo duplicate question IDs found 🎉")
        return

    print("\n=== Duplicated Question IDs ===")
    for base_id in sorted(duplicates):
        q_pages = sorted(q_pages_map.get(base_id, []))
        s_pages = sorted(s_pages_map.get(base_id, []))
        print(f"\n• {base_id}")
        print(f"  Question pages : {q_pages}")
        if s_pages:
            print(f"  Solution pages : {s_pages}")


if __name__ == "__main__":
    main()
