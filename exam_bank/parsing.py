import re
import json
from dataclasses import asdict
from typing import List, Dict, Optional
from typing import List, Optional
import pdfplumber

from exam_bank.models import Question
from exam_bank.regexes import (
    QUESTION_HEADER_RE,
    SOLUTION_HEADER_RE,
    CHALLENGE_HEADER_RE,
    CHALLENGE_SOLUTION_HEADER_RE,
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
