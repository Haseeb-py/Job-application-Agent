"""Few-shot LangChain prompt templates for cover letter generation."""

from langchain_core.prompts import PromptTemplate

cover_letter_prompt = PromptTemplate(
    input_variables=["job_title", "company", "resume_skills", "job_description", "candidate_name"],
    template="""You are an expert career writing assistant.

System instruction:
Write a concise, 3-paragraph professional cover letter. Use no fluff. Highlight matching skills from the candidate profile. Show enthusiasm for the specific company and role. Do not invent experience.

Example 1:
Job Title: Software Engineer
Company: NovaCloud
Resume Skills: Python, FastAPI, Docker, PostgreSQL, AWS, CI/CD
Job Description: NovaCloud needs a backend engineer to build scalable APIs, improve deployment workflows, and support cloud infrastructure.
Candidate Name: Alex Morgan
Cover Letter:
Dear Hiring Team,

I am excited to apply for the Software Engineer role at NovaCloud. My experience building backend services with Python and FastAPI, combined with hands-on work in Docker, PostgreSQL, AWS, and CI/CD, aligns closely with your need for reliable API development and scalable cloud delivery.

In previous engineering work, I have focused on writing maintainable services, improving deployment consistency, and collaborating across product and infrastructure concerns. NovaCloud's emphasis on scalable systems is especially appealing because it matches the kind of practical engineering problems I enjoy solving.

I would welcome the opportunity to bring my backend engineering background and cloud deployment experience to NovaCloud. Thank you for considering my application.

Example 2:
Job Title: Data Scientist
Company: InsightWorks
Resume Skills: Python, Pandas, Scikit-learn, TensorFlow, NLP, Tableau
Job Description: InsightWorks is hiring a Data Scientist to develop machine learning models, analyze business datasets, communicate insights, and build NLP prototypes.
Candidate Name: Priya Shah
Cover Letter:
Dear Hiring Team,

I am pleased to apply for the Data Scientist role at InsightWorks. My background with Python, Pandas, Scikit-learn, TensorFlow, NLP, and Tableau is a strong match for your focus on machine learning, business analysis, and clear communication of insights.

I have worked across the analytics lifecycle, from preparing datasets and developing predictive models to translating technical results into practical recommendations. InsightWorks stands out to me because the role combines rigorous modeling with direct business impact.

I would be glad to contribute my machine learning and analytics skills to your team. Thank you for your time and consideration.

Now write the cover letter.

Job Title: {job_title}
Company: {company}
Resume Skills: {resume_skills}
Job Description: {job_description}
Candidate Name: {candidate_name}
Cover Letter:
""",
)
