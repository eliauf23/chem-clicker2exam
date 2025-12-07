import re
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional, Iterable
from pypdf import PdfReader, PdfWriter
from typing import List, Optional
import pdfplumber

from exam_bank.models import Question



# ---------- REGEXES ----------
# building blocks

TOPIC_STR = r"T([1-9]|1[0-8])"        # group(1): topic 13-18
QNUM_STR = r"Q([1-9][0-9]?)"          # group(2): questions 1-99 (adjust to 100 if you ever need)
LEVEL_STR = r"Level\s*([1-4])\+?"     # group(3): Level 1-4, optionally like "3+"
LG_STR = r"L\.G\.\s*(\d+)"            # group(4): one LG code, can be multi-digit (e.g. 11)

QUESTION_HEADER_RE = re.compile(
    rf"""^
        {TOPIC_STR}              # T13-T18       -> group(1)
        {QNUM_STR}               # Q1-Q99        -> group(2)
        \s*:\s*
        {LEVEL_STR}              # Level 1-4(+)  -> group(3)
        \s*\(
        {LG_STR}                 # L.G. n        -> group(4), multi-digit OK
        \)\s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

SOLUTION_HEADER_RE = re.compile(
    rf"""^
        {TOPIC_STR}
        (100|[1-9][0-9]?)        # question number for solutions, keep your 100 support here
        \s*:\s*Solution\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Challenge question: "8 pt challenge" or "8 pt Challenge again" (you can tweak if wording differs)
# solution is typically on the following slide

# TODO: check other slides to see if point is supported
CHALLENGE_HEADER_RE = re.compile(
    r"""\b8\s*pt\s*challenge\b""",
    re.IGNORECASE,
)


CHALLENGE_SOLUTION_HEADER_RE = re.compile(
    r"""^
        Q0[a-zA-Z]?              # Q0 or Q0b, Q0c, etc.
        \s*:\s*Solution\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

__all__ = [
    # building blocks
    "TOPIC_STR",
    "QNUM_STR",
    "LEVEL_STR",
    "LG_STR",

    # compiled regexes
    "QUESTION_HEADER_RE",
    "SOLUTION_HEADER_RE",
    "CHALLENGE_HEADER_RE",
    "CHALLENGE_SOLUTION_HEADER_RE",
]