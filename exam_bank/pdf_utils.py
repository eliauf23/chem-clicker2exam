from typing import List
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

def select_questions(
    questions: Iterable[Question],
    topics: Optional[List[int]] = None,
    include_challenges: bool = True,
    levels: Optional[List[int]] = None,
    learning_goals: Optional[List[str]] = None,
    require_question_page: bool = False,
) -> List[Question]:
    """
    Generic filter over the question bank.

    - topics: only keep questions whose topic is in this list (if provided)
    - include_challenges: keep or drop challenge questions (qnum == 0)
    - levels: only keep questions whose level is in this list (if provided)
    - learning_goals: only keep questions that have at least one LG in this list
    - require_question_page: if True, drop questions with no question_page
      (useful when preparing PDFs)
    """
    result: List[Question] = []

    for q in questions:
        # topic filter
        if topics is not None and q.topic not in topics:
            continue

        # challenge filter
        if not include_challenges and q.is_challenge:
            continue

        # level filter
        if levels is not None:
            if q.level is None or q.level not in levels:
                continue

        # LG filter: require at least one overlap with requested LGs
        if learning_goals is not None:
            if not q.learning_goals:
                continue
            if not any(lg in q.learning_goals for lg in learning_goals):
                continue

        # PDF-related filter
        if require_question_page and q.question_page is None:
            continue

        result.append(q)

    # Sort however you like
    result.sort(key=lambda qq: (qq.topic, qq.is_challenge, qq.qnum))
    return result

