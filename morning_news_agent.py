import requests
import feedparser
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

# --------------------------
# SETTINGS
# --------------------------

LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL_NAME = "google/gemma-3-4b"

GMAIL_ADDRESS = "c02tice@gmail.com"
GMAIL_APP_PASSWORD = "asglzxlykgyyvkdb"

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=artificial+intelligence",
    "https://news.google.com/rss/search?q=finance",
    "https://news.google.com/rss/search?q=accounting",
    "https://news.google.com/rss"
]

# --------------------------
# FETCH NEWS
# --------------------------

def fetch_news():
    articles = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            articles.append(f"{entry.title}\n{entry.summary}\n")
    return "\n\n".join(articles)

# --------------------------
# SUMMARIZE USING LM STUDIO
# --------------------------

def summarize(text):
    # Break text into safe chunks
    chunk_size = 2500
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

    partial_summaries = []

    for idx, chunk in enumerate(chunks):
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "system",
                    "content": "Summarize this news content clearly and concisely."
                },
                {"role": "user", "content": chunk}
            ],
            "temperature": 0.3
        }

        try:
            response = requests.post(LM_STUDIO_URL, json=payload)
            data = response.json()
        except Exception as e:
            partial_summaries.append(f"[ERROR parsing chunk {idx}] {e}")
            continue

        if "error" in data:
            partial_summaries.append(f"[LM STUDIO ERROR chunk {idx}] {data['error']}")
            continue

        if "choices" not in data:
            partial_summaries.append(f"[INVALID RESPONSE chunk {idx}] {data}")
            continue

        partial_summaries.append(data["choices"][0]["message"]["content"])

    # Now summarize the summaries into a final briefing
    final_payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a news summarizer. Create a clean morning briefing with "
                    "sections for AI, Finance, and General News."
                )
            },
            {"role": "user", "content": "\n\n".join(partial_summaries)}
        ],
        "temperature": 0.3
    }

    final_response = requests.post(LM_STUDIO_URL, json=final_payload).json()

    if "choices" in final_response:
        return final_response["choices"][0]["message"]["content"]

    return f"[FINAL SUMMARY ERROR] {final_response}"


# --------------------------
# SEND EMAIL
# --------------------------

def send_email(content):
    msg = MIMEText(content)
    msg["Subject"] = f"Morning News Briefing - {datetime.now().strftime('%Y-%m-%d')}"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = GMAIL_ADDRESS

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)

# --------------------------
# MAIN
# --------------------------

if __name__ == "__main__":
    print("Fetching news...")
    news = fetch_news()

    print("Summarizing...")
    summary = summarize(news)

    print("Sending email...")
    send_email(summary)

    print("Done.")
