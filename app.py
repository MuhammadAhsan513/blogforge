"""BlogForge — Streamlit interface (assignment requirement 8).

Run with:  streamlit run app.py

The compiled graph is cached with @st.cache_resource so its in-memory MemorySaver
checkpoint survives Streamlit reruns; the active thread_id lives in session_state.
A small phase state-machine (idle -> review -> done) drives the UI around the
graph's interrupt() human-review checkpoint. Visual layer lives in ui.py.
"""
import os
import uuid

import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

import ui
from graph import build_graph

load_dotenv()

st.set_page_config(page_title="BlogForge — AI Blog Writer", page_icon="📝", layout="wide")
st.markdown(ui.inject_css(), unsafe_allow_html=True)

EXAMPLES = [
    "Benefits of intermittent fasting for beginners",
    "How to start composting at home",
    "Remote work productivity tips for 2025",
]


# --------------------------------------------------------------------------- #
# Cached graph + session helpers
# --------------------------------------------------------------------------- #
@st.cache_resource
def get_graph():
    """Build the graph once; its MemorySaver persists across reruns."""
    return build_graph()


def _init_state():
    ss = st.session_state
    ss.setdefault("thread_id", str(uuid.uuid4()))
    ss.setdefault("phase", "idle")          # idle | review | done
    ss.setdefault("error", "")
    ss.setdefault("topic_input", "")


def _config():
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def _reset_session():
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.phase = "idle"
    st.session_state.error = ""
    st.session_state.topic_input = ""


# --------------------------------------------------------------------------- #
# Graph driving (with live animated stepper)
# --------------------------------------------------------------------------- #
def _stream(graph_input):
    graph = get_graph()
    st.session_state.error = ""

    with st.container(border=True):
        st.markdown(ui.section("Generating your blog post", "⚙️"), unsafe_allow_html=True)
        track = st.empty()
        caption = st.empty()
        done = set()
        track.markdown(ui.stepper(done, ui.STEPS[0][0]), unsafe_allow_html=True)
        try:
            for chunk in graph.stream(graph_input, _config(), stream_mode="updates"):
                for node, update in chunk.items():
                    if node == "__interrupt__":
                        track.markdown(ui.stepper(done, "human_review"), unsafe_allow_html=True)
                        caption.caption("⏸️ Paused for your review")
                        continue
                    done.add(node)
                    nxt = ui.NEXT.get(node)
                    track.markdown(ui.stepper(done, nxt), unsafe_allow_html=True)
                    label = dict((k, l) for k, l, _ in ui.STEPS).get(node, node)
                    extra = f" — scored {update.get('quality_score')}/100" if node == "quality_check" else ""
                    caption.caption(f"✓ {label} complete{extra}")
            snap = graph.get_state(_config())
            st.session_state.phase = "review" if snap.next else "done"
        except Exception as exc:  # surface key/quota/network errors gracefully
            msg = str(exc)
            low = msg.lower()
            if "rate_limit" in low or "429" in low or "tokens per day" in low:
                st.session_state.error = (
                    "RATE_LIMIT::Groq's free-tier token limit was hit for this model. "
                    "Switch the model to **llama-3.1-8b-instant** in the sidebar (it has a "
                    "higher free daily limit), or wait for the quota to reset.\n\n"
                    f"Details: {msg}"
                )
            else:
                st.session_state.error = msg
    st.rerun()


def _render_post_card(draft: dict):
    body = "\n\n".join(draft.get("sections", []))
    with st.container(border=True):
        st.markdown('<div class="bf-article">', unsafe_allow_html=True)
        st.markdown(f"# {draft.get('title', '')}")
        st.markdown(body)
        st.markdown("</div>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
def sidebar():
    with st.sidebar:
        st.markdown('<div class="bf-side-title">⚙️ Settings</div>', unsafe_allow_html=True)
        st.write("")
        key = st.text_input(
            "Groq API key",
            value=os.getenv("GROQ_API_KEY", ""),
            type="password",
            help="Free key at console.groq.com/keys. Used only for this session.",
        )
        if key:
            os.environ["GROQ_API_KEY"] = key.strip()

        model = st.selectbox(
            "Model",
            ["llama-3.3-70b-versatile", "openai/gpt-oss-20b", "llama-3.1-8b-instant"],
            index=0,
            help="If you hit a daily rate limit on one model, switch to another — "
                 "each model has its own free-tier quota. 70B gives the best writing; "
                 "gpt-oss-20b is a reliable alternative; 8b-instant is fastest but has a "
                 "tight per-minute limit.",
        )
        os.environ["GROQ_MODEL"] = model

        st.markdown(
            f'<div class="bf-kw"><span>thread: {st.session_state.thread_id[:8]}</span>'
            f'<span>phase: {st.session_state.phase}</span></div>',
            unsafe_allow_html=True,
        )

        if st.button("🔄 Reset session", use_container_width=True):
            _reset_session()
            st.rerun()

        st.divider()
        st.markdown(
            "**Workflow** · Iterative + Conditional\n\n"
            "`research → outline → draft → seo → quality_check → review → publish`"
        )
        st.caption("Self-corrects on low quality · pauses for human approval.")
        return key


# --------------------------------------------------------------------------- #
# Phases
# --------------------------------------------------------------------------- #
def phase_idle(key):
    st.markdown(ui.hero(), unsafe_allow_html=True)

    with st.container(border=True):
        topic = st.text_input(
            "Blog topic",
            key="topic_input",
            placeholder="e.g. The benefits of intermittent fasting for beginners",
            label_visibility="collapsed",
        )
        disabled = not (key and topic.strip())
        if st.button("🚀 Generate blog post", type="primary",
                     disabled=disabled, use_container_width=True):
            _stream({"topic": topic.strip(), "revision_count": 0})

        if not key:
            st.info("Add your Groq API key in the sidebar to begin.", icon="🔑")
        else:
            st.caption("Try an example:")
            cols = st.columns(len(EXAMPLES))
            for col, ex in zip(cols, EXAMPLES):
                if col.button(ex, use_container_width=True, key=f"ex_{ex}"):
                    st.session_state.topic_input = ex
                    st.rerun()


def phase_review():
    snap = get_graph().get_state(_config())
    vals = snap.values
    draft = vals.get("draft", {})
    seo = vals.get("seo_output", {})

    st.markdown(ui.section("Human review checkpoint", "👀"), unsafe_allow_html=True)
    st.markdown(ui.stepper({"research", "outline", "draft", "seo", "quality_check"},
                           "human_review"), unsafe_allow_html=True)
    st.markdown(
        ui.metrics(vals.get("quality_score"), vals.get("revision_count"),
                   draft.get("word_count"), seo.get("report", {}).get("seo_score")),
        unsafe_allow_html=True,
    )
    st.markdown(ui.keyword_tags(seo.get("keywords", [])), unsafe_allow_html=True)

    if vals.get("quality_feedback"):
        with st.expander("🧠 Reviewer feedback from the quality check"):
            st.write(vals["quality_feedback"])

    _render_post_card(draft)

    st.markdown(ui.section("Your decision", "🗳️"), unsafe_allow_html=True)
    col1, col2 = st.columns([1, 1.4])
    with col1:
        with st.container(border=True):
            st.markdown("**Looks good?**")
            if st.button("✅ Approve & publish", type="primary", use_container_width=True):
                _stream(Command(resume={"action": "approve"}))
    with col2:
        with st.container(border=True):
            with st.form("edit_form"):
                st.markdown("**Request changes** (loops back to redraft)")
                fb = st.text_area("Feedback", placeholder="e.g. Add a section on common mistakes.",
                                  label_visibility="collapsed")
                if st.form_submit_button("✏️ Request edit", use_container_width=True):
                    _stream(Command(resume={"action": "edit", "feedback": fb}))


def phase_done():
    snap = get_graph().get_state(_config())
    vals = snap.values
    draft = vals.get("draft", {})
    seo = vals.get("seo_output", {})

    st.markdown(ui.section("Published", "✅"), unsafe_allow_html=True)
    st.markdown(ui.stepper(set(k for k, _, _ in ui.STEPS)), unsafe_allow_html=True)
    st.markdown(
        ui.metrics(vals.get("quality_score"), vals.get("revision_count"),
                   draft.get("word_count"), seo.get("report", {}).get("seo_score")),
        unsafe_allow_html=True,
    )
    st.markdown(ui.keyword_tags(seo.get("keywords", [])), unsafe_allow_html=True)

    _render_post_card(draft)

    slug = seo.get("slug", "blog-post")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("⬇️ Download .md", vals.get("final_markdown", ""),
                           file_name=f"{slug}.md", mime="text/markdown", use_container_width=True)
    with c2:
        st.download_button("⬇️ Download .json", vals.get("final_json", "{}"),
                           file_name=f"{slug}.json", mime="application/json", use_container_width=True)
    with c3:
        if st.button("📝 Write another", use_container_width=True):
            _reset_session()
            st.rerun()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    _init_state()
    key = sidebar()

    st.markdown(ui.topbar(), unsafe_allow_html=True)

    if st.session_state.error:
        err = st.session_state.error
        if err.startswith("RATE_LIMIT::"):
            st.warning(err.replace("RATE_LIMIT::", ""), icon="⏳")
        else:
            st.error(f"Something went wrong: {err}", icon="⚠️")

    phase = st.session_state.phase
    if phase == "idle":
        phase_idle(key)
    elif phase == "review":
        phase_review()
    elif phase == "done":
        phase_done()

    st.markdown(ui.footer(), unsafe_allow_html=True)


if __name__ == "__main__":
    main()
