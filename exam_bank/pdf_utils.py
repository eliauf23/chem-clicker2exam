from typing import Iterable, List, Optional
from pypdf import PdfReader, PdfWriter

from exam_bank.models import Question

def build_question_pdf(
    src_pdf_path: str,
    questions: List[Question],
    output_pdf_path: str,
):
    """PDF with only question slides, in given order."""
    reader = PdfReader(src_pdf_path)
    writer = PdfWriter()

    for q in questions:
        page_index = q.question_page - 1  # pypdf is 0-based
        writer.add_page(reader.pages[page_index])

    with open(output_pdf_path, "wb") as f:
        writer.write(f)

    print(f"Wrote questions PDF to {output_pdf_path}")


def build_solution_pdf(
    src_pdf_path: str,
    questions: List[Question],
    output_pdf_path: str,
):
    """PDF with only solution slides (for the same questions)."""
    reader = PdfReader(src_pdf_path)
    writer = PdfWriter()

    for q in questions:
        if q.solution_page is None:
            continue
        page_index = q.solution_page - 1
        writer.add_page(reader.pages[page_index])

    with open(output_pdf_path, "wb") as f:
        writer.write(f)

    print(f"Wrote solutions PDF to {output_pdf_path}")


def build_interleaved_q_and_a_pdf(
    src_pdf_path: str,
    questions: List[Question],
    output_pdf_path: str,
):
    """
    PDF where each question slide is followed immediately by its solution slide.
    If a solution is missing, you just get the question.
    """
    reader = PdfReader(src_pdf_path)
    writer = PdfWriter()

    for q in questions:
        if q.question_page is not None:
            writer.add_page(reader.pages[q.question_page - 1])
        if q.solution_page is not None:
            writer.add_page(reader.pages[q.solution_page - 1])

    with open(output_pdf_path, "wb") as f:
        writer.write(f)

    print(f"Wrote interleaved Q&A PDF to {output_pdf_path}")


# def select_questions(
#     questions: Iterable["Question"],
#     topics: Optional[list[int]] = None,
#     include_challenges: bool = True,
#     levels: Optional[list[int]] = None,
#     learning_goals: Optional[list[str]] = None,
#     require_question_page: bool = True,
#     require_solution_page: bool = True,
# ) -> List["Question"]:
#     """
#     Filter questions by topic, challenge flag, level, and learning goals.

#     - Challenge questions (q.is_challenge == True):
#         * If include_challenges=False -> drop all of them.
#         * If include_challenges=True -> they are included or excluded
#           based on levels / learning_goals, but NOT topic filters.

#     - Non-challenge questions:
#         * Obey topic filters, level filters, and learning goal filters.

#     - require_question_page=True drops any question without a mapped question slide.
#     """

#     result: List["Question"] = []

#     for q in questions:
#         is_challenge = getattr(q, "is_challenge", False)
#         q_topic = getattr(q, "topic", None)

#         # --- Challenge vs non-challenge ---

#         if is_challenge:
#             # Only controlled by the include_challenges flag
#             if not include_challenges:
#                 continue
#             # IMPORTANT: do NOT apply topic filter to challenge questions
#         else:
#             # Non-challenge: obey topic filters if provided
#             if topics is not None and q_topic not in topics:
#                 continue

#         # --- Level filter ---
#         if levels is not None and not is_challenge:
#             q_level = getattr(q, "level", None)
#             if q_level is None or q_level not in levels:
#                 continue

#         # --- Learning goals filter (any overlap) ---
#         if learning_goals is not None and not is_challenge:
#             q_lgs = getattr(q, "learning_goals", []) or []
#             if not any(lg in q_lgs for lg in learning_goals):
#                 continue

#         # --- Require mapped question page ---
#         if require_question_page and getattr(q, "question_page", None) is None:
#             continue

#         if require_solution_page and getattr(q, "solution_page", None) is None:
#             continue

#         result.append(q)

#     # Sort however you like; keep challenges at the end of their topic group
#     def sort_key(qq: "Question"):
#         topic_val = getattr(qq, "topic", None)
#         # Put None-topic last
#         topic_sort = topic_val if topic_val is not None else 999
#         return (topic_sort, int(bool(getattr(qq, "is_challenge", False))), qq.qnum)

#     result.sort(key=sort_key)
#     return result


def select_questions(
    questions: Iterable["Question"],
    topics: Optional[list[int]] = None,
    include_challenges: bool = True,
    levels: Optional[list[int]] = None,
    learning_goals: Optional[list[str]] = None,
    require_question_page: bool = True,
    require_solution_page: bool = True,
) -> List["Question"]:
    """
    Filter questions by topic, challenge flag, level, and learning goals.

    - All questions (challenge or not) obey the topic filter if provided.
    - Challenge questions:
        * Included only if include_challenges is True.
        * Do NOT use the level filter (they usually have no level).
    - Non-challenge questions:
        * Obey both topic and level filters.
    - Learning goals (if provided) apply to both.
    """

    result: List["Question"] = []

    for q in questions:
        is_challenge = getattr(q, "is_challenge", False)
        q_topic = getattr(q, "topic", None)

        # --- Challenge toggle ---
        if is_challenge and not include_challenges:
            continue

        # --- Topic filter (applies to ALL questions now) ---
        if topics is not None and q_topic not in topics:
            continue

        # --- Level filter (only for non-challenges) ---
        if levels is not None and not is_challenge:
            q_level = getattr(q, "level", None)
            if q_level is None or q_level not in levels:
                continue

        # --- Learning goals filter (any overlap) ---
        if learning_goals is not None:
            q_lgs = getattr(q, "learning_goals", []) or []
            if not any(lg in q_lgs for lg in learning_goals):
                continue

        # --- Require mapped pages ---
        if require_question_page and getattr(q, "question_page", None) is None:
            continue

        if require_solution_page and getattr(q, "solution_page", None) is None:
            continue

        result.append(q)

    # Sort reasonably: by topic, then normal before challenge, then Q number
    def sort_key(qq: "Question"):
        topic_val = getattr(qq, "topic", None)
        topic_sort = topic_val if topic_val is not None else 999
        return (topic_sort, int(bool(getattr(qq, "is_challenge", False))), qq.qnum)

    result.sort(key=sort_key)
    return result
