import os
import json
import streamlit as st

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

SRC_PDF = "data/slides.pdf"
BANK_JSON = "output/question_bank.json"
TOPIC_LG_JSON = "config/topic_learning_goals.json"


# -------------------------------------------------
# Load topic → { "title": ..., "goals": {code: text} }
# -------------------------------------------------
def load_topic_learning_goals(path: str) -> dict[int, dict]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    # convert keys to int
    return {int(k): v for k, v in raw.items()}


# -------------------------------------------------
# Build question bank on first run
# -------------------------------------------------
def ensure_question_bank():
    os.makedirs("output", exist_ok=True)

    if not os.path.exists(BANK_JSON):
        st.info("Building question bank from slides…")
        entries = parse_pdf_to_entries(SRC_PDF)
        questions = build_question_bank(entries)
        save_question_bank_json(questions, BANK_JSON)
        st.success("Question bank built!")
    else:
        st.caption(f"Using existing question bank at {BANK_JSON}")


# -------------------------------------------------
# STREAMLIT APPLICATION
# -------------------------------------------------

st.set_page_config(page_title="Practice Exam Builder", layout="wide")

def main():
    st.title("CHE 166 Practice Exam Builder 🧪📘")
    st.subheader("Build Practice Exams From Clicker Questions")

    if not os.path.exists(SRC_PDF):
        st.error(f"Missing source PDF: {SRC_PDF}")
        return

    ensure_question_bank()

    questions = load_question_bank_json(BANK_JSON)
    topic_lg_map = load_topic_learning_goals(TOPIC_LG_JSON)

    # What topics exist in your PDF?
    all_topics_in_bank = sorted({q.topic for q in questions})

    st.sidebar.header("Filters")

    # --------------------------
    # Topic selection
    # --------------------------
    selected_topics = st.sidebar.multiselect(
        "Topics",
        options=all_topics_in_bank,
        default=all_topics_in_bank,
        format_func=lambda t: f"{t}: {topic_lg_map.get(t, {}).get('title', '')}"
    )

    # --------------------------
    # Dynamic learning goal list
    # --------------------------
    # Collect LG pairs for selected topics
    lg_pairs = []  # (code, text)

    if selected_topics:
        for topic in selected_topics:
            goal_dict = topic_lg_map.get(topic, {}).get("goals", {})
            for code, text in goal_dict.items():
                lg_pairs.append((code, text))
    else:
        # If no topics selected (unlikely) show all LGs
        for topic, data in topic_lg_map.items():
            for code, text in data["goals"].items():
                lg_pairs.append((code, text))

    # Deduplicate
    seen = set()
    unique_lg_pairs = []
    for code, text in lg_pairs:
        if code not in seen:
            seen.add(code)
            unique_lg_pairs.append((code, text))

    # Build nice labels
    lg_labels = [f"{code}: {text}" for code, text in unique_lg_pairs]
    label_to_code = {f"{code}: {text}": code for code, text in unique_lg_pairs}

    selected_lg_labels = st.sidebar.multiselect(
        "Learning Goals",
        options=lg_labels,
        default=lg_labels,
    )

    # Convert UI labels → LG codes
    selected_lg_codes = [label_to_code[label] for label in selected_lg_labels]

    # --------------------------
    # Levels (from question bank)
    # --------------------------
    all_levels = sorted({q.level for q in questions if q.level is not None})
    selected_levels = st.sidebar.multiselect(
        "Levels",
        options=all_levels,
        default=all_levels,
    )

    include_challenges = st.sidebar.checkbox("Include challenge questions (Q0)", value=True)

    base_name = st.text_input("Name your PDF set", value="practice")

    # -------------------------------------------------------
    # Generate PDFs when the user clicks
    # -------------------------------------------------------
    if st.button("Build PDFs"):
        selected = select_questions(
            questions,
            topics=selected_topics or None,
            include_challenges=include_challenges,
            levels=selected_levels or None,
            learning_goals=selected_lg_codes or None,
            require_question_page=True,
        )

        st.write(f"Selected **{len(selected)}** questions.")

        if not selected:
            st.warning("No questions match these filters.")
            return

        os.makedirs("output", exist_ok=True)
        q_path = f"output/{base_name}_questions.pdf"
        s_path = f"output/{base_name}_solutions.pdf"
        qa_path = f"output/{base_name}_q_and_a.pdf"

        # Build all three PDF types
        build_question_pdf(SRC_PDF, selected, q_path)
        build_solution_pdf(SRC_PDF, selected, s_path)
        build_interleaved_q_and_a_pdf(SRC_PDF, selected, qa_path)

        # Helper to load PDF bytes
        def load_bytes(path):
            with open(path, "rb") as f:
                return f.read()

        st.success("PDFs generated! Download below:")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button(
                "⬇️ Questions PDF",
                data=load_bytes(q_path),
                file_name=os.path.basename(q_path),
                mime="application/pdf",
            )
        with col2:
            st.download_button(
                "⬇️ Solutions PDF",
                data=load_bytes(s_path),
                file_name=os.path.basename(s_path),
                mime="application/pdf",
            )
        with col3:
            st.download_button(
                "⬇️ Q&A PDF",
                data=load_bytes(qa_path),
                file_name=os.path.basename(qa_path),
                mime="application/pdf",
            )


if __name__ == "__main__":
    main()
