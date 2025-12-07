from exam_bank.parsing import (
    parse_pdf_to_entries,
    build_question_bank,
    save_question_bank_json,
    load_question_bank_json,
)


from exam_bank.pdf_utils import (
    build_question_pdf,
    build_solution_pdf,
    build_interleaved_q_and_a_pdf,
    select_questions
)



def main():
    # Paths
    src_pdf_path = "data/slides.pdf"
    bank_json_path = "output/question_bank.json"

    # Step 1: parse the PDF and build/save question bank
    entries = parse_pdf_to_entries(src_pdf_path)
    print(f"Parsed {len(entries)} question/solution/challenge slides.")

    questions = build_question_bank(entries)
    print(f"Built question bank with {len(questions)} unique questions (including challenges).")

    save_question_bank_json(questions, bank_json_path)
    print(f"Saved question bank to {bank_json_path}")

    # Step 2: reload bank (mirrors real usage)
    questions = load_question_bank_json(bank_json_path)

    # Step 3: select questions for this practice set
    selected = select_questions(
        questions,
        topics=[13, 14, 15, 16, 17, 18],
        include_challenges=True,
        levels=None,            # or [1,2,3,4]
        learning_goals=None,    # or ["2", "7"]
        require_question_page=True,
    )

    print(f"Selected {len(selected)} questions for PDF output.")

    # Step 4: build PDFs
    build_question_pdf(src_pdf_path, selected, "output/practice_questions.pdf")
    build_solution_pdf(src_pdf_path, selected, "output/practice_solutions.pdf")
    build_interleaved_q_and_a_pdf(src_pdf_path, selected, "output/practice_q_and_a.pdf")

    print("Done building PDFs 🎉")


if __name__ == "__main__":
    main()
