import os
import sqlite3
from datetime import datetime

import pandas as pd
from agno.agent import Agent
from agno.models.openai import OpenAIChat


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(BASE_DIR, "agno_test_data_pack")
MEMORY_FOLDER = os.path.join(BASE_DIR, "memory")
DB_FILE = os.path.join(MEMORY_FOLDER, "release_memory.db")


def load_csv(file_name):
    file_path = os.path.join(DATA_FOLDER, file_name)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Missing file: {file_path}")

    return pd.read_csv(file_path)


def load_all_data():
    return {
        "historical": load_csv("historical_releases.csv"),
        "current": load_csv("current_release.csv"),
        "lessons": load_csv("lessons_learned.csv"),
        "jira": load_csv("jira_data.csv"),
        "test": load_csv("test_data.csv"),
        "security": load_csv("security_data.csv"),
    }


def build_release_context(data):
    return f"""
You are an Enterprise Release Manager Agent.

Analyze release readiness using:
- Historical releases
- Current release
- Lessons learned
- Jira defects
- Test results
- Security findings

Historical Releases:
{data["historical"].to_string(index=False)}

Current Release:
{data["current"].to_string(index=False)}

Lessons Learned:
{data["lessons"].to_string(index=False)}

Jira Data:
{data["jira"].to_string(index=False)}

Test Data:
{data["test"].to_string(index=False)}

Security Data:
{data["security"].to_string(index=False)}
"""


def init_memory_db():
    os.makedirs(MEMORY_FOLDER, exist_ok=True)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            user_message TEXT,
            agent_response TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_conversation(user_message, agent_response):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO conversation_memory 
        (timestamp, user_message, agent_response)
        VALUES (?, ?, ?)
    """, (
        datetime.now().isoformat(),
        user_message,
        agent_response
    ))

    conn.commit()
    conn.close()


def load_recent_memory(limit=5):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_message, agent_response
        FROM conversation_memory
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    rows.reverse()

    memory_text = ""
    for user_msg, agent_msg in rows:
        memory_text += f"\nUser: {user_msg}\nAgent: {agent_msg}\n"

    return memory_text


def create_agent():
    return Agent(
        name="Release Manager Agent",
        model=OpenAIChat(id="gpt-4o-mini"),
        markdown=True
    )


def main():
    print("=" * 70)
    print("AGNO RELEASE MANAGER AGENT - STAGE 3")
    print("Custom SQLite Persistent Memory Enabled")
    print("=" * 70)

    init_memory_db()

    data = load_all_data()
    release_context = build_release_context(data)
    agent = create_agent()

    print(f"\nMemory DB location: {DB_FILE}")
    print("\nAsk release questions. Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in ["exit", "quit"]:
            print("\nExiting Release Manager Agent.")
            break

        if not user_input:
            continue

        recent_memory = load_recent_memory(limit=5)

        full_prompt = f"""
{release_context}

Recent Conversation Memory:
{recent_memory}

Current User Question:
{user_input}

Answer as an Enterprise Release Manager Agent.
Use release data and conversation memory where relevant.
"""

        response = agent.run(full_prompt)

        if hasattr(response, "content"):
            agent_answer = response.content
        else:
            agent_answer = str(response)

        print("\nAgent:")
        print(agent_answer)

        save_conversation(user_input, agent_answer)


if __name__ == "__main__":
    main()