import os
import json
import random
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
    select_questions,  # your existing filter helper
)

SRC_PDF = "data/slides.pdf"
BANK_JSON = "output/question_bank.json"
TOPIC_LG_JSON = "config/topic_learning_goals.json"
USED_IDS_JSON = "output/used_questions.json"

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
# Used-question tracking helpers
# -------------------------------------------------
def question_id(q) -> str:
    """A stable ID for a question so we can track if it's been used."""
    # topic + qnum is enough here; include challenge flag just in case
    return f"T{q.topic}-Q{q.qnum}-C{int(bool(q.is_challenge))}"


def load_used_ids(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return set(data)


def save_used_ids(path: str, ids: set[str]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(list(ids)), f, indent=2)

def build_suggested_name(
    user_id: str | None,
    topics: list[int],
    levels: list[int] | None,
    learning_goals: list[str] | None,
    num_questions: int
) -> str:
    """Build a filename string summarizing filters."""

    parts = ["practice_questions"]

    # Include user ID prefix if provided
    if user_id:
        safe = "".join(ch for ch in user_id.lower() if ch.isalnum() or ch in "-_")
        if safe:
            parts.append(safe)

    # Topics
    if topics:
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
    parts.append(f"{num_questions}questions")

    # Final joined name
    return "_".join(parts)


# -------------------------------------------------
# Sampling helper: even-ish distribution by topic
# -------------------------------------------------
def sample_questions_even_by_topic(
    questions,
    n_desired: int,
    avoid_used: bool = True,
    used_ids_path: str | None = None,
):
    """
    Given a list of filtered Question objects, return a random subset
    of size at most n_desired, trying to distribute evenly across topics.

    If avoid_used=True and used_ids_path is provided, we skip questions whose
    IDs are in the used set.

    Returns: (selected_questions, updated_used_ids_set)
    """
    # Load or init used IDs
    used_ids = load_used_ids(used_ids_path) if (avoid_used and used_ids_path) else set()

    # Filter out questions with no page or already used
    candidates = [
        q
        for q in questions
        if q.question_page is not None
        and (not avoid_used or question_id(q) not in used_ids)
    ]

    if not candidates:
        return [], used_ids

    # Cap requested size by availability
    n = min(n_desired, len(candidates))

    # Group by topic
    from collections import defaultdict

    by_topic: dict[int, list] = defaultdict(list)
    for q in candidates:
        by_topic[q.topic].append(q)

    topics = sorted(by_topic.keys())
    t_count = len(topics)

    if t_count == 0:
        return [], used_ids

    # Base allocation per topic
    base = n // t_count
    rem = n % t_count

    # Initial allocation can't exceed available in that topic
    allocation: dict[int, int] = {
        t: min(base, len(by_topic[t])) for t in topics
    }

    # Distribute remainder one by one to topics that still have spare capacity
    remaining = rem
    while remaining > 0:
        # topics that still have more candidates than allocated
        avail_topics = [t for t in topics if allocation[t] < len(by_topic[t])]
        if not avail_topics:
            break
        for t in avail_topics:
            if remaining == 0:
                break
            allocation[t] += 1
            remaining -= 1

    # Now randomly sample per topic
    selected = []
    for t in topics:
        k = allocation[t]
        if k <= 0:
            continue
        selected.extend(random.sample(by_topic[t], k))

    # Shuffle final list so questions aren't grouped by topic
    random.shuffle(selected)

    # Update used IDs
    for q in selected:
        used_ids.add(question_id(q))

    return selected, used_ids


# -------------------------------------------------
# STREAMLIT APPLICATION
# -------------------------------------------------
def main():
    st.title("CHE 166 Practice Exam Builder 🧪")
    st.subheader("Build practice exams from in-class clicker questions (Exam 3 only now)")



    if not os.path.exists(SRC_PDF):
        st.error(f"Missing source PDF: {SRC_PDF}")
        return


    ensure_question_bank()

    questions = load_question_bank_json(BANK_JSON)
    topic_lg_map = load_topic_learning_goals(TOPIC_LG_JSON)

    st.info(f"Total questions in bank: **{len(questions)}**")

    # Topics actually present in the bank
    all_topics_in_bank = sorted({q.topic for q in questions})


    st.header("User")

    if "user_id" not in st.session_state:
        st.session_state["user_id"] = ""

    user_id = st.text_input(
        "Enter a unique name so we can track which questions you've seen",
        value="",
        key="user_id",
        placeholder="e.g. alice",
    )

    # Simple sanitization: lowercase, no spaces
    if user_id.strip():
        safe_user_id = "".join(ch for ch in user_id.strip().lower() if ch.isalnum() or ch in ("_", "-"))
        used_ids_path = f"output/used_questions_{safe_user_id}.json"
    else:
        # Fallback: shared/global history if no ID provided
        used_ids_path = USED_IDS_JSON

    # JavaScript: persist to browser localStorage - 
    # TODO: get this to use safe user id?
    st.write(
    """
    <script>
    const input = window.parent.document.querySelector('input[id="user_id"]');
    if (input) {
        // Load saved value on page load
        const saved = localStorage.getItem("che166_user_id");
        if (saved && !input.value) {
            input.value = saved;
            input.dispatchEvent(new Event('input'));
        }

        // Save changes
        input.onchange = () => {
            localStorage.setItem("che166_user_id", input.value);
        };
    }
    </script>
    """,
    unsafe_allow_html=True,
)

    st.caption(f"Using history file: {used_ids_path}")

    # Reset history button (only for this user's file)
    if st.button("Reset my question history"):
        if os.path.exists(used_ids_path):
            os.remove(used_ids_path)
            st.success(f"History reset! Removed {used_ids_path}")
        else:
            st.info("No history file existed to reset.")




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

    # How many questions?
    num_questions = st.number_input(
        "Number of questions in this practice exam",
        min_value=1,
        max_value=200,
        value=20,
        step=1,
    )

    avoid_used = st.checkbox(
        "Avoid questions used in previously generated practice exams",
        value=True,
    )

    # --------------------------
    # Advanced Mode for learning goals
    # --------------------------
    advanced_mode = st.checkbox("Advanced filters (learning goals)", value=False)

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
            for topic, data in topic_lg_map.items():
                for code, text in data["goals"].items():
                    lg_triplets.append((topic, code, text))

        # Dedupe
        seen = set()
        unique_lg_triplets: list[tuple[int, str, str]] = []
        for topic, code, text in lg_triplets:
            key = (topic, code)
            if key not in seen:
                seen.add(key)
                unique_lg_triplets.append((topic, code, text))

        # Labels like "T13 · LG 4: Balance chemical equations…"
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

    # -------------------------------------------------------
    # Name + Build PDFs
    # -------------------------------------------------------
    suggested_name = build_suggested_name(
    user_id=user_id,
    topics=selected_topics,
    levels=selected_levels,
    learning_goals=selected_lg_codes,
    num_questions=int(num_questions),
)
    
    base_name = st.text_input("Name your PDF set (no spaces)", value=suggested_name)

    if st.button("Build PDFs"):
        # 1) Apply topic/level/LG filters to get a candidate pool
        filtered = select_questions(
            questions,
            topics=selected_topics or None,
            include_challenges=include_challenges,
            levels=selected_levels or None,
            learning_goals=selected_lg_codes or None,
            require_question_page=True,
        )

        st.write(f"Found **{len(filtered)}** questions matching your filters.")

        if not filtered:
            st.warning("No questions match these filters.")
            return

        # 2) Sample evenly by topic, avoiding previously used if requested
        selected, updated_used_ids = sample_questions_even_by_topic(
            filtered,
            n_desired=int(num_questions),
            avoid_used=avoid_used,
            used_ids_path=used_ids_path,
        )


        if avoid_used and len(selected) < num_questions:
            st.warning(
                f"Only {len(selected)} unused questions available matching your filters. "
                f"The exam will have {len(selected)} questions."
            )

        if not selected:
            st.warning("No available questions left (given filters and usage history).")
            return

        # Save updated used IDs (only if we actually avoid_used)
        if avoid_used and used_ids_path:
            save_used_ids(used_ids_path, updated_used_ids)


        st.write(f"Selected **{len(selected)}** questions for this exam.")

        os.makedirs("output", exist_ok=True)
        q_path = f"output/{base_name}_questions.pdf"
        s_path = f"output/{base_name}_solutions.pdf"
        qa_path = f"output/{base_name}_q_and_a.pdf"

        # 3) Build PDFs for the sampled questions
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
