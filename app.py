import os
import json
import random
from collections import defaultdict
from typing import Iterable, Set, Tuple, List
import streamlit as st
import tempfile 


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
    select_questions,  # your existing filter helper
)

SRC_PDF = "data/allclickerslides.pdf"
BANK_JSON = "output/question_bank.json"
TOPIC_LG_JSON = "config/topic_learning_goals.json"

# Configure page *before* other st.* calls
st.set_page_config(page_title="CHE 166 Practice Exam Builder", layout="wide")


# TODO: make this part of the question class!
def question_id(q) -> str:
    """A stable ID for a question so we can track if it's been used."""
    return f"T{q.topic}-Q{q.qnum}-C{int(bool(q.is_challenge))}"


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


def build_suggested_name(
    topics: list[int],
    levels: list[int] | None,
    learning_goals: list[str] | None,
    num_questions: int,
    use_all_matching: bool,
    preset_label: str | None = None,  # NEW
) -> str:
    """Build a filename string summarizing filters."""
    parts = ["practice_questions"]

    # Include exam preset if provided
    if preset_label:
        safe_preset = preset_label.lower().replace(" ", "")
        parts.append(safe_preset)  # e.g., exam1

    # Topics (still included for custom or explicit clarity)
    if topics and not preset_label:
        topic_part = "T" + "-".join(str(t) for t in sorted(topics))
        parts.append(topic_part)

    # Levels
    if levels:
        lvl_part = "L" + "-".join(str(l) for l in sorted(levels))
        parts.append(lvl_part)

    # Learning goals
    if learning_goals:
        lg_part = "LG" + "-".join(str(lg) for lg in learning_goals)
        parts.append(lg_part)

    # Number of questions
    if use_all_matching:
        parts.append(f"all_questions")
    else:
        parts.append(f"{num_questions}questions")

    return "_".join(parts)






def sample_questions_even_by_topic(
    questions: Iterable["Question"],
    n_desired: int,
    used_ids: Set[str],
    avoid_used: bool = True,
) -> Tuple[List["Question"], Set[str]]:
    """
    Given a list of filtered Question objects, return a random subset
    of size at most n_desired, trying to distribute evenly across topics.

    - used_ids: set of question IDs already used in this session
    - avoid_used: if True, skip any questions whose ID is in used_ids

    Returns: (selected_questions, updated_used_ids_set)
    """

    # Filter out questions with no page or already used
    candidates = [
        q
        for q in questions
        if q.question_page is not None
        and (not avoid_used or question_id(q) not in used_ids)
    ]

    if not candidates:
        return [], used_ids

    # We'll never pick more than we have
    n = min(n_desired, len(candidates))

    # Group candidates by topic (challenges have topics too, but that's fine;
    # they were already filtered in select_questions)
    by_topic: dict[int, list] = defaultdict(list)
    for q in candidates:
        by_topic[q.topic].append(q)

    topics = sorted(by_topic.keys())
    t_count = len(topics)
    if t_count == 0:
        return [], used_ids

    # Round-robin allocation across topics until we've assigned n slots
    allocation = {t: 0 for t in topics}
    remaining = n

    while remaining > 0:
        made_progress = False
        for t in topics:
            if remaining == 0:
                break
            if allocation[t] < len(by_topic[t]):
                allocation[t] += 1
                remaining -= 1
                made_progress = True
        if not made_progress:
            # No topic had spare capacity; we're done
            break

    # Now randomly sample per topic using the final allocation
    selected: List["Question"] = []
    for t in topics:
        k = allocation[t]
        if k <= 0:
            continue
        # random.sample ensures we don't pick the same question twice per topic
        selected.extend(random.sample(by_topic[t], k))

    # Shuffle final list so questions aren’t grouped by topic
    random.shuffle(selected)

    # Update used_ids
    new_used = set(used_ids)
    for q in selected:
        new_used.add(question_id(q))

    return selected, new_used


# -------------------------------------------------
# STREAMLIT APPLICATION
# -------------------------------------------------
def main():
    st.title("CHE 166 Practice Exam Builder 🧪")
    st.subheader("Build practice exams from in-class clicker questions")

    # --------------------------
    # NEW: Let user upload a PDF
    # --------------------------
    uploaded_file = st.file_uploader(
        "Upload clicker slides PDF (optional)",
        type=["pdf"],
        help="If you don't upload anything, the app will use the built-in PDF.",
    )

    if uploaded_file is not None:
        # Save uploaded PDF to a temporary file
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(uploaded_file.read())
        tmp.flush()
        tmp.close()
        src_pdf = tmp.name
        use_uploaded = True
        st.caption(f"Using uploaded PDF: {uploaded_file.name}")
    else:
        src_pdf = SRC_PDF
        use_uploaded = False
        st.caption(f"Using default PDF at: {SRC_PDF}")

    if not os.path.exists(src_pdf):
        st.error(f"Missing source PDF: {src_pdf}")
        return

    # --------------------------
    # Build / load question bank
    # --------------------------
    if use_uploaded:
        # Build a fresh bank in memory from the uploaded file

        st.info("Building question bank from uploaded PDF…") # TODO: hide this when upload finishes...
        entries = parse_pdf_to_entries(src_pdf)
        questions = build_question_bank(entries)
        st.success(f"Question bank built from upload! Found {len(questions)} questions.")
    else:
        # Use your existing JSON-based cache for the default PDF
        ensure_question_bank()
        questions = load_question_bank_json(BANK_JSON)

    topic_lg_map = load_topic_learning_goals(TOPIC_LG_JSON)

    st.info(f"Total questions in bank: **{len(questions)}**")

    # Topics actually present in the bank
    all_topics_in_bank = sorted({q.topic for q in questions})

    # Per-session used question IDs
    if "used_ids" not in st.session_state:
        st.session_state["used_ids"] = []

    # --------------------------
    # User
    # --------------------------

    if st.button("Reset my question history for this session"):
        st.session_state["used_ids"] = []
        st.success("Your question history for this session has been reset.")

    # --------------------------
    # Exam / Topic Range
    # --------------------------
    st.markdown("### Exam / Topic Range")

    exam_topic_ranges = {
        "Exam 1": (1, 6),
        "Exam 2": (7, 12),
        "Exam 3": (13, 18),
        "All": (1, 18),
    }
    exam_presets = {
        f"{name} (Topics {rng[0]}-{rng[1]})": list(range(rng[0], rng[1] + 1))
        for name, rng in exam_topic_ranges.items()
    }
    exam_presets["Custom (choose topics)"] = None

    exam_choice = st.radio(
        "Choose an exam or use custom topics:",
        options=list(exam_presets.keys()),
        index=2,
    )

    preset_topics = exam_presets[exam_choice]

    st.markdown("### Topics")

    selected_topics = []
    if preset_topics is None:
        selected_topics = st.multiselect(
            "Choose topics",
            options=all_topics_in_bank,
            default=all_topics_in_bank,
            format_func=lambda t: f"{t}: {topic_lg_map.get(t, {}).get('title', '')}",
        )
    else:
        selected_topics = [t for t in preset_topics if t in all_topics_in_bank]
        pretty = [
            f"T{t}: {topic_lg_map.get(t, {}).get('title', '')}" for t in selected_topics
        ]
        st.write(
            "Using topics:", ", ".join(pretty) if pretty else "None available in bank."
        )

    st.markdown("### Levels")
    all_levels = sorted({q.level for q in questions if q.level is not None})
    selected_levels = st.multiselect(
        "Choose difficulty levels",
        options=all_levels,
        default=all_levels,
    )

    include_challenges = st.checkbox(
        "Include challenge questions (Q0) [these questions don't have a level]",
        value=True,
    )

    num_questions = st.number_input(
        "Number of questions in this practice exam",
        min_value=1,
        max_value=200,
        value=20,
        step=1,
    )

    use_all_matching = st.checkbox(
        "Use all questions that match filters (max exam length) [ignores number in field above]",
        value=False,
    )

    avoid_used = st.checkbox(
        "Avoid questions used in previously generated practice exams (this session)",
        value=True,
    )

    # --------------------------
    # Advanced filters (LGs)
    # --------------------------
    advanced_mode = st.checkbox("Advanced filters (learning goals)", value=False)

    if advanced_mode:
        st.markdown("### Learning Goals (filtered by topic)")

        lg_triplets: list[tuple[int, str, str]] = []

        if selected_topics:
            for topic in selected_topics:
                goal_dict = topic_lg_map.get(topic, {}).get("goals", {})
                for code, text in goal_dict.items():
                    lg_triplets.append((topic, code, text))
        else:
            for topic, data in topic_lg_map.items():
                for code, text in data["goals"].items():
                    lg_triplets.append((topic, code, text))

        seen = set()
        unique_lg_triplets: list[tuple[int, str, str]] = []
        for topic, code, text in lg_triplets:
            key = (topic, code)
            if key not in seen:
                seen.add(key)
                unique_lg_triplets.append((topic, code, text))

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
        selected_lg_codes = None

    st.markdown("---")

    # --------------------------
    # Name + build PDFs
    # --------------------------
    if exam_choice.startswith("Exam"):
        preset_label = exam_choice.split()[1]  # "1", "2", "3", "4"
        if preset_label != "4":
            preset_label = f"exam{preset_label}"
        elif preset_label == "4":
            preset_label = "all_topics"
    else:
        preset_label = "custom"

    suggested_name = build_suggested_name(
        topics=selected_topics,
        levels=selected_levels,
        learning_goals=selected_lg_codes,
        num_questions=int(num_questions),
        use_all_matching=use_all_matching,
        preset_label=preset_label,
    )

    base_name = st.text_input("Name your PDF set (no spaces)", value=suggested_name)

    if st.button("Build PDFs"):
        filtered = select_questions(
            questions,
            topics=selected_topics or None,
            include_challenges=include_challenges,
            levels=selected_levels or None,
            learning_goals=selected_lg_codes or None,
            require_question_page=True,
        )

        st.write(f"Total questions matching filters (before sampling): {len(filtered)}")
        unused_filtered = [
            q
            for q in filtered
            if question_id(q) not in set(st.session_state["used_ids"])
        ]
        st.write(f"Unused questions matching filters: {len(unused_filtered)}")

        st.write(f"Found **{len(filtered)}** questions matching your filters.")

        if not filtered:
            st.warning("No questions match these filters.")
            return

        current_used_ids = set(st.session_state.get("used_ids", []))

        n_desired = int(num_questions)
        if use_all_matching:
            if avoid_used:
                n_desired = len(unused_filtered)
            else:
                n_desired = len(filtered)
        else:
            n_desired = int(num_questions)

        selected, updated_used_ids = sample_questions_even_by_topic(
            filtered,
            n_desired=n_desired,
            used_ids=current_used_ids,
            avoid_used=avoid_used,
        )

        if avoid_used and len(selected) < num_questions:
            st.warning(
                f"Only {len(selected)} unused questions available matching your filters. "
                f"The exam will have {len(selected)} questions."
            )

        if not selected:
            st.warning("No available questions left (given filters and usage history).")
            return

        st.session_state["used_ids"] = list(updated_used_ids)

        st.write(f"Selected **{len(selected)}** questions for this exam.")

        os.makedirs("output", exist_ok=True)
        q_path = f"output/{base_name}_questions.pdf"
        s_path = f"output/{base_name}_solutions.pdf"
        qa_path = f"output/{base_name}_q_and_a.pdf"

        # IMPORTANT: use src_pdf (uploaded or default), not SRC_PDF
        build_question_pdf(src_pdf, selected, q_path)
        build_solution_pdf(src_pdf, selected, s_path)
        build_interleaved_q_and_a_pdf(src_pdf, selected, qa_path)

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
