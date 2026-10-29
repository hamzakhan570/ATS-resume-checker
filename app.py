import io
import json
import os
import re

import streamlit as st
from groq import Groq
from pypdf import PdfReader

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
# Groq retires models regularly (llama-3.3-70b-versatile and llama-3.1-8b-instant were
# shut down for free/developer accounts on 16 Aug 2026). If a model stops working, pick
# another one in the sidebar, type a custom model ID, or update this list.
# Current list: https://console.groq.com/docs/models
DEFAULT_MODEL = "openai/gpt-oss-120b"
MODEL_OPTIONS = [
    "openai/gpt-oss-120b",  # best quality
    "openai/gpt-oss-20b",   # faster / cheaper
]
MAX_RESUME_CHARS = 12000  # keep prompts well within the model's context window
MAX_JD_CHARS = 6000
MIN_TEXT_CHARS = 150  # below this we assume the file is scanned / unreadable

# Weight of the rule-based score vs the AI score in the final result
RULE_WEIGHT = 0.4
AI_WEIGHT = 0.6

SECTION_PATTERNS = {
    "Experience": r"\b(work experience|professional experience|experience|employment history|work history)\b",
    "Education": r"\b(education|academic background|qualifications)\b",
    "Skills": r"\b(skills|technical skills|core competencies|technologies)\b",
    "Summary": r"\b(summary|professional summary|profile|objective|about me)\b",
    "Projects": r"\b(projects|personal projects|key projects)\b",
}

ACTION_VERBS = {
    "led", "managed", "developed", "built", "created", "designed", "implemented",
    "improved", "increased", "reduced", "launched", "delivered", "optimized",
    "optimised", "automated", "analyzed", "analysed", "engineered", "architected",
    "achieved", "streamlined", "coordinated", "mentored", "negotiated", "drove",
    "established", "spearheaded", "deployed", "migrated", "trained", "generated",
}


# ----------------------------------------------------------------------------
# File parsing
# ----------------------------------------------------------------------------
def extract_text(file_name: str, data: bytes) -> str:
    """Extract plain text from PDF, DOCX or TXT bytes."""
    ext = os.path.splitext(file_name.lower())[1]

    if ext == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                raise ValueError("This PDF is password protected.")
        pages = [(page.extract_text() or "") for page in reader.pages]
        return "\n".join(pages).strip()

    if ext == ".docx":
        doc = Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        # Resumes often use tables for layout; include their text too.
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        parts.append(cell.text.strip())
        return "\n".join(parts).strip()

    if ext == ".txt":
        return data.decode("utf-8", errors="ignore").strip()

    raise ValueError(f"Unsupported file type: {ext or 'unknown'}")


# ----------------------------------------------------------------------------
# Rule-based ATS checks
# ----------------------------------------------------------------------------
def rule_based_checks(text: str) -> dict:
    """Deterministic checks. Each check records points earned and points possible."""
    lowered = text.lower()
    words = re.findall(r"\b\w+\b", text)
    word_count = len(words)
    checks = []  # dicts: label, earned, max, detail

    def add(label, earned, maximum, detail):
        checks.append({"label": label, "earned": earned, "max": maximum, "detail": detail})

    # Contact info (20 pts)
    has_email = bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text))
    has_phone = bool(re.search(r"\+?\d[\d\s().-]{8,}\d", text))
    has_link = bool(re.search(r"(linkedin\.com|github\.com|portfolio|https?://)", lowered))
    add("Email address", 8 if has_email else 0, 8,
        "Found." if has_email else "Include a professional email address.")
    add("Phone number", 7 if has_phone else 0, 7,
        "Found." if has_phone else "Add a phone number.")
    add("LinkedIn / GitHub / portfolio link", 5 if has_link else 0, 5,
        "Found." if has_link else "Add a LinkedIn or portfolio link.")

    # Standard sections (30 pts)
    section_points = {"Experience": 10, "Education": 8, "Skills": 8, "Summary": 2, "Projects": 2}
    for name, pattern in SECTION_PATTERNS.items():
        found = bool(re.search(pattern, lowered))
        pts = section_points[name]
        add(f"{name} section", pts if found else 0, pts,
            "Found." if found else f"Add a clearly labelled {name} section.")

    # Length (15 pts)
    if 300 <= word_count <= 900:
        add("Resume length", 15, 15, f"{word_count} words - good length.")
    elif 200 <= word_count < 300 or 900 < word_count <= 1200:
        add("Resume length", 8, 15, f"{word_count} words - slightly outside the ideal 300-900 range.")
    else:
        add("Resume length", 0, 15, f"{word_count} words - aim for 300-900 words (1-2 pages).")

    # Action verbs (10 pts)
    verb_hits = sum(1 for w in words if w.lower() in ACTION_VERBS)
    verb_pts = 10 if verb_hits >= 8 else (5 if verb_hits >= 4 else 0)
    add("Strong action verbs", verb_pts, 10,
        f"{verb_hits} action verbs found." + ("" if verb_pts == 10 else " Start bullets with verbs like 'Led', 'Built', 'Reduced'."))

    # Quantified achievements (15 pts)
    numbers = re.findall(r"\b\d+(?:[.,]\d+)?\s?(?:%|\+|k\b|m\b|x\b)|\$\s?\d[\d,.]*", text)
    num_pts = 15 if len(numbers) >= 6 else (8 if len(numbers) >= 3 else 0)
    add("Quantified achievements", num_pts, 15,
        f"{len(numbers)} metrics found (%, $, multipliers)." + ("" if num_pts == 15 else " Add more measurable results."))

    # Bullet usage (10 pts)
    bullet_lines = len(re.findall(r"(?m)^\s*[-•*▪●◦‣·]", text))
    bullet_pts = 10 if bullet_lines >= 5 else (5 if bullet_lines >= 2 else 0)
    add("Bullet-point formatting", bullet_pts, 10,
        f"{bullet_lines} bullet lines detected." + ("" if bullet_pts == 10 else " Use bullet points for achievements."))

    total_max = sum(c["max"] for c in checks)
    total_earned = sum(c["earned"] for c in checks)
    return {"score": round(100 * total_earned / total_max), "checks": checks, "word_count": word_count}


# ----------------------------------------------------------------------------
# Groq / AI analysis
# ----------------------------------------------------------------------------
SYSTEM_PROMPT = """You are an expert ATS (Applicant Tracking System) analyst and professional resume coach.
Evaluate the resume text provided and respond with ONLY a valid JSON object using exactly this schema:
{
  "ai_score": <integer 0-100>,
  "category_scores": {
    "formatting_and_structure": <integer 0-100>,
    "keywords_and_skills": <integer 0-100>,
    "experience_and_impact": <integer 0-100>,
    "education_and_credentials": <integer 0-100>,
    "readability_and_clarity": <integer 0-100>
  },
  "summary": "<2-3 sentence overall assessment>",
  "strengths": ["<short point>", "..."],
  "weaknesses": ["<short point>", "..."],
  "improvements": [
    {"priority": "High|Medium|Low", "issue": "<what is wrong>", "suggestion": "<specific fix>", "example": "<optional rewritten example bullet, or empty string>"}
  ],
  "missing_keywords": ["<keyword>", "..."],
  "job_match": {"score": <integer 0-100 or null>, "matched_keywords": ["..."], "missing_keywords": ["..."]}
}
Rules:
- Be honest and strict; do not inflate scores. Typical average resumes score 55-70.
- Give 5-8 improvements, ordered by priority. Reference real content from the resume.
- If no job description is provided, set job_match to {"score": null, "matched_keywords": [], "missing_keywords": []}
  and put generally expected industry keywords in missing_keywords.
- Never invent experience the candidate does not have in rewritten examples; use placeholders like [X%] where numbers are unknown.
- Output JSON only. No markdown, no commentary."""


def _clamp(value, default=0) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def parse_ai_json(raw: str) -> dict:
    """Parse model output into JSON, tolerating code fences or stray text."""
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError("The AI returned an unreadable response. Please try again.")


def normalise_ai_result(data: dict) -> dict:
    """Make sure every field we render exists and has the right type."""
    if not isinstance(data, dict):
        raise ValueError("The AI returned an unexpected response format.")

    cats = data.get("category_scores") if isinstance(data.get("category_scores"), dict) else {}
    category_keys = [
        "formatting_and_structure", "keywords_and_skills", "experience_and_impact",
        "education_and_credentials", "readability_and_clarity",
    ]
    improvements = []
    for item in _as_list(data.get("improvements")):
        if isinstance(item, dict):
            priority = str(item.get("priority", "Medium")).title()
            if priority not in ("High", "Medium", "Low"):
                priority = "Medium"
            improvements.append({
                "priority": priority,
                "issue": str(item.get("issue", "")).strip(),
                "suggestion": str(item.get("suggestion", "")).strip(),
                "example": str(item.get("example", "") or "").strip(),
            })
        elif isinstance(item, str):
            improvements.append({"priority": "Medium", "issue": "", "suggestion": item, "example": ""})

    jm = data.get("job_match") if isinstance(data.get("job_match"), dict) else {}
    job_score = jm.get("score")
    return {
        "ai_score": _clamp(data.get("ai_score")),
        "category_scores": {k: _clamp(cats.get(k)) for k in category_keys},
        "summary": str(data.get("summary", "")).strip(),
        "strengths": [str(s) for s in _as_list(data.get("strengths"))],
        "weaknesses": [str(s) for s in _as_list(data.get("weaknesses"))],
        "improvements": improvements,
        "missing_keywords": [str(s) for s in _as_list(data.get("missing_keywords"))],
        "job_match": {
            "score": None if job_score is None else _clamp(job_score),
            "matched_keywords": [str(s) for s in _as_list(jm.get("matched_keywords"))],
            "missing_keywords": [str(s) for s in _as_list(jm.get("missing_keywords"))],
        },
    }


def analyze_with_groq(api_key: str, model: str, resume_text: str, job_description: str = "") -> dict:
    """Call Groq and return a normalised analysis dict."""
    client = Groq(api_key=api_key)
    user_content = f"RESUME:\n\"\"\"\n{resume_text[:MAX_RESUME_CHARS]}\n\"\"\""
    if job_description.strip():
        user_content += f"\n\nJOB DESCRIPTION:\n\"\"\"\n{job_description.strip()[:MAX_JD_CHARS]}\n\"\"\""
    else:
        user_content += "\n\nJOB DESCRIPTION: (none provided)"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    # gpt-oss models are reasoning models: reasoning tokens count toward the output
    # limit, so leave plenty of room and keep reasoning short.
    params = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_completion_tokens": 6000,
        "response_format": {"type": "json_object"},
    }
    if "gpt-oss" in model:
        params["reasoning_effort"] = "low"

    try:
        response = client.chat.completions.create(**params)
    except Exception as exc:
        low = str(exc).lower()
        fatal = any(k in low for k in ("401", "429", "invalid api key", "rate limit", "connection",
                                       "timeout", "decommissioned", "not found", "does not exist"))
        if fatal:
            raise
        # Probably an optional parameter this model rejects: retry with a plain request.
        # parse_ai_json() copes with fenced or chatty output.
        response = client.chat.completions.create(
            model=model, messages=messages, temperature=0.2, max_completion_tokens=6000
        )
    raw = response.choices[0].message.content
    return normalise_ai_result(parse_ai_json(raw))


def friendly_error(exc: Exception) -> str:
    """Turn API errors into messages a user can act on."""
    msg = str(exc)
    low = msg.lower()
    if "401" in msg or "invalid api key" in low or "authentication" in low:
        return "Your Groq API key was rejected. Please check it and try again."
    if "429" in msg or "rate limit" in low:
        return "Groq rate limit reached. Wait a minute and try again."
    if "model" in low and ("not found" in low or "decommissioned" in low or "does not exist" in low):
        return "The selected model is unavailable. Pick another model in the sidebar."
    if "connection" in low or "timeout" in low:
        return "Could not reach Groq. Check your internet connection and try again."
    return f"Something went wrong: {msg}"


def final_score(rule_score: int, ai_score: int) -> int:
    return round(RULE_WEIGHT * rule_score + AI_WEIGHT * ai_score)


def score_label(score: int):
    if score >= 80:
        return "Excellent", "green"
    if score >= 65:
        return "Good", "orange"
    if score >= 50:
        return "Needs work", "orange"
    return "Poor", "red"


def build_report(file_name, final, rule, ai) -> str:
    """Plain-text report for download."""
    lines = [f"ATS RESUME REPORT - {file_name}", "=" * 50,
             f"Overall ATS score: {final}/100",
             f"  Rule-based score: {rule['score']}/100",
             f"  AI score: {ai['ai_score']}/100", "", "SUMMARY", ai["summary"], ""]
    lines.append("CATEGORY SCORES")
    for k, v in ai["category_scores"].items():
        lines.append(f"  - {k.replace('_', ' ').title()}: {v}/100")
    lines += ["", "STRENGTHS"] + [f"  + {s}" for s in ai["strengths"]]
    lines += ["", "WEAKNESSES"] + [f"  - {s}" for s in ai["weaknesses"]]
    lines += ["", "IMPROVEMENTS"]
    for i, imp in enumerate(ai["improvements"], 1):
        lines.append(f"{i}. [{imp['priority']}] {imp['issue']}")
        lines.append(f"   Fix: {imp['suggestion']}")
        if imp["example"]:
            lines.append(f"   Example: {imp['example']}")
    lines += ["", "MISSING KEYWORDS: " + ", ".join(ai["missing_keywords"])]
    jm = ai["job_match"]
    if jm["score"] is not None:
        lines += ["", f"JOB MATCH: {jm['score']}/100",
                  "  Matched: " + ", ".join(jm["matched_keywords"]),
                  "  Missing: " + ", ".join(jm["missing_keywords"])]
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------
def get_api_key(sidebar_value: str) -> str:
    if sidebar_value.strip():
        return sidebar_value.strip()
    try:
        if "GROQ_API_KEY" in st.secrets:
            return str(st.secrets["GROQ_API_KEY"]).strip()
    except Exception:
        pass
    return os.environ.get("GROQ_API_KEY", "").strip()


def render_results(file_name, rule, ai):
    final = final_score(rule["score"], ai["ai_score"])
    label, color = score_label(final)

    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Overall ATS score", f"{final}/100")
    c2.metric("Rule-based score", f"{rule['score']}/100")
    c3.metric("AI score", f"{ai['ai_score']}/100")
    st.progress(final / 100)
    st.markdown(f"**Verdict:** :{color}[{label}]")
    if ai["summary"]:
        st.info(ai["summary"])

    tab_cat, tab_imp, tab_kw, tab_checks = st.tabs(
        ["Category scores", "Improvements", "Keywords", "Formatting checks"]
    )

    with tab_cat:
        for key, val in ai["category_scores"].items():
            st.write(f"**{key.replace('_', ' ').title()}** - {val}/100")
            st.progress(val / 100)
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Strengths")
            for s in ai["strengths"] or ["No strengths reported."]:
                st.markdown(f"- {s}")
        with col_b:
            st.subheader("Weaknesses")
            for s in ai["weaknesses"] or ["No weaknesses reported."]:
                st.markdown(f"- {s}")

    with tab_imp:
        order = {"High": 0, "Medium": 1, "Low": 2}
        items = sorted(ai["improvements"], key=lambda x: order[x["priority"]])
        if not items:
            st.write("No improvements returned.")
        icons = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}
        for imp in items:
            title = imp["issue"] or imp["suggestion"][:60]
            with st.expander(f"{icons[imp['priority']]} {imp['priority']}: {title}", expanded=imp["priority"] == "High"):
                if imp["suggestion"]:
                    st.markdown(f"**How to fix:** {imp['suggestion']}")
                if imp["example"]:
                    st.markdown(f"**Example:** _{imp['example']}_")

    with tab_kw:
        jm = ai["job_match"]
        if jm["score"] is not None:
            st.metric("Job description match", f"{jm['score']}/100")
            st.markdown("**Matched keywords:** " + (", ".join(jm["matched_keywords"]) or "none"))
            st.markdown("**Missing keywords:** " + (", ".join(jm["missing_keywords"]) or "none"))
        else:
            st.caption("Paste a job description in the sidebar to get a tailored keyword match.")
        st.markdown("**Suggested keywords to consider:** " + (", ".join(ai["missing_keywords"]) or "none"))

    with tab_checks:
        for chk in rule["checks"]:
            icon = "✅" if chk["earned"] == chk["max"] else ("🟡" if chk["earned"] > 0 else "❌")
            st.markdown(f"{icon} **{chk['label']}** ({chk['earned']}/{chk['max']}) - {chk['detail']}")

    st.download_button(
        "Download report (.txt)",
        data=build_report(file_name, final, rule, ai),
        file_name="ats_report.txt",
        mime="text/plain",
    )


def main():
    st.set_page_config(page_title="AI ATS Resume Checker", page_icon="📄", layout="wide")
    st.title("📄 AI ATS Resume Checker")
    st.caption("Upload your resume to get an ATS score and specific suggestions to improve it.")

    with st.sidebar:
        st.header("Settings")
        key_input = st.text_input("Groq API key", type="password",
                                  help="Get a free key at console.groq.com. Not stored anywhere.")
        model = st.selectbox("Model", MODEL_OPTIONS, index=MODEL_OPTIONS.index(DEFAULT_MODEL))
        custom_model = st.text_input("Custom model ID (optional)", placeholder="e.g. a newer Groq model",
                                     help="Overrides the model above. Useful if Groq retires a model.")
        if custom_model.strip():
            model = custom_model.strip()
        st.markdown("---")
        job_description = st.text_area("Job description (optional)", height=220,
                                       placeholder="Paste a job posting to check keyword match...")
        st.caption("Your resume text is sent to Groq for analysis. Don't upload anything you aren't comfortable sharing.")

    uploaded = st.file_uploader("Upload resume", type=["pdf", "docx", "txt"])

    if st.button("Analyze resume", type="primary", disabled=uploaded is None):
        api_key = get_api_key(key_input)
        if not api_key:
            st.error("Please enter your Groq API key in the sidebar (or set GROQ_API_KEY).")
            st.stop()

        try:
            with st.spinner("Reading your resume..."):
                text = extract_text(uploaded.name, uploaded.getvalue())
        except Exception as exc:
            st.error(f"Could not read the file: {exc}")
            st.stop()

        if len(text) < MIN_TEXT_CHARS:
            st.error("Very little text could be extracted. If your resume is a scanned image, "
                     "ATS systems can't read it either - export a text-based PDF or DOCX instead.")
            st.stop()

        rule = rule_based_checks(text)

        try:
            with st.spinner("Analyzing with AI..."):
                ai = analyze_with_groq(api_key, model, text, job_description)
        except Exception as exc:
            st.error(friendly_error(exc))
            st.stop()

        st.session_state["result"] = (uploaded.name, rule, ai)

    if "result" in st.session_state:
        name, rule, ai = st.session_state["result"]
        render_results(name, rule, ai)


if __name__ == "__main__":
    main()
