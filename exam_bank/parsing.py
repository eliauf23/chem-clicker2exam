import re
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional, Iterable
from pypdf import PdfReader, PdfWriter
from typing import List, Optional
import pdfplumber

from exam_bank.models import Question



# ---------- REGEXES ----------

# Regular questions: T13–18Q1–100
# QUESTION_HEADER_RE = re.compile(
#     r"""^
#         T(1[3-8])             # topic 13-18  -> group(1)
#         Q(100|[1-9][0-9]?)    # question 1-100 -> group(2)
#         \b
#     """,
#     re.IGNORECASE | re.VERBOSE,
# )
QUESTION_HEADER_RE = re.compile(
    r"""^
        T(1[3-8])                 # topic 13-18           -> group(1)
        Q(100|[1-9][0-9]?)        # question 1-100        -> group(2)
        \s*:\s*
        Level\s*([1-4])           # Level 1-4             -> group(3)
        \s*\(
        L\.G\.\s*([^)]+)          # everything inside (...) -> group(4)
        \)\s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Regular solutions: T13–18Q1–100: Solution
SOLUTION_HEADER_RE = re.compile(
    r"""^
        T(1[3-8])
        Q(100|[1-9][0-9]?)
        \s*:\s*Solution\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Challenge question: "8 pt challenge" (you can tweak if wording differs)
CHALLENGE_HEADER_RE = re.compile(
    r"""\b8\s*pt\s*challenge\b""",
    re.IGNORECASE,
)

# Challenge solution: "Q0: Solution"
CHALLENGE_SOLUTION_HEADER_RE = re.compile(
    r"""^Q0\s*:\s*Solution\b""",
    re.IGNORECASE,
)




# ---------- PARSING ----------

def parse_pdf_to_entries(pdf_path: str):
    entries = []
    current_topic: Optional[int] = None

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            lines = text.splitlines()
            if not lines:
                continue

            header = lines[0].strip()
            body = "\n".join(lines[1:]).strip()

            # ---- Regular question ----
            q_match = QUESTION_HEADER_RE.search(header)
            if q_match:
                topic = int(q_match.group(1))
                qnum = int(q_match.group(2))
                level = int(q_match.group(3))
                raw_lg = q_match.group(4).strip()
                # split LG string on commas/ampersands/etc.
                lg_list = [p.strip() for p in re.split(r"[,&/]", raw_lg) if p.strip()]

                current_topic = topic

                entries.append({
                    "kind": "question",
                    "topic": topic,
                    "qnum": qnum,
                    "level": level,
                    "learning_goals": lg_list,
                    "text": body,
                    "page": page_index,
                })
                continue

            # ---- Regular solution ----
            s_match = SOLUTION_HEADER_RE.search(header)
            if s_match:
                topic = int(s_match.group(1))
                qnum = int(s_match.group(2))
                current_topic = topic

                entries.append({
                    "kind": "solution",
                    "topic": topic,
                    "qnum": qnum,
                    "text": body,
                    "page": page_index,
                })
                continue

            # ---- Challenge question ----
            ch_match = CHALLENGE_HEADER_RE.search(header)
            if ch_match and current_topic is not None:
                entries.append({
                    "kind": "challenge_q",
                    "topic": current_topic,
                    "qnum": 0,
                    "text": body,
                    "page": page_index,
                })
                continue

            # ---- Challenge solution ----
            chs_match = CHALLENGE_SOLUTION_HEADER_RE.search(header)
            if chs_match and current_topic is not None:
                entries.append({
                    "kind": "challenge_sol",
                    "topic": current_topic,
                    "qnum": 0,
                    "text": body,
                    "page": page_index,
                })
                continue

    return entries

def build_question_bank(entries) -> List[Question]:
    bank: Dict[tuple[int, int], Question] = {}

    for e in entries:
        key = (e["topic"], e["qnum"])
        kind = e["kind"]

        if key not in bank:
            bank[key] = Question(
                topic=e["topic"],
                qnum=e["qnum"],
                is_challenge=(kind in {"challenge_q", "challenge_sol"}),
                question_text="",
            )

        q_obj = bank[key]

        # if we see a challenge entry, mark it
        if kind in {"challenge_q", "challenge_sol"}:
            q_obj.is_challenge = True

        if kind == "question":
            q_obj.question_text = e["text"]
            q_obj.question_page = e["page"]
            q_obj.level = e.get("level")
            q_obj.learning_goals = e.get("learning_goals")

        elif kind == "solution":
            q_obj.solution_text = e["text"]
            q_obj.solution_page = e["page"]

        elif kind == "challenge_q":
            q_obj.question_text = e["text"]
            q_obj.question_page = e["page"]

        elif kind == "challenge_sol":
            q_obj.solution_text = e["text"]
            q_obj.solution_page = e["page"]

    return list(bank.values())


def save_question_bank_json(questions: List[Question], output_path: str):
    data = [asdict(q) for q in questions]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_question_bank_json(path: str) -> List[Question]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Question(**q) for q in data]
