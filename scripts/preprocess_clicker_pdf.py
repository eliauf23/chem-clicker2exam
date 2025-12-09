import argparse
import json
from collections import defaultdict
from pathlib import Path

import pdfplumber
from pypdf import PdfReader, PdfWriter

from exam_bank.parsing import parse_pdf_to_entries, build_question_bank
from exam_bank.models import Question


# ------------ Helpers ------------

def question_id(q: Question) -> str:
    """Stable key for deduping questions."""
    return f"T{q.topic}-Q{q.qnum}-C{int(bool(q.is_challenge))}"


def build_question_bank_dedup(entries):
    """
    Wrap your existing build_question_bank, but ensure we dedupe
    by (topic, qnum, is_challenge) and keep the *last occurrence*
    (which is what your current logic effectively does).
    """
    questions = build_question_bank(entries)

    by_id: dict[str, Question] = {}
    for q in questions:
        by_id[question_id(q)] = q  # last one wins

    return list(by_id.values())


def compute_used_pages(questions: list[Question]) -> dict[int, list[str]]:
    """
    Return mapping page_index -> [question_ids_that_use_it]
    Page indices are 1-based (same as pdfplumber / your parser).
    """
    page_to_qids: dict[int, list[str]] = defaultdict(list)

    for q in questions:
        qid = question_id(q)

        if getattr(q, "question_page", None) is not None:
            page_to_qids[q.question_page].append(f"{qid}:Q")

        if getattr(q, "solution_page", None) is not None:
            page_to_qids[q.solution_page].append(f"{qid}:S")

    return page_to_qids


def write_filtered_pdf(input_pdf: str, output_pdf: str, pages_to_keep_sorted: list[int]):
    """
    Create a new PDF with only the given 1-based page numbers, in order.
    """
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    for p in pages_to_keep_sorted:
        # p is 1-based; PdfReader is 0-based
        writer.add_page(reader.pages[p - 1])

    out_path = Path(output_pdf)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("wb") as f:
        writer.write(f)


def summarize(
    input_pdf: str,
    output_pdf: str,
    page_to_qids: dict[int, list[str]],
    total_pages: int,
):
    kept_pages = sorted(page_to_qids.keys())
    kept_set = set(kept_pages)
    removed_pages = [p for p in range(1, total_pages + 1) if p not in kept_set]

    summary = {
        "input_pdf": str(input_pdf),
        "output_pdf": str(output_pdf),
        "total_pages": total_pages,
        "num_kept_pages": len(kept_pages),
        "num_removed_pages": len(removed_pages),
        "kept_pages": kept_pages,
        "removed_pages": removed_pages,
        "page_usage": page_to_qids,  # page -> [question_ids]
    }

    return summary


# ------------ Main CLI ------------

def main():
    parser = argparse.ArgumentParser(
        description="Pre-process a clicker PDF to keep only question/solution slides "
                    "and dedupe by (topic, qnum, challenge)."
    )
    parser.add_argument("input_pdf", help="Path to source PDF (raw clicker slides)")
    parser.add_argument(
        "-o",
        "--output",
        dest="output_pdf",
        help="Path to filtered PDF (default: <input>_filtered.pdf)",
    )
    parser.add_argument(
        "--summary-json",
        dest="summary_json",
        help="Optional path to write JSON summary of kept/removed slides",
    )

    args = parser.parse_args()

    input_pdf = args.input_pdf
    if args.output_pdf:
        output_pdf = args.output_pdf
    else:
        p = Path(input_pdf)
        output_pdf = str(p.with_name(p.stem + "_filtered" + p.suffix))

    # 1) Parse entries with existing logic
    print(f"Parsing PDF: {input_pdf}")
    entries = parse_pdf_to_entries(input_pdf)
    print(f"Found {len(entries)} entries (questions/solutions/challenge variants).")

    # 2) Build question bank + dedupe by (topic, qnum, is_challenge)
    questions = build_question_bank_dedup(entries)
    print(f"Built question bank with {len(questions)} unique questions.")

    # 3) Compute used pages
    page_to_qids = compute_used_pages(questions)

    # 4) Count total pages in the original PDF
    with pdfplumber.open(input_pdf) as pdf:
        total_pages = len(pdf.pages)

    # 5) Summary + print to stdout
    summary = summarize(
        input_pdf=input_pdf,
        output_pdf=output_pdf,
        page_to_qids=page_to_qids,
        total_pages=total_pages,
    )

    print("\n=== Summary ===")
    print(f"Total pages      : {summary['total_pages']}")
    print(f"Pages kept       : {summary['num_kept_pages']}")
    print(f"Pages removed    : {summary['num_removed_pages']}")
    print(f"Kept page numbers: {summary['kept_pages']}")
    print(f"Removed pages    : {summary['removed_pages']}")

    # Optional: show brief mapping of page -> question ids
    print("\nPage usage (page -> question IDs):")
    for p in sorted(page_to_qids.keys()):
        print(f"  Page {p}: {', '.join(page_to_qids[p])}")

    # 6) Write filtered PDF (only pages with questions/solutions)
    kept_pages_sorted = sorted(page_to_qids.keys())
    if not kept_pages_sorted:
        print("\nWARNING: No pages found with questions or solutions. "
              "No filtered PDF written.")
        return

    print(f"\nWriting filtered PDF to: {output_pdf}")
    write_filtered_pdf(input_pdf, output_pdf, kept_pages_sorted)

    # 7) Optional JSON summary
    if args.summary_json:
        json_path = Path(args.summary_json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"Wrote summary JSON to: {json_path}")


if __name__ == "__main__":
    main()
