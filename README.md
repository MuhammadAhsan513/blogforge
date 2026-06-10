# 📝 BlogForge — LangGraph AI Blog Writer

> QAU LangGraph Group Project. An autonomous AI agent that turns a single topic into
> a polished, SEO-optimized blog post — researching, drafting, self-evaluating with a
> retry loop, and pausing for human review before publishing.

**Workflow type: Iterative + Conditional**

Given a topic, BlogForge runs live web research, structures and writes a full post,
injects SEO keywords, **scores its own output** and **loops back to rewrite** when
quality is low, then stops at a **human-review checkpoint** where you can approve or
request edits before it publishes.

---

## 🧭 Architecture

![BlogForge graph](flowchart/blogforge_graph.png)

```
START → research → outline → draft → seo → quality_check
quality_check ──(score < 75 & retries left)──▶ draft        (retry loop)
quality_check ──(score ≥ 75 or retries done)─▶ human_review
human_review  ──(approve)────────────────────▶ publish
human_review  ──(request edit)───────────────▶ draft        (human loop)
publish → END
```

| Node | What it does |
|------|--------------|
| `research` | Multi-query **DuckDuckGo** search, aggregates sources (append reducer), LLM distils facts |
| `outline` | Structures the title + section headings |
| `draft` | Writes the full markdown post; consumes feedback on retries |
| `seo` | Generates keywords/meta/slug, runs a **custom SEO scorer** tool |
| `quality_check` | Scores the draft 0–100; drives the conditional retry loop |
| `human_review` | Pauses via `interrupt()` for approve / request-edit |
| `publish` | Exports final Markdown + JSON snapshot |

---

## ✅ LangGraph features

| # | Requirement | How it's met |
|---|-------------|--------------|
| 1 | **State (TypedDict + reducer)** | `BlogState` in `state.py`; `research_results` uses an `operator.add` append reducer |
| 2 | **≥3 meaningful nodes** | 7 nodes in `nodes.py`, each doing real LLM/tool work |
| 3 | **Conditional edges** | `route_after_quality` and `route_after_review` in `graph.py` |
| 4 | **A loop** | `draft → quality_check → draft` retry (capped at 2 retries) + human-edit loop |
| 5 | **Tool use** | DuckDuckGo web search + custom `seo_scorer` tool (`tools.py`) |
| 6 | **Memory / Persistence** | `MemorySaver` + `thread_id`; `interrupt()` pauses & resumes from the checkpoint |
| 7 | **Structured output** | Pydantic models via `with_structured_output()` (`models.py`) |
| 8 | **Streamlit interface** | `app.py` — progress tracker, quality badge, review panel, downloads |

---

## 🚀 Setup & run

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your Groq API key
cp .env.example .env
#   then edit .env and set GROQ_API_KEY=gsk_...
#   (get a free key at https://console.groq.com/keys)

# 4. Launch the Streamlit app
streamlit run app.py
```

The notebook walkthrough (with the graph diagram and a full run) is in
**`agent.ipynb`** — open it in Jupyter/VS Code, or run:

```bash
jupyter notebook agent.ipynb
```

---

## 🧩 Tech stack

| Component | Library |
|-----------|---------|
| Agent framework | `langgraph` |
| LLM | `langchain-groq` → `ChatGroq` (`llama-3.3-70b-versatile`) |
| Web search | DuckDuckGo via `ddgs` (no API key) |
| Structured output | `pydantic` v2 |
| Persistence | `MemorySaver` (built-in) |
| UI | `streamlit` |

> **Switching models:** set `GROQ_MODEL` in `.env` (e.g. `llama-3.1-8b-instant`)
> if you hit free-tier rate limits during a live demo.

---

## 📁 Project structure

```
BlogForge/
├── app.py            # Streamlit UI
├── graph.py          # StateGraph, edges, routing, compile(MemorySaver)
├── nodes.py          # The 7 node functions
├── state.py          # BlogState TypedDict + reducer
├── models.py         # Pydantic models (structured output)
├── tools.py          # DuckDuckGo search + custom SEO scorer
├── prompts.py        # Prompt builders per node
├── llm.py            # ChatGroq factory
├── agent.ipynb       # Notebook with draw_mermaid_png() + full run
├── flowchart/        # Graph diagram (PNG)
├── slides/           # Presentation slides
├── requirements.txt
├── .env.example      # Template (never commit the real .env)
└── README.md
```

## 🔐 API key note

Never commit your real key. `.env` is git-ignored; only `.env.example` is tracked.
