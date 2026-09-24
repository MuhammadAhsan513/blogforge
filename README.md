# 📝 BlogForge — LangGraph AI Blog Writer

> An autonomous AI agent that turns a single topic into
> a polished, SEO-optimized blog post — researching, drafting, self-evaluating with a
> retry loop, and pausing for human review before publishing.

**Workflow type: Iterative + Conditional**

Given a topic, BlogForge runs live web research, structures and writes a full post,
injects SEO keywords, **scores its own output** and **loops back to rewrite** when
quality is low, then stops at a **human-review checkpoint** where you can approve or
request edits before it publishes.

---

## 🧭 Architecture

BlogForge is **provider-agnostic**: the LangGraph workflow never knows whether
Anthropic, OpenAI, or Groq is answering a call. The Streamlit sidebar picks a
provider/model, and a small config + provider-adapter layer resolves that into
a concrete LLM before each node runs:

```
Streamlit UI (app.py)
   │  Provider ▸ Model ▸ API key  (sidebar)
   ▼
config/models.py   — model registry (provider, model, tier, structured-output method)
config/plans.py    — FREE vs PAID budgets (tokens/stage, research limits, retries)
   │
   ▼
llm.py             — get_llm() / invoke_structured()   ← the only thing nodes.py calls
   │
   ▼
providers/         — base.py + anthropic_provider.py / openai_provider.py / groq_provider.py
                      each: build_chat_model(), structured_output_method(), normalize_error()
   │
   ▼
Selected LangChain chat model (ChatAnthropic / ChatOpenAI / ChatGroq)
   │
   ▼
LangGraph workflow (unchanged regardless of provider)
```

![BlogForge graph](flowchart/blogforge_graph.png)

```
START → research → outline → draft → seo → quality_check
quality_check ──(score < threshold & retries left)──▶ draft   (retry loop)
quality_check ──(score ≥ threshold or retries done)─▶ human_review
human_review  ──(approve)────────────────────▶ publish
human_review  ──(request edit)───────────────▶ draft        (human loop)
publish → END
```

`threshold` and the retry cap come from the active usage plan (see below) —
75 / 2 retries for paid tiers, 75 / 1 retry for the free tier — instead of
being hardcoded.

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

# 3. (optional) Pre-fill a provider key for local/dev use
cp .env.example .env
#   then edit .env and set ANTHROPIC_API_KEY / OPENAI_API_KEY / GROQ_API_KEY
#   — you can also skip this and just paste a key into the sidebar at runtime

# 4. Launch the Streamlit app
streamlit run app.py
```

In the sidebar, pick a **provider**, then a **model**, then paste your API
key for that provider — the key is used only for the current session and is
never logged or persisted. See "LLM providers & usage plans" below.

The notebook walkthrough (with the graph diagram and a full run) is in
**`agent.ipynb`** — open it in Jupyter/VS Code, or run:

```bash
jupyter notebook agent.ipynb
```

---

## 🔌 LLM providers & usage plans

BlogForge supports three providers out of the box, each already registered
in **`config/models.py`**:

| Provider | Tier | Models | API key |
|----------|------|--------|---------|
| **Anthropic** | Paid (bring your own key) | Claude Sonnet 5, Claude Haiku 4.5 | console.anthropic.com/settings/keys |
| **OpenAI** | Paid (bring your own key) | GPT-4o, GPT-4o mini | platform.openai.com/api-keys |
| **Groq** | Free (bring your own free key) | Llama 3.3 70B Versatile, Llama 3.1 8B Instant, GPT-OSS 120B, GPT-OSS 20B | console.groq.com/keys |

A model's `tier` (free/paid) automatically selects its **usage plan** from
**`config/plans.py`** — there's no separate "plan" dropdown in the UI. Each
plan controls, per workflow stage:

- max completion tokens (`research`/`outline`/`draft`/`seo`/`quality`)
- research breadth (search queries, results per query, snippet/result truncation)
- how much of the draft is sent to the `seo`/`quality` stages
- `max_drafts` (revision-loop cap) and `quality_threshold`
- `max_retries` for transient/rate-limit errors (always bounded, never a retry storm)

**Paid tier** budgets match BlogForge's original hardcoded values exactly
(1200/800/4096/800/1000 tokens, 2 draft attempts, 2 retries). **Free tier**
(Groq) is deliberately tighter — smaller token budgets, one search query,
one draft pass, one retry — so a free account's usage stays low without the
workflow silently producing a worse-structured post.

Errors from any provider (missing/invalid key, rate limit, context-window
overflow, unavailable model, transient outage) are normalized into a common
set of exceptions (`providers/errors.py`) before they ever reach the UI, so
`app.py` always shows a clean, actionable message — never a raw traceback or
a provider-specific error string.

### Adding a new provider

1. Add a `providers/<name>_provider.py` implementing `ProviderAdapter`
   (`build_chat_model()`, `structured_output_method()`, `normalize_error()`)
   — see `providers/groq_provider.py` for the shortest example.
2. Register it in `providers/__init__.py`'s `_ADAPTERS` dict.
3. Add its models to `config/models.py`'s `MODEL_REGISTRY`.

`nodes.py` and `graph.py` never need to change — they only ever call
`llm.invoke_structured()`, which dispatches through the registry above.

---

## 🧩 Tech stack

| Component | Library |
|-----------|---------|
| Agent framework | `langgraph` |
| LLM providers | `langchain-anthropic`, `langchain-openai`, `langchain-groq` (dispatched via `providers/`) |
| Web search | DuckDuckGo via `ddgs` (no API key) |
| Structured output | `pydantic` v2 |
| Persistence | `MemorySaver` (built-in) |
| UI | `streamlit` |
| Testing | `pytest` (mocked provider SDKs, no real API keys needed) |

---

## 📁 Project structure

```
BlogForge/
├── app.py            # Streamlit UI (provider/model/key sidebar, phases)
├── graph.py           # StateGraph, edges, routing, compile(MemorySaver)
├── nodes.py           # The 7 node functions (provider-agnostic)
├── state.py           # BlogState TypedDict + reducer
├── models.py          # Pydantic models (structured output)
├── tools.py           # DuckDuckGo search + custom SEO scorer
├── prompts.py         # Prompt builders per node
├── llm.py             # Provider-agnostic LLM facade (get_llm / invoke_structured)
├── config/
│   ├── models.py       # Provider/model registry
│   └── plans.py        # FREE vs PAID usage-tier budgets
├── providers/
│   ├── base.py          # ProviderAdapter interface
│   ├── errors.py         # Normalized, user-safe LLM error hierarchy
│   ├── anthropic_provider.py
│   ├── openai_provider.py
│   └── groq_provider.py
├── tests/              # pytest suite (mocked provider SDKs)
├── agent.ipynb        # Notebook with draw_mermaid_png() + full run
├── flowchart/         # Graph diagram (PNG)
├── slides/            # Presentation slides
├── requirements.txt
├── .env.example       # Template (never commit the real .env)
└── README.md
```

## 🔐 API key note

Never commit your real key. `.env` is git-ignored; only `.env.example` is
tracked. Keys entered in the Streamlit sidebar live only in that session's
`session_state` (masked as you type) and are never written to disk or logged.

## 🧪 Testing

```bash
pytest tests/ -v
```

The suite covers the model registry, plan budgets, per-provider error
normalization, the LLM factory's provider dispatch and bounded retry
behavior, and the graph's plan-aware conditional routing — all with mocked
provider SDKs, so no real API keys are required to run it.
