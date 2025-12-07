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
    select_questions,  # assuming you export this from your package
)

SRC_PDF = "data/slides.pdf"
BANK_JSON = "output/question_bank.json"
TOPIC_LG_JSON = "config/topic_learning_goals.json"

# Configure page *before* other st.* calls
st.set_page_config(page_title="CHE 166 Practice Exam Builder", layout="wide")


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
def main():
    st.title("CHE 166 Practice Exam Builder 🧪📘")
    st.subheader("Build practice exams from in-class clicker questions")

    if not os.path.exists(SRC_PDF):
        st.error(f"Missing source PDF: {SRC_PDF}")
        return

    ensure_question_bank()

    questions = load_question_bank_json(BANK_JSON)
    topic_lg_map = load_topic_learning_goals(TOPIC_LG_JSON)

    # Topics actually present in the bank
    all_topics_in_bank = sorted({q.topic for q in questions})

    st.header("Filters")

    # --------------------------
    # Basic filters (always visible)
    # --------------------------

    st.markdown("### Topics")

    selected_topics = st.multiselect(
        "Choose topics",
        options=all_topics_in_bank,
        default=all_topics_in_bank,
        format_func=lambda t: f"{t}: {topic_lg_map.get(t, {}).get('title', '')}",
    )

    st.markdown("### Levels")

    all_levels = sorted({q.level for q in questions if q.level is not None})
    selected_levels = st.multiselect(
        "Choose difficulty levels",
        options=all_levels,
        default=all_levels,
    )

    include_challenges = st.checkbox("Include challenge questions (Q0)", value=True)

    # --------------------------
    # Advanced Mode toggle
    # --------------------------

    advanced_mode = st.checkbox("Advanced filters (learning goals)", value=False)

    # --------------------------
    # Learning Goals (only shown in advanced mode)
    # --------------------------

    if advanced_mode:
        st.markdown("### Learning Goals (filtered by topic)")

        # Build list of (topic, code, text)
        lg_triplets: list[tuple[int, str, str]] = []

        if selected_topics:
            for topic in selected_topics:
                goal_dict = topic_lg_map.get(topic, {}).get("goals", {})
                for code, text in goal_dict.items():
                    lg_triplets.append((topic, code, text))
        else:
            # If no topics somehow selected, show all LGs
            for topic, data in topic_lg_map.items():
                for code, text in data["goals"].items():
                    lg_triplets.append((topic, code, text))

        # Dedupe
        seen = set()
        unique_lg_triplets = []
        for topic, code, text in lg_triplets:
            key = (topic, code)
            if key not in seen:
                seen.add(key)
                unique_lg_triplets.append((topic, code, text))

        # Labels like: "T14 · LG 3: Compute theoretical yield"
        lg_labels = []
        label_to_code = {}
        for topic, code, text in unique_lg_triplets:
            label = f"T{topic} · LG {code}: {text}"
            lg_labels.append(label)
            label_to_code[label] = code

        selected_lg_labels = st.multiselect(
            "Choose learning goals",
            options=lg_labels,
            default=lg_labels,
        )

        st.markdown("**Selected Learning Goals:**")
        for label in selected_lg_labels:
            st.markdown(f"- {label}")

        selected_lg_codes = [label_to_code[label] for label in selected_lg_labels]

    else:
        # No LG filtering
        selected_lg_codes = None

    # -------------------------------------------------------
    # Name + Build PDFs
    # -------------------------------------------------------
    base_name = st.text_input("Name your PDF set", value="practice")

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
        def load_bytes(path: str) -> bytes:
            with open(path, "rb") as f:
                return f.read()

        st.success("PDFs generated! Download below:")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button(
                "⬇️ Questions PDF",
                data=load_bytes(q_path),
                file_name=os.path.basename(q_path),
                mime="application/pdf",
            )
        with c2:
            st.download_button(
                "⬇️ Solutions PDF",
                data=load_bytes(s_path),
                file_name=os.path.basename(s_path),
                mime="application/pdf",
            )
        with c3:
            st.download_button(
                "⬇️ Q&A PDF",
                data=load_bytes(qa_path),
                file_name=os.path.basename(qa_path),
                mime="application/pdf",
            )


if __name__ == "__main__":
    main()
