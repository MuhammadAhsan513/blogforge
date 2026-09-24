"""BlogForge — Streamlit interface (assignment requirement 8).

Run with:  streamlit run app.py

The compiled graph is cached with @st.cache_resource so its in-memory MemorySaver
checkpoint survives Streamlit reruns; the active thread_id lives in session_state.
A small phase state-machine (idle -> review -> done) drives the UI around the
graph's interrupt() human-review checkpoint. Visual layer lives in ui.py.
"""
import logging
import os
import uuid

import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

import ui
from graph import build_graph
from config.models import list_providers, list_models
from config.plans import get_plan_config
from providers.errors import BlogForgeLLMError

load_dotenv()

logger = logging.getLogger("blogforge")

st.set_page_config(page_title="BlogForge — AI Blog Writer", page_icon="📝", layout="wide")
st.markdown(ui.inject_css(), unsafe_allow_html=True)

EXAMPLES = [
    "Benefits of intermittent fasting for beginners",
    "How to start composting at home",
    "Remote work productivity tips for 2025",
]

PROVIDER_LABELS = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "groq": "Groq (free tier)",
}
PROVIDER_KEY_HELP = {
    "anthropic": "From console.anthropic.com/settings/keys. Used only for this session.",
    "openai": "From platform.openai.com/api-keys. Used only for this session.",
    "groq": "Free key from console.groq.com/keys. Used only for this session.",
}
# Optional server/dev fallbacks (.env) — the sidebar field below is
# pre-filled from these if present, but a user's own typed key always
# takes priority once they edit the field.
ENV_KEY_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "groq": "GROQ_API_KEY",
}
ENV_MODEL_VARS = {
    "anthropic": "ANTHROPIC_MODEL",
    "openai": "OPENAI_MODEL",
    "groq": "GROQ_MODEL",
}


def _provider_label(provider: str) -> str:
    return PROVIDER_LABELS.get(provider, provider.title())


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
    ss.setdefault("error_retryable", False)
    ss.setdefault("topic_input", "")


def _config():
    sel = st.session_state.get("_selection", {})
    return {
        "configurable": {
            "thread_id": st.session_state.thread_id,
            "provider": sel.get("provider"),
            "model": sel.get("model"),
            "api_key": sel.get("api_key"),
            "plan": sel.get("tier"),
        }
    }


def _reset_session():
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.phase = "idle"
    st.session_state.error = ""
    st.session_state.error_retryable = False
    st.session_state.topic_input = ""


# --------------------------------------------------------------------------- #
# Graph driving (with live animated stepper)
# --------------------------------------------------------------------------- #
def _stream(graph_input, revision_context: str | None = None):
    graph = get_graph()
    st.session_state.error = ""

    with st.container(border=True):
        st.markdown(ui.section("Generating your blog post", "⚙️"), unsafe_allow_html=True)
        track = st.empty()
        caption = st.empty()
        done = set()
        revision_count = None
        track.markdown(ui.stepper(done, ui.STEPS[0][0]), unsafe_allow_html=True)
        try:
            for chunk in graph.stream(graph_input, _config(), stream_mode="updates"):
                for node, update in chunk.items():
                    if node == "__interrupt__":
                        track.markdown(ui.stepper(done, "human_review"), unsafe_allow_html=True)
                        caption.caption("⏸️ Paused for your review")
                        continue

                    if node == "draft":
                        revision_count = update.get("revision_count", revision_count)
                    is_repeat_draft = node == "draft" and node in done
                    is_human_edit_draft = (
                        node == "draft" and node not in done and revision_context == "human_edit"
                    )

                    done.add(node)
                    nxt = ui.NEXT.get(node)
                    track.markdown(ui.stepper(done, nxt), unsafe_allow_html=True)
                    label = dict((k, l) for k, l, _ in ui.STEPS).get(node, node)

                    if is_repeat_draft:
                        text = ui.revision_caption("quality", revision_count)
                    elif is_human_edit_draft:
                        text = ui.revision_caption("human_edit", revision_count)
                    else:
                        extra = (
                            f" — scored {update.get('quality_score')}/100"
                            if node == "quality_check" else ""
                        )
                        text = f"✓ {label} complete{extra}"

                    next_text = None
                    if node == "quality_check":
                        sel = st.session_state.get("_selection", {})
                        plan = get_plan_config(sel.get("tier"))
                        will_revise = (
                            update.get("quality_score", 0) < plan.quality_threshold
                            and (revision_count or 0) < plan.max_drafts
                        )
                        next_text = (
                            "Revising the draft based on the quality check…"
                            if will_revise else "Preparing for your review…"
                        )
                    elif node != "publish":
                        next_text = ui.PROGRESS_LABEL.get(nxt)

                    caption.caption(f"{text} · {next_text}" if next_text else text)
            snap = graph.get_state(_config())
            st.session_state.phase = "review" if snap.next else "done"
        except BlogForgeLLMError as exc:  # normalized, user-safe LLM/provider errors
            logger.error("LLM error during graph run: %s", exc.technical_detail)
            st.session_state.error = exc.user_message
            st.session_state.error_retryable = exc.retryable
        except Exception:  # anything else: never leak a raw traceback to the UI
            logger.exception("Unexpected error during graph run")
            st.session_state.error = (
                "Something went wrong while generating your post. Please try again."
            )
            st.session_state.error_retryable = False
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
        st.markdown(ui.sidebar_brand(), unsafe_allow_html=True)
        if st.button("+ New blog post", type="primary", use_container_width=True):
            _reset_session()
            st.rerun()

        st.divider()
        st.markdown('<div class="bf-side-title">⚙️ AI configuration</div>', unsafe_allow_html=True)
        st.write("")

        provider = st.selectbox(
            "AI provider",
            list_providers(),
            format_func=_provider_label,
            key="provider_select",
        )

        models = list_models(provider=provider)
        env_model_id = os.getenv(ENV_MODEL_VARS.get(provider, ""), "")
        default_index = next(
            (i for i, m in enumerate(models) if m.model_id == env_model_id), 0
        )
        model_info = st.selectbox(
            "Model",
            models,
            index=default_index,
            format_func=lambda m: m.display_name,
            help="Model options and their free/paid tier come from the central model "
            "registry (config/models.py).",
            # Keyed per-provider so switching providers never leaves a stale
            # selection from another provider's model list.
            key=f"model_select_{provider}",
        )

        api_key = st.text_input(
            f"{_provider_label(provider)} API key",
            value=os.getenv(ENV_KEY_VARS.get(provider, ""), ""),
            type="password",
            help=PROVIDER_KEY_HELP.get(provider, "Used only for this session."),
            key=f"api_key_input_{provider}",
        )

        plan = get_plan_config(model_info.tier)
        st.markdown(
            ui.usage_panel(model_info.tier, plan, model_info.display_name),
            unsafe_allow_html=True,
        )

        st.markdown(f"**Workflow** · {ui.workflow_summary()}")
        st.caption("Self-corrects on low quality · pauses for human approval.")

        with st.expander("Session info"):
            st.markdown(
                f'<div class="bf-kw"><span>thread: {st.session_state.thread_id[:8]}</span>'
                f'<span>phase: {st.session_state.phase}</span></div>',
                unsafe_allow_html=True,
            )

        selection = {
            "provider": provider,
            "model": model_info.model_id,
            "api_key": (api_key or "").strip(),
            "tier": model_info.tier,
        }
        st.session_state["_selection"] = selection
        return selection


# --------------------------------------------------------------------------- #
# Phases
# --------------------------------------------------------------------------- #
def phase_idle(selection):
    st.markdown(ui.hero(), unsafe_allow_html=True)

    api_key = selection.get("api_key")

    with st.container(border=True):
        topic = st.text_input(
            "Blog topic",
            key="topic_input",
            placeholder="e.g. The benefits of intermittent fasting for beginners",
            label_visibility="collapsed",
        )
        disabled = not (api_key and topic.strip())
        if st.button("🚀 Generate blog post", type="primary",
                     disabled=disabled, use_container_width=True):
            plan = get_plan_config(selection.get("tier", "paid"))
            _stream({
                "topic": topic.strip(),
                "revision_count": 0,
                "plan": selection.get("tier"),
                "max_drafts": plan.max_drafts,
                "quality_threshold": plan.quality_threshold,
            })

        if not api_key:
            label = _provider_label(selection.get("provider", ""))
            st.info(f"Add your {label} API key in the sidebar to begin.", icon="🔑")
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

    st.markdown(ui.section("This article is ready for your review", "👀"), unsafe_allow_html=True)
    st.markdown(ui.stepper({"research", "outline", "draft", "seo", "quality_check"},
                           "human_review"), unsafe_allow_html=True)
    st.markdown(
        ui.metrics(vals.get("quality_score"), vals.get("revision_count"),
                   draft.get("word_count"), seo.get("report", {}).get("seo_score")),
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown(ui.section("SEO details", "🚀"), unsafe_allow_html=True)
        st.markdown(ui.seo_card(seo), unsafe_allow_html=True)

    if vals.get("quality_feedback"):
        with st.expander("🧠 Reviewer feedback from the quality check"):
            st.markdown(
                ui.quality_feedback_card(vals.get("quality_score"), vals["quality_feedback"]),
                unsafe_allow_html=True,
            )

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
                    _stream(Command(resume={"action": "edit", "feedback": fb}),
                            revision_context="human_edit")


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
    with st.container(border=True):
        st.markdown(ui.section("SEO details", "🚀"), unsafe_allow_html=True)
        st.markdown(ui.seo_card(seo), unsafe_allow_html=True)

    _render_post_card(draft)

    with st.expander("📋 View / copy markdown"):
        st.code(vals.get("final_markdown", ""), language="markdown")

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
    selection = sidebar()

    st.markdown(ui.topbar(), unsafe_allow_html=True)

    if st.session_state.error:
        if st.session_state.error_retryable:
            st.warning(st.session_state.error, icon="⏳")
        else:
            st.error(st.session_state.error, icon="⚠️")

    phase = st.session_state.phase
    if phase == "idle":
        phase_idle(selection)
    elif phase == "review":
        phase_review()
    elif phase == "done":
        phase_done()

    st.markdown(ui.footer(), unsafe_allow_html=True)


if __name__ == "__main__":
    main()
