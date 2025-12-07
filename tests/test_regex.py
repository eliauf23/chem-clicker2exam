import re
from exam_bank.regexes import (
    LEVEL_STR,
    LG_STR,
    QUESTION_HEADER_RE,
    SOLUTION_HEADER_RE,
    CHALLENGE_HEADER_RE,
    CHALLENGE_SOLUTION_HEADER_RE,
)

def test_level_re():
    m = re.search(LEVEL_STR, "Level 3+ (L.G. 11)")
    assert m
    assert m.group(1) == "3"

    m2 = re.search(LEVEL_STR, "Level 2")
    assert m2 and m2.group(1) == "2"


def test_lg_re():
    m = re.search(LG_STR, "L.G. 11)")
    assert m and m.group(1) == "11"

    m2 = re.search(LG_STR, "L.G. 4)")
    assert m2 and m2.group(1) == "4"


def test_question_header_re():
    header = "T13Q7: Level 3+ (L.G. 11)"
    m = QUESTION_HEADER_RE.match(header)
    assert m
    assert m.group(1) == "13"
    assert m.group(2) == "7"
    assert m.group(3) == "3"
    assert m.group(4) == "11"

# TODO: main block to run tests!
