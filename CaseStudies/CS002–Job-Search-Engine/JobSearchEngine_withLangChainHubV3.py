# V2 program - fixed timeout issue in Agent 4

import os
import time
import json
import re
import urllib.parse
import gspread
from typing import List

from pydantic import BaseModel, Field

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager

from langsmith import Client
from langchain_openai import ChatOpenAI


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is missing in environment variables.")

if not LANGSMITH_API_KEY:
    raise ValueError("LANGSMITH_API_KEY is missing in environment variables.")

GOOGLE_CREDS_FILE = os.getenv(
    "GOOGLE_CREDS_FILE",
    r"C:\Users\prabh\PyCharmMiscProject\Utility_Package\google-credentials.json"
)

GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Job-Search-Results")
# give this prompt in ChatGPT to find suitable job roles
# "im doing a job search on AI Solution architect. can you give me similar job roles

KEYWORDS = [
"AI Solution Architect",
"Generative AI Solution Architect",
"Enterprise AI Architect",
"AI Applications Architect",
"AI Platform Architect",
"AI Systems Architect",
"AI Integration Architect",
"GenAI Architect",
"LLM Solution Architect",
"Conversational AI Architect",
"AI Infrastructure Architect",
"Intelligent Automation Architect",
"AI Transformation Architect",
"AI Technology Architect",
"AI Enterprise Architect"
]


LOCATIONS = [
    "Remote",
    "San Francisco",
    "San Jose",
    "Sunnyvale",
    "Santa Clara",
    "Mountain view",
    "Palo Alto",
    "Menlo Park",
    "Cupertino",
    "Seattle",
    "Dallas",
    "Austin",
    "New York City",
    "Atlanta",
    "Chicago"
]


DOMAIN_FILTERS = [
    "Prompt Engineering",
    "Full Stack Development",
    "Frontend Engineering",
    "Backend Engineering",
    "React JS",
    "Digital Transformation"
]


llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    timeout=180,
    max_retries=3
)

hub_client = Client()

JOB_SEARCH_PROMPT = "job-search-agent"
JOB_REVIEW_PROMPT = "job-review-agent"
GOOGLE_SHEET_PROMPT = "google-sheet-agent"


class JobResult(BaseModel):
    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    link: str = Field(description="Job posting link")
    source: str = Field(description="LinkedIn or Indeed")
    relevance_score: int = Field(description="Relevance score from 1 to 100")
    comments: str = Field(description="Short review comments")


class JobResultList(BaseModel):
    jobs: List[JobResult]


def parse_llm_json_response(response) -> JobResultList:
    if isinstance(response, dict):
        return JobResultList(**response)

    if isinstance(response, JobResultList):
        return response

    content = response.content

    if isinstance(content, dict):
        return JobResultList(**content)

    if isinstance(content, list):
        content = "\n".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        )

    content = str(content).strip()
    content = re.sub(r"^```json\s*", "", content)
    content = re.sub(r"^```\s*", "", content)
    content = re.sub(r"\s*```$", "", content)

    data = json.loads(content)
    return JobResultList(**data)


def invoke_with_retry(chain, payload, retries=3, wait_seconds=10):
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            return chain.invoke(payload)
        except Exception as e:
            last_error = e
            print(f"⚠️ LLM call failed attempt {attempt}/{retries}: {str(e)}")
            if attempt < retries:
                print(f"   Retrying in {wait_seconds} seconds...")
                time.sleep(wait_seconds)

    raise last_error


def create_driver():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )


def deduplicate_raw_jobs(jobs):
    seen_links = set()
    unique_jobs = []

    for job in jobs:
        link = job.get("link", "").strip()
        if link and link not in seen_links:
            unique_jobs.append(job)
            seen_links.add(link)

    return unique_jobs


def scrape_linkedin_jobs(driver):
    print("🔎 Scraping LinkedIn jobs across locations...")

    jobs = []
    keyword_query = " OR ".join(KEYWORDS)
    encoded_keywords = urllib.parse.quote(keyword_query)

    for location in LOCATIONS:
        print(f"   LinkedIn location: {location}")

        encoded_location = urllib.parse.quote(location)

        url = (
            f"https://www.linkedin.com/jobs/search?"
            f"keywords={encoded_keywords}"
            f"&location={encoded_location}"
        )

        if location.lower() == "remote":
            url += "&f_WT=2"

        driver.get(url)
        time.sleep(5)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        for job_card in soup.find_all("div", class_="base-search-card"):
            try:
                title_tag = job_card.find("h3", class_="base-search-card__title")
                company_tag = job_card.find("h4", class_="base-search-card__subtitle")
                link_tag = job_card.find("a")

                if title_tag and company_tag and link_tag and link_tag.get("href"):
                    jobs.append({
                        "title": title_tag.get_text(strip=True),
                        "company": company_tag.get_text(strip=True),
                        "link": link_tag["href"],
                        "source": f"LinkedIn - {location}"
                    })
            except Exception:
                continue

    return deduplicate_raw_jobs(jobs)


def scrape_indeed_jobs(driver):
    print("🔎 Scraping Indeed jobs across locations...")

    jobs = []
    keyword_query = " OR ".join(KEYWORDS)
    encoded_keywords = urllib.parse.quote(keyword_query)

    for location in LOCATIONS:
        print(f"   Indeed location: {location}")

        encoded_location = urllib.parse.quote(location)

        url = (
            f"https://www.indeed.com/jobs?"
            f"q={encoded_keywords}"
            f"&l={encoded_location}"
        )

        driver.get(url)
        time.sleep(5)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        for job_card in soup.find_all("div", class_="job_seen_beacon"):
            try:
                title_element = job_card.find("h2", class_="jobTitle")
                company_element = job_card.find("span", class_="companyName")
                link_element = job_card.find("a")

                if title_element and company_element and link_element and link_element.get("href"):
                    href = link_element["href"]
                    full_link = href if href.startswith("http") else "https://www.indeed.com" + href

                    jobs.append({
                        "title": title_element.get_text(strip=True),
                        "company": company_element.get_text(strip=True),
                        "link": full_link,
                        "source": f"Indeed - {location}"
                    })
            except Exception:
                continue

    return deduplicate_raw_jobs(jobs)


def batch_jobs(jobs, batch_size=10):
    for i in range(0, len(jobs), batch_size):
        yield jobs[i:i + batch_size]


def job_search_agent(raw_jobs):
    prompt = hub_client.pull_prompt(JOB_SEARCH_PROMPT)
    chain = prompt | llm

    response = invoke_with_retry(chain, {
        "keywords": ", ".join(KEYWORDS),
        "location": ", ".join(LOCATIONS),
        "domain_filters": "\n".join(DOMAIN_FILTERS),
        "raw_jobs": json.dumps(raw_jobs, indent=2)
    })

    return parse_llm_json_response(response)


def review_agent(agent1_results):
    prompt = hub_client.pull_prompt(JOB_REVIEW_PROMPT)
    chain = prompt | llm

    response = invoke_with_retry(chain, {
        "keywords": ", ".join(KEYWORDS),
        "location": ", ".join(LOCATIONS),
        "jobs": agent1_results.model_dump_json(indent=2)
    })

    return parse_llm_json_response(response)


def remove_seen_jobs(results, seen_file="seen_jobs.json"):
    if os.path.exists(seen_file):
        with open(seen_file, "r", encoding="utf-8") as f:
            seen_links = set(json.load(f))
    else:
        seen_links = set()

    new_jobs = []

    for job in results.jobs:
        if job.link not in seen_links:
            new_jobs.append(job)
            seen_links.add(job.link)

    with open(seen_file, "w", encoding="utf-8") as f:
        json.dump(list(seen_links), f, indent=2)

    return JobResultList(jobs=new_jobs)


def google_sheet_agent(results, batch_size=10):
    prompt = hub_client.pull_prompt(GOOGLE_SHEET_PROMPT)
    chain = prompt | llm

    final_jobs = []

    for index, batch in enumerate(batch_jobs(results.jobs, batch_size=batch_size), start=1):
        print(f"   Preparing Google Sheet batch {index} with {len(batch)} jobs...")

        batch_input = JobResultList(jobs=batch)

        try:
            response = invoke_with_retry(chain, {
                "jobs": batch_input.model_dump_json(indent=2)
            })

            batch_result = parse_llm_json_response(response)
            final_jobs.extend(batch_result.jobs)
            time.sleep(2)

        except Exception as e:
            print(f"⚠️ Agent 4 failed for batch {index}: {str(e)}")
            print("   Using original reviewed jobs for this batch...")
            final_jobs.extend(batch)

    return JobResultList(jobs=final_jobs)


def save_to_google_sheets(results):
    if not os.path.exists(GOOGLE_CREDS_FILE):
        print(f"❌ Google credentials file not found: {GOOGLE_CREDS_FILE}")
        return False

    try:
        gc = gspread.service_account(filename=GOOGLE_CREDS_FILE)
        sheet = gc.open(GOOGLE_SHEET_NAME).sheet1

        sheet.clear()

        rows = [[
            "Title",
            "Company",
            "Link",
            "Source",
            "Relevance Score",
            "Comments"
        ]]

        for job in results.jobs:
            rows.append([
                job.title,
                job.company,
                job.link,
                job.source,
                job.relevance_score,
                job.comments
            ])

        sheet.append_rows(rows)

        print("✅ Final reviewed jobs saved to Google Sheets.")
        return True

    except Exception as e:
        print(f"❌ Google Sheets Error: {str(e)}")
        return False


def main():
    driver = create_driver()

    try:
        linkedin_jobs = scrape_linkedin_jobs(driver)
        indeed_jobs = scrape_indeed_jobs(driver)

        raw_jobs = linkedin_jobs + indeed_jobs
        raw_jobs = deduplicate_raw_jobs(raw_jobs)

        if not raw_jobs:
            print("❌ No jobs found.")
            return

        print(f"✅ Raw unique jobs found: {len(raw_jobs)}")

        print("\n🤖 Agent 1: Filtering and scoring jobs...")
        agent1_all_jobs = []

        for index, batch in enumerate(batch_jobs(raw_jobs, batch_size=10), start=1):
            print(f"   Processing Agent 1 batch {index} with {len(batch)} jobs...")

            try:
                batch_result = job_search_agent(batch)
                agent1_all_jobs.extend(batch_result.jobs)
                time.sleep(2)
            except Exception as e:
                print(f"⚠️ Agent 1 failed for batch {index}: {str(e)}")
                continue

        agent1_results = JobResultList(jobs=agent1_all_jobs)
        print(f"✅ Agent 1 output jobs: {len(agent1_results.jobs)}")

        if not agent1_results.jobs:
            print("❌ No jobs passed Agent 1 filtering.")
            return

        print("\n🧐 Agent 2: Reviewing and cleaning jobs in smaller batches...")
        reviewed_all_jobs = []

        for index, batch in enumerate(batch_jobs(agent1_results.jobs, batch_size=5), start=1):
            print(f"   Reviewing Agent 2 batch {index} with {len(batch)} jobs...")

            batch_input = JobResultList(jobs=batch)

            try:
                batch_reviewed = review_agent(batch_input)
                reviewed_all_jobs.extend(batch_reviewed.jobs)
                time.sleep(2)
            except Exception as e:
                print(f"⚠️ Agent 2 failed for batch {index}: {str(e)}")
                continue

        reviewed_results = JobResultList(jobs=reviewed_all_jobs)
        print(f"✅ Agent 2 reviewed jobs: {len(reviewed_results.jobs)}")

        if not reviewed_results.jobs:
            print("❌ No jobs passed Agent 2 review.")
            return

        print("\n🧠 Memory Agent: Removing jobs already seen earlier...")
        new_only_results = remove_seen_jobs(reviewed_results)
        print(f"✅ New jobs after memory filter: {len(new_only_results.jobs)}")

        if not new_only_results.jobs:
            print("⚠️ No new jobs to update in Google Sheets.")
            return

        print("\n📊 Agent 4: Preparing Google Sheet output in batches...")
        final_results = google_sheet_agent(new_only_results, batch_size=10)
        print(f"✅ Final jobs for sheet: {len(final_results.jobs)}")

        print("\n💾 Updating Google Sheet...")
        save_ok = save_to_google_sheets(final_results)

        if save_ok:
            print("✅ Job Search Workflow completed successfully.")
        else:
            print("⚠️ Workflow completed, but Google Sheet update failed.")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()