# Job Application Agent

Job Application Agent is an autonomous AI-powered job search and application system. It parses a candidate resume, extracts technical skills, scrapes LinkedIn and public Glassdoor job listings, ranks jobs by semantic relevance using sentence-transformers and FAISS, generates tailored cover letters with Groq Llama 3 through LangChain, performs skill-gap analysis, and exports a bulk JSON application payload.

## Architecture

```text
+-------------------+     +---------------------+     +----------------------+
| Streamlit UI      | --> | LangGraph StateGraph | --> | JSON Export          |
| Resume + Config   |     | AgentState pipeline  |     | applications.json    |
+-------------------+     +----------+----------+     +----------------------+
                                      |
                                      v
+-------------------+     +---------------------+     +----------------------+
| Resume Parser     |     | Scrapers            |     | Semantic Matcher     |
| PyPDF2/python-docx|     | LinkedIn/Glassdoor  |     | MiniLM + FAISS       |
+-------------------+     +---------------------+     +----------------------+
                                      |
                                      v
                           +---------------------+
                           | Cover Letters       |
                           | LangChain + Groq    |
                           +---------------------+
```

## Prerequisites

- Python 3.10+
- Google Chrome installed
- Groq API key
- LinkedIn account credentials for LinkedIn scraping

## Setup

```bash
git clone <your-repo-url>
cd job-application-agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` with your own credentials:

```env
GROQ_API_KEY=your_groq_api_key_here
LINKEDIN_EMAIL=your_linkedin_email@example.com
LINKEDIN_PASSWORD=your_linkedin_password_here
HEADLESS=true
```

## Run

```bash
streamlit run app.py
```

Upload a PDF or DOCX resume, enter the job title, location, candidate name, relevance threshold, and maximum results per source, then run the agent from the sidebar.

## Generate Report

```bash
python generate_report.py
```

This creates `Job_Application_Agent_Project_Report.docx` in the project root.

## Environment Variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `GROQ_API_KEY` | Yes | Authenticates Groq LLM calls for cover letter generation. |
| `LINKEDIN_EMAIL` | Yes | LinkedIn login email used by the Selenium scraper. |
| `LINKEDIN_PASSWORD` | Yes | LinkedIn login password used by the Selenium scraper. |
| `HEADLESS` | No | Controls whether Chrome runs headlessly. Defaults to `true`. |
| `CHROME_VERSION_MAIN` | No | Pin Chrome major version for undetected-chromedriver, for example `148`. |
| `CHROME_USER_DATA_DIR` | No | Optional persistent Chrome profile directory, useful for manual LinkedIn verification. |

## Example Output Record

```json
{
  "job_id": "senior-ai-engineer-example",
  "job_title": "Senior AI Engineer",
  "company": "Example AI Labs",
  "location": "Remote",
  "url": "https://www.linkedin.com/jobs/view/example",
  "source": "linkedin",
  "relevance_score": 0.82,
  "matching_skills": ["Python", "LangChain", "FAISS"],
  "missing_skills": ["Kubernetes"],
  "match_percentage": 75.0,
  "cover_letter": "Dear Hiring Team,...",
  "scraped_at": "2026-06-07T10:00:00+00:00"
}
```

## Known Limitations

- LinkedIn actively detects automation. Even with undetected Chrome, checkpoint prompts, rate limits, and account verification can block scraping.
- Glassdoor is scraped without login, so public pages may expose only limited fields. Salary and full descriptions may be unavailable and are stored as `None`.
- Semantic matching depends on scraped job descriptions. Sparse snippets produce weaker scores than full descriptions.
- Groq cover letter generation requires a valid `GROQ_API_KEY` and network access.
- Selenium scraping should be used responsibly and in accordance with each platform's terms.
