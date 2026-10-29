# 📄 AI ATS Resume Checker

Upload a resume (PDF, DOCX or TXT) and get an **ATS score**, a category breakdown and
**specific, prioritised improvements**. Built with [Streamlit](https://streamlit.io) and
[Groq](https://groq.com).

## Features

- Reads PDF, DOCX (including tables) and TXT resumes
- **Overall ATS score (0-100)** = 40% rule-based checks + 60% AI evaluation
- Rule-based checks: contact info, standard sections, length, action verbs, quantified results, bullets
- AI category scores, strengths, weaknesses, and rewrite suggestions with example bullets
- Optional **job description** matching: matched and missing keywords
- Downloadable text report

## Project structure

```
app.py            # the whole app
requirements.txt  # Python dependencies
README.md
.gitignore        # keeps secrets out of Git
```

## Run locally

1. Install Python 3.10+.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Get a free API key at <https://console.groq.com/keys>.
4. Provide the key in **one** of these ways:
   - Paste it into the sidebar when the app is running (simplest), or
   - Set an environment variable: `export GROQ_API_KEY="gsk_..."` (Windows PowerShell: `$env:GROQ_API_KEY="gsk_..."`), or
   - Create `.streamlit/secrets.toml` containing `GROQ_API_KEY = "gsk_..."`
5. Start the app:
   ```bash
   streamlit run app.py
   ```

## Push to GitHub (using the website, no Git needed)

1. Sign in at <https://github.com> and click **+** (top right) → **New repository**.
2. Name it (e.g. `ats-resume-checker`), choose **Public**, and click **Create repository**.
3. On the empty repo page click **uploading an existing file**.
4. Drag in `app.py`, `requirements.txt`, `README.md` and `.gitignore`.
5. Scroll down and click **Commit changes**.

> Never upload a `secrets.toml` file or paste your API key into any file in the repo.

## Deploy on Streamlit Community Cloud (free)

1. Go to <https://share.streamlit.io> and sign in with GitHub (authorise access to your repos if asked).
2. Click **Create app** → **Deploy a public app from GitHub**.
3. Choose your repository, branch `main`, and main file path `app.py`.
4. Click **Advanced settings** and, in the **Secrets** box, add:
   ```toml
   GROQ_API_KEY = "gsk_your_key_here"
   ```
   Pick Python 3.11 or 3.12 if it asks.
5. Click **Deploy**. The first build takes a few minutes; you then get a public `*.streamlit.app` URL.

To update the app later, edit the file on GitHub (pencil icon → **Commit changes**). Streamlit redeploys automatically.
To change the key later: app **⋮ menu → Settings → Secrets**.

## How the score works

| Part | Weight | What it measures |
|------|--------|------------------|
| Rule-based | 40% | Email/phone/links, sections, length (300-900 words), action verbs, metrics, bullets |
| AI evaluation | 60% | Structure, keywords, impact, education, readability |

Adjust `RULE_WEIGHT` and `AI_WEIGHT` at the top of `app.py` if you want a different blend.

## Models

Groq retires models from time to time. The app defaults to `openai/gpt-oss-120b` with
`openai/gpt-oss-20b` as a faster option. If you see "model unavailable", enter a current model ID in the
**Custom model ID** field in the sidebar (see <https://console.groq.com/docs/models>) or edit
`MODEL_OPTIONS` in `app.py`.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "API key was rejected" | Re-copy the key from console.groq.com; remove spaces |
| "Rate limit reached" | Wait a minute and retry (free tier limits) |
| "Very little text could be extracted" | The PDF is probably a scanned image. Export a text-based PDF or use DOCX |
| "Model is unavailable" | Choose another model or type a custom model ID |
| Deployed app says no API key | Add `GROQ_API_KEY` in the app's **Settings → Secrets** |

## Limitations and privacy

- This is an estimate. Real ATS products (Workday, Greenhouse, Lever...) differ and don't publish their scoring.
- Resume text is sent to Groq for analysis. Don't upload documents you aren't comfortable sharing.
- AI suggestions can be wrong: review them before changing your resume, and never add experience you don't have.
