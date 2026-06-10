"""Presentation layer for BlogForge — CSS theme + reusable HTML components.

Keeps app.py focused on flow/state while this module owns the look & feel.
All components return HTML strings to be rendered with
`st.markdown(..., unsafe_allow_html=True)`.
"""
import html

# Pipeline steps: (state-key, label, icon)
STEPS = [
    ("research", "Research", "🔎"),
    ("outline", "Outline", "🗂"),
    ("draft", "Draft", "✍️"),
    ("seo", "SEO", "🚀"),
    ("quality_check", "Quality", "✅"),
    ("human_review", "Review", "👀"),
    ("publish", "Publish", "📦"),
]
NEXT = {k: STEPS[i + 1][0] for i, (k, _, _) in enumerate(STEPS[:-1])}


def inject_css() -> str:
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&display=swap');

:root {
  --bf-primary:#6d5efc; --bf-primary2:#9b8bff; --bf-ink:#1b1f2a;
  --bf-muted:#6b7280; --bf-line:#e9eaf3; --bf-bg:#f5f6fb; --bf-card:#ffffff;
  --bf-good:#16a34a; --bf-ok:#f59e0b; --bf-bad:#ef4444;
  --bf-shadow:0 10px 30px -12px rgba(40,33,120,.25);
}

html, body, [class*="css"], .stApp { font-family:'Inter',system-ui,sans-serif; }
.stApp { background:
   radial-gradient(1200px 500px at 10% -10%, #ece9ff 0%, rgba(236,233,255,0) 55%),
   radial-gradient(1000px 500px at 110% 0%, #e6f0ff 0%, rgba(230,240,255,0) 50%),
   var(--bf-bg); }

/* hide default chrome for an app-like feel */
#MainMenu, [data-testid="stToolbar"], footer { visibility:hidden; height:0; }
header[data-testid="stHeader"] { background:transparent; }
.block-container { padding-top:1.6rem; padding-bottom:4rem; max-width:1080px; }

/* ---- top brand bar ---- */
.bf-topbar { display:flex; align-items:center; justify-content:space-between; margin-bottom:1.2rem; }
.bf-brand { display:flex; align-items:center; gap:.6rem; font-weight:800; font-size:1.15rem; color:var(--bf-ink); }
.bf-logo { width:34px; height:34px; border-radius:10px; display:grid; place-items:center;
  background:linear-gradient(135deg,var(--bf-primary),var(--bf-primary2)); color:#fff; font-size:1.1rem;
  box-shadow:var(--bf-shadow); }
.bf-tag { font-size:.72rem; font-weight:600; color:var(--bf-primary); background:#efecff;
  padding:.28rem .6rem; border-radius:999px; border:1px solid #e0dbff; }

/* ---- hero ---- */
.bf-hero { text-align:center; padding:1.4rem 0 .4rem; }
.bf-hero h1 { font-family:'Fraunces',serif; font-weight:600; font-size:3rem; line-height:1.05;
  margin:0 0 .5rem; color:var(--bf-ink); letter-spacing:-.02em; }
.bf-hero h1 .grad { background:linear-gradient(120deg,var(--bf-primary),#b06bff 60%,#5b8def);
  -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; }
.bf-hero p { color:var(--bf-muted); font-size:1.06rem; max-width:560px; margin:0 auto; }
.bf-chips { display:flex; gap:.5rem; justify-content:center; flex-wrap:wrap; margin:1rem 0 .2rem; }
.bf-chip { font-size:.78rem; color:#444; background:#fff; border:1px solid var(--bf-line);
  padding:.4rem .75rem; border-radius:999px; box-shadow:0 2px 8px -6px rgba(0,0,0,.2); }
.bf-chip b { color:var(--bf-primary); }

/* ---- cards (bordered containers) ---- */
div[data-testid="stVerticalBlockBorderWrapper"] {
  background:var(--bf-card); border:1px solid var(--bf-line)!important; border-radius:18px!important;
  box-shadow:var(--bf-shadow); padding:.4rem .25rem; }

/* ---- section heading ---- */
.bf-sec { display:flex; align-items:center; gap:.55rem; font-weight:700; font-size:1.15rem;
  color:var(--bf-ink); margin:.2rem 0 .9rem; }
.bf-sec .bf-ico { width:30px;height:30px;border-radius:9px;display:grid;place-items:center;
  background:#efecff; }

/* ---- stepper ---- */
.bf-stepper { display:flex; align-items:flex-start; justify-content:space-between; margin:.4rem .2rem 0; }
.bf-step { display:flex; flex-direction:column; align-items:center; gap:.4rem; width:62px; text-align:center; }
.bf-dot { width:44px; height:44px; border-radius:50%; display:grid; place-items:center; font-size:1.05rem;
  background:#fff; border:2px solid var(--bf-line); color:var(--bf-muted); transition:all .25s; }
.bf-step .bf-tx { font-size:.72rem; font-weight:600; color:var(--bf-muted); }
.bf-step.done .bf-dot { background:linear-gradient(135deg,var(--bf-primary),var(--bf-primary2));
  border-color:transparent; color:#fff; box-shadow:0 6px 16px -6px rgba(109,94,252,.6); }
.bf-step.done .bf-tx { color:var(--bf-ink); }
.bf-step.active .bf-dot { border-color:var(--bf-primary); color:var(--bf-primary);
  animation:bf-pulse 1.2s infinite; }
.bf-step.active .bf-tx { color:var(--bf-primary); }
.bf-conn { flex:1; height:3px; border-radius:3px; background:var(--bf-line); margin-top:21px; }
.bf-conn.done { background:linear-gradient(90deg,var(--bf-primary),var(--bf-primary2)); }
@keyframes bf-pulse { 0%{box-shadow:0 0 0 0 rgba(109,94,252,.4);} 70%{box-shadow:0 0 0 8px rgba(109,94,252,0);} 100%{box-shadow:0 0 0 0 rgba(109,94,252,0);} }

/* ---- metric cards ---- */
.bf-metrics { display:grid; grid-template-columns:repeat(4,1fr); gap:.7rem; margin:.2rem 0 1rem; }
.bf-metric { background:#fff; border:1px solid var(--bf-line); border-radius:14px; padding:.85rem 1rem; }
.bf-metric .v { font-size:1.5rem; font-weight:800; color:var(--bf-ink); line-height:1; }
.bf-metric .l { font-size:.74rem; font-weight:600; color:var(--bf-muted); margin-top:.35rem;
  text-transform:uppercase; letter-spacing:.04em; }
.bf-metric .v.good{color:var(--bf-good);} .bf-metric .v.ok{color:var(--bf-ok);} .bf-metric .v.bad{color:var(--bf-bad);}

/* ---- pill / badge ---- */
.bf-pill { display:inline-flex; align-items:center; gap:.4rem; font-size:.82rem; font-weight:700;
  padding:.4rem .8rem; border-radius:999px; }
.bf-pill.good{background:#e8f7ee;color:#13853c;} .bf-pill.ok{background:#fef3e2;color:#b9770b;}
.bf-pill.bad{background:#fdeaea;color:#c62828;}

/* keyword tags */
.bf-kw { display:flex; gap:.4rem; flex-wrap:wrap; margin:.5rem 0; }
.bf-kw span { font-size:.74rem; background:#f1f0fb; color:#5a4fd0; border:1px solid #e6e3fb;
  padding:.28rem .6rem; border-radius:8px; }

/* ---- buttons ---- */
.stButton>button, .stDownloadButton>button, .stFormSubmitButton>button {
  border-radius:11px; font-weight:600; border:1px solid var(--bf-line); padding:.55rem 1rem;
  transition:transform .12s ease, box-shadow .2s ease; }
.stButton>button:hover, .stDownloadButton>button:hover, .stFormSubmitButton>button:hover {
  transform:translateY(-1px); }
.stButton>button[kind="primary"], .stDownloadButton>button, .stFormSubmitButton>button {
  background:linear-gradient(135deg,var(--bf-primary),var(--bf-primary2)); color:#fff; border:none;
  box-shadow:0 10px 22px -10px rgba(109,94,252,.7); }
.stButton>button[kind="primary"]:hover, .stDownloadButton>button:hover, .stFormSubmitButton>button:hover {
  box-shadow:0 14px 26px -10px rgba(109,94,252,.85); }

/* ---- inputs ---- */
.stTextInput>div>div>input, .stTextArea textarea {
  border-radius:11px!important; border:1px solid var(--bf-line)!important; }
.stTextInput>div>div>input:focus, .stTextArea textarea:focus {
  border-color:var(--bf-primary)!important; box-shadow:0 0 0 3px rgba(109,94,252,.15)!important; }

/* article preview typography */
.bf-article h1,.bf-article h2 { font-family:'Fraunces',serif; }

/* sidebar */
section[data-testid="stSidebar"] { background:#ffffffcc; backdrop-filter:blur(6px); border-right:1px solid var(--bf-line); }
section[data-testid="stSidebar"] .bf-side-title { font-weight:800; font-size:1.05rem; display:flex; gap:.5rem; align-items:center; }

/* footer note */
.bf-foot { text-align:center; color:#9aa0ad; font-size:.78rem; margin-top:2rem; }
</style>
"""


def topbar() -> str:
    return """
<div class="bf-topbar">
  <div class="bf-brand"><span class="bf-logo">📝</span> BlogForge</div>
  <span class="bf-tag">⚡ Groq · LangGraph</span>
</div>
"""


def hero() -> str:
    return """
<div class="bf-hero">
  <h1>Turn a topic into a<br><span class="grad">publish-ready blog post</span></h1>
  <p>An autonomous AI writer that researches, drafts, optimizes SEO,
     scores its own work, and waits for your approval.</p>
  <div class="bf-chips">
    <div class="bf-chip">🔎 <b>Live research</b></div>
    <div class="bf-chip">🔁 <b>Self-correcting</b></div>
    <div class="bf-chip">👀 <b>Human-in-the-loop</b></div>
    <div class="bf-chip">🚀 <b>SEO optimized</b></div>
  </div>
</div>
"""


def section(title: str, icon: str = "•") -> str:
    return f'<div class="bf-sec"><span class="bf-ico">{icon}</span>{html.escape(title)}</div>'


def stepper(done: set, active: str | None = None) -> str:
    parts = []
    for i, (key, label, icon) in enumerate(STEPS):
        if key in done:
            cls, mark = "done", "✓"
        elif key == active:
            cls, mark = "active", icon
        else:
            cls, mark = "", icon
        parts.append(
            f'<div class="bf-step {cls}"><div class="bf-dot">{mark}</div>'
            f'<div class="bf-tx">{label}</div></div>'
        )
        if i < len(STEPS) - 1:
            parts.append(f'<div class="bf-conn {"done" if key in done else ""}"></div>')
    return f'<div class="bf-stepper">{"".join(parts)}</div>'


def _grade(score):
    if score is None:
        return "", "—"
    if score >= 80:
        return "good", "Excellent"
    if score >= 60:
        return "ok", "Good"
    return "bad", "Needs work"


def quality_pill(score) -> str:
    cls, word = _grade(score)
    s = "—" if score is None else f"{score}/100"
    return f'<span class="bf-pill {cls}">★ Quality {s} · {word}</span>'


def metrics(quality, revisions, words, seo_score) -> str:
    qcls, _ = _grade(quality)
    scls, _ = _grade(seo_score)
    cells = [
        (f'<span class="{qcls}">{quality if quality is not None else "—"}</span>', "Quality score"),
        (revisions if revisions is not None else "—", "Revisions"),
        (words if words else "—", "Words"),
        (f'<span class="{scls}">{seo_score if seo_score is not None else "—"}</span>', "SEO score"),
    ]
    body = "".join(f'<div class="bf-metric"><div class="v">{v}</div><div class="l">{l}</div></div>'
                   for v, l in cells)
    return f'<div class="bf-metrics">{body}</div>'


def keyword_tags(keywords) -> str:
    if not keywords:
        return ""
    tags = "".join(f"<span>{html.escape(str(k))}</span>" for k in keywords)
    return f'<div class="bf-kw">{tags}</div>'


def footer() -> str:
    return ('<div class="bf-foot">Built with LangGraph · '
            'Iterative + Conditional workflow · MemorySaver persistence</div>')
