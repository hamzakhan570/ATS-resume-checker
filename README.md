# ATS-resume-checker
ATS Resume Analyzer (Streamlit + Groq)
A small Streamlit app that accepts PDF, DOCX, and TXT resumes, calculates a transparent heuristic ATS-style score, and asks a Groq-hosted language model for prioritized resume improvements.
Important: This is not an actual ATS score and cannot predict a specific employer's screening result. The score is a lightweight rubric based on resume sections, contact details, length, achievement language/metrics, and (when provided) job-description keyword overlap.

Features
- PDF, DOCX, and TXT text extraction (8 MB upload limit).
- Optional job description for keyword alignment.
- Explainable score breakdown and missing-section checks.
- AI-generated improvement plan and downloadable Markdown report.
- Uses environment variables or Streamlit Secrets for the Groq API key; the key is not hard-coded.
- Does not write uploaded resumes to disk or a database.
Project files
ats-resume-analyzer/
├── app.py
├── requirements.txt
└── README.md
Run locally
1. Install Python 3.10 or newer.
2. Download/clone this repository and open a terminal in its folder.
3. Create and activate a virtual environment (recommended):
   Windows PowerShell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   macOS/Linux
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
4. Create a Groq API key in the Groq Console. Keep it private.
5. Set the key in your terminal:
   Windows PowerShell
   $env:GROQ_API_KEY="paste_your_key_here"
   macOS/Linux
   export GROQ_API_KEY="paste_your_key_here"
6. Start the app:
   streamlit run app.py
The default model is llama-3.3-70b-versatile. If that model is not available for your Groq account, set GROQ_MODEL to a model ID currently supported by your account, or change the model in the app's sidebar.
Add the API key in Streamlit Community Cloud
Do not put the key in app.py, README, or a committed file.
1. Deploy the app as described below.
2. In your app workspace, open App settings (or Advanced settings during deployment).
3. In Secrets, add:
   GROQ_API_KEY = "paste_your_key_here"
4. Save/reboot the app if needed. Streamlit exposes this through st.secrets.
Optionally add GROQ_MODEL = "your-supported-model-id" to Secrets; the app's sidebar also lets you choose a model.
Push to GitHub using the website UI (no Git commands)
1. Sign in to GitHub and click + → New repository.
2. Name it ats-resume-analyzer. Choose Public or Private, then click Create repository.
3. On the empty repository page, click Add file → Create new file.
4. Name the file app.py, paste the complete contents of this project's app.py, then click Commit changes.
5. Repeat Add file → Create new file for requirements.txt and README.md, paste each file's contents, and commit each one. (Alternatively, use Add file → Upload files to upload all three files from your computer.)
6. Confirm all three files appear at the repository root. Never upload your API key or a .streamlit/secrets.toml file containing the real key.
Deploy on Streamlit Community Cloud
1. Open Streamlit Community Cloud and sign in with GitHub.
2. Click Create app and select your repository, branch (usually main), and main file path app.py.
3. Open Advanced settings and choose Python 3.11 or 3.12 if a version selector is shown.
4. In Secrets, add GROQ_API_KEY = "paste_your_key_here" as TOML, then save/deploy.
5. Wait for the build to finish. Open the app URL and test it with a non-sensitive sample resume.
6. If deployment fails, open the app's logs. Common causes are a missing/invalid API key, an unavailable model ID, or a dependency installation issue.
Official deployment guide: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
How the score works
The heuristic score is out of 100:
- Sections and structure: up to 25
- Contact details: up to 15
- Length/readability proxy: up to 15
- Achievement language and measurable results: up to 20
- Job-description keyword overlap: up to 25 when a job description is supplied; otherwise a neutral 25 points are used so general resume checks remain useful
This rubric is intentionally simple and should be treated as guidance, not a validated hiring metric. Keyword matching is literal and may miss synonyms, abbreviations, and context.
Troubleshooting
- Missing API key: set GROQ_API_KEY locally or add it in Streamlit Secrets.
- Model error: choose a model ID enabled for your Groq account in the sidebar.
- Scanned PDF: OCR it first; pypdf extracts embedded text but does not perform OCR.
- No text extracted: re-export the resume as a text-based PDF, DOCX, or TXT.
- Rate limit/network error: retry later and check your Groq account status/limits.
Privacy
When the user clicks Analyze, extracted resume text and the optional job description are sent to Groq for feedback. Do not upload confidential or sensitive personal information unless you have permission and have reviewed the provider's current terms. The app itself does not persist the uploaded file or report between sessions.
