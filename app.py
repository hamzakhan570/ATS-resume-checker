### Overall assessment
### Top 5 improvements (prioritized)
### Suggested summary rewrite
### Stronger bullet examples
### Keywords to consider (only if supported by the candidate's experience)
### Formatting and ATS tips
Keep advice actionable and avoid guaranteeing ATS outcomes. If no job description is supplied, give general resume advice.

Heuristic ATS estimate: {score}/100
Score breakdown: {json.dumps(categories)}

JOB DESCRIPTION:
{job_description[:12000] if job_description.strip() else "Not provided"}

RESUME TEXT:
{resume_text[:18000]}
"""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You provide honest, evidence-based resume feedback. Never fabricate candidate details."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_completion_tokens=1800,
    )
    result = response.choices[0].message.content
    if not result:
        raise RuntimeError("Groq returned an empty response. Please try again.")
    return result


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")
    st.title("📄 ATS Resume Analyzer")
    st.write("Upload your resume to get a transparent ATS-style estimate and practical improvement suggestions.")
    st.info("The score is a heuristic estimate, not a score from an actual Applicant Tracking System. Results depend on the job description and resume text extraction.")

    with st.sidebar:
        st.header("Settings")
        model = st.text_input("Groq model ID", value=os.getenv("GROQ_MODEL", DEFAULT_MODEL), help="Use a model currently enabled for your Groq account.")
        st.caption("Your resume is sent to Groq only when you click Analyze. Avoid uploading sensitive information you do not want processed by an external AI provider.")

    uploaded_file = st.file_uploader("Upload resume", type=["pdf", "docx", "txt"], help="Maximum file size: 8 MB. Scanned PDFs need OCR before upload.")
    job_description = st.text_area("Job description (recommended)", height=180, placeholder="Paste the job posting here to evaluate keyword alignment. Optional, but it makes the score more relevant.")

    if uploaded_file is not None and uploaded_file.size > MAX_FILE_BYTES:
        st.error("File is larger than 8 MB. Please upload a smaller file.")
        return

    if st.button("Analyze resume", type="primary", disabled=uploaded_file is None, use_container_width=True):
        try:
            resume_text = extract_text(uploaded_file.name, uploaded_file.getvalue())
        except ValueError as exc:
            st.error(str(exc))
            return

        if len(resume_text) < 80:
            st.warning("Very little text was extracted. Check the file or use a text-based PDF/DOCX/TXT file.")

        score, categories, missing_sections, matched_keywords = calculate_ats_score(resume_text, job_description)
        st.subheader("ATS-style score")
        metric_col, details_col = st.columns([1, 2])
        with metric_col:
            st.metric("Estimated score", f"{score}/100")
            st.progress(score / 100)
            if score >= 80:
                st.success("Strong baseline — review the detailed suggestions.")
            elif score >= 60:
                st.warning("Good starting point — several improvements may help.")
            else:
                st.error("Needs work — start with structure and job alignment.")
        with details_col:
            st.markdown("**Score breakdown**")
            for label, points in categories.items():
                max_points = {"Sections and structure": 25, "Contact details": 15, "Length and readability proxy": 15, "Achievements and metrics": 20, "Job-description keyword match": 25}[label]
                st.write(f"{label}: **{points}/{max_points}**")
                st.progress(min(points / max_points, 1.0))

        st.subheader("Resume checks")
        if missing_sections:
            st.write("Consider adding or clearly labeling: " + ", ".join(missing_sections) + ".")
        else:
            st.write("Core resume sections appear to be present.")
        if job_description.strip():
            st.write(f"Matched {len(matched_keywords)} of the extracted job-description keywords.")
            with st.expander("Matched keywords"):
                st.write(", ".join(matched_keywords) if matched_keywords else "No clear keyword matches found.")

        with st.spinner("Asking Groq for tailored suggestions…"):
            try:
                feedback = get_groq_feedback(resume_text, job_description, score, categories, model.strip() or DEFAULT_MODEL)
                st.subheader("AI improvement plan")
                st.markdown(feedback)
                report = f"# ATS Resume Analyzer Report\n\nEstimated score: {score}/100\n\n## Score breakdown\n" + "\n".join(f"- {key}: {value}" for key, value in categories.items()) + f"\n\n## AI improvement plan\n\n{feedback}\n"
                st.download_button("Download analysis report (.md)", data=report, file_name="resume_analysis_report.md", mime="text/markdown")
            except Exception as exc:
                st.error(f"Could not get AI feedback from Groq: {exc}")
                st.caption("The heuristic score above is still available. Check your API key, model ID, account limits, and network connection.")

    st.divider()
    st.caption("Privacy note: this demo does not save uploaded files to disk or a database. The resume text is sent to Groq when analysis is requested. Review Groq's current privacy terms before using this with real candidate data.")


if __name__ == "__main__":
    main()
