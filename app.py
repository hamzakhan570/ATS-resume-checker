
def get_groq_feedback(resume_text, job_description, score, categories, model):
    """Generate evidence-based resume feedback using Groq."""

    prompt = f"""
Analyze the resume and provide practical, honest feedback.

Use these headings:
### Overall assessment
### Top 5 improvements (prioritized)
### Suggested summary rewrite
### Stronger bullet examples
### Keywords to consider (only if supported by the candidate's experience)
### Formatting and ATS tips

Keep advice actionable. Never invent experience, skills, qualifications,
or achievements. Do not guarantee ATS outcomes.

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
            {
                "role": "system",
                "content": (
                    "You provide honest, evidence-based resume feedback. "
                    "Never fabricate candidate details."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_completion_tokens=1800,
    )

    result = response.choices[0].message.content

    if not result:
        raise RuntimeError(
            "Groq returned an empty response. Please try again."
        )

    return result
