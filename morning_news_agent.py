import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

# --------------------------
# SETTINGS
# --------------------------

LM_STUDIO_URL = "YOUR URL"
MODEL_NAME = "YOUR MODEL"

GMAIL_ADDRESS = "YOUR EMAIL"
GMAIL_APP_PASSWORD = "YOUR PASSWORD"

NEWSAPI_KEY = "YOUR API KEY"
FINNHUB_KEY = "YOUR API KEY"

# --------------------------
# FETCH MARKET DATA
# --------------------------

def fetch_markets():
    symbols = {
        "S&P 500": "SPY",
        "Nasdaq": "QQQ",
        "Dow Jones": "DIA",
        "Bitcoin": "BTC-USD",
    }

    market_rows = []
    market_text_for_llm = []

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    for name, symbol in symbols.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            response = requests.get(url, headers=headers).json()
            result = response["chart"]["result"][0]["meta"]

            price = result["regularMarketPrice"]
            prev = result["previousClose"]
            change = ((price - prev) / prev) * 100

            color = "#16a34a" if change >= 0 else "#dc2626"
            arrow = "▲" if change >= 0 else "▼"
            sign = "+" if change >= 0 else ""

            market_rows.append(f"""
                <tr>
                    <td style="padding:8px 12px; font-weight:600; color:#1e293b;">{name}</td>
                    <td style="padding:8px 12px; color:#334155;">{round(price, 2)}</td>
                    <td style="padding:8px 12px; font-weight:700; color:{color};">
                        {arrow} {sign}{round(change, 2)}%
                    </td>
                </tr>
            """)

            market_text_for_llm.append(
                f"{name} ({symbol}): ${round(price, 2)}, {sign}{round(change, 2)}% change from prior close"
            )

        except Exception as e:
            market_rows.append(f"""
                <tr>
                    <td style="padding:8px 12px;">{name}</td>
                    <td style="padding:8px 12px;" colspan="2">Unavailable</td>
                </tr>
            """)

    table_html = f"""
        <table style="border-collapse:collapse; width:100%; max-width:500px;">
            <thead>
                <tr style="background:#f1f5f9; border-bottom:2px solid #e2e8f0;">
                    <th style="padding:8px 12px; text-align:left; color:#64748b; font-size:12px; text-transform:uppercase; letter-spacing:0.05em;">Index</th>
                    <th style="padding:8px 12px; text-align:left; color:#64748b; font-size:12px; text-transform:uppercase; letter-spacing:0.05em;">Price</th>
                    <th style="padding:8px 12px; text-align:left; color:#64748b; font-size:12px; text-transform:uppercase; letter-spacing:0.05em;">1-Day Change</th>
                </tr>
            </thead>
            <tbody>
                {"".join(market_rows)}
            </tbody>
        </table>
    """

    return table_html, "\n".join(market_text_for_llm)

# --------------------------
# GENERATE MARKET COMMENTARY
# --------------------------

def generate_market_commentary(market_text):
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a concise financial analyst writing a morning market summary for an executive. "
                    "Given today's market data, write 3–5 sentences covering:\n"
                    "1. Overall market sentiment based on today's moves\n"
                    "2. Any notable macroeconomic events or themes to be aware of (e.g. Fed decisions, inflation, earnings season, geopolitical risks)\n"
                    "3. Any key observations about specific indexes or Bitcoin\n\n"
                    "Be direct, professional, and informative. Do NOT use bullet points — write in flowing prose."
                )
            },
            {
                "role": "user",
                "content": f"Here is today's market data:\n{market_text}\n\nWrite the morning market commentary."
            }
        ],
        "temperature": 0.4
    }

    try:
        response = requests.post(LM_STUDIO_URL, json=payload).json()
        if "choices" in response:
            return response["choices"][0]["message"]["content"]
        return "Market commentary unavailable."
    except Exception as e:
        return f"Market commentary unavailable: {e}"

# --------------------------
# FETCH NEWS
# --------------------------

def fetch_newsapi(query, label, page_size=5):
    """Fetch articles from NewsAPI for a given keyword query."""
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": page_size,
            "apiKey": NEWSAPI_KEY,
        }
        response = requests.get(url, params=params).json()
        articles = []
        for a in response.get("articles", []):
            if a.get("title") and a.get("url") and "[Removed]" not in a.get("title", ""):
                articles.append(
                    f"SECTION: {label}\n"
                    f"TITLE: {a['title']}\n"
                    f"SUMMARY: {a.get('description') or a.get('content') or 'No summary available.'}\n"
                    f"LINK: {a['url']}\n"
                    f"SOURCE: {a.get('source', {}).get('name', 'Unknown')}\n"
                )
        return articles
    except Exception as e:
        print(f"[NewsAPI ERROR - {label}] {e}")
        return []


def fetch_finnhub_finance(count=5):
    """Fetch finance news from Finnhub (market-specific, high quality)."""
    try:
        url = "https://finnhub.io/api/v1/news"
        params = {
            "category": "general",
            "token": FINNHUB_KEY,
        }
        response = requests.get(url, params=params).json()
        articles = []
        for a in response[:count]:
            if a.get("headline") and a.get("url"):
                sentiment = a.get("sentiment", "")
                sentiment_label = ""
                if sentiment == "positive":
                    sentiment_label = " [Sentiment: Positive 📈]"
                elif sentiment == "negative":
                    sentiment_label = " [Sentiment: Negative 📉]"

                articles.append(
                    f"SECTION: Finance\n"
                    f"TITLE: {a['headline']}{sentiment_label}\n"
                    f"SUMMARY: {a.get('summary', 'No summary available.')}\n"
                    f"LINK: {a['url']}\n"
                    f"SOURCE: {a.get('source', 'Finnhub')}\n"
                )
        return articles
    except Exception as e:
        print(f"[Finnhub ERROR] {e}")
        return []


def fetch_news():
    """Fetch all news from NewsAPI and Finnhub, organized by section."""
    all_articles = []

    print("  → Fetching General News from NewsAPI...")
    all_articles += fetch_newsapi("world news OR politics OR economy", "General News", page_size=5)

    print("  → Fetching Accounting news from NewsAPI...")
    all_articles += fetch_newsapi("accounting OR audit OR GAAP OR CPA OR financial reporting", "Accounting", page_size=5)

    print("  → Fetching AI news from NewsAPI...")
    all_articles += fetch_newsapi("artificial intelligence OR machine learning OR large language model OR OpenAI OR AI", "Artificial Intelligence", page_size=5)

    print("  → Fetching Finance news from Finnhub...")
    all_articles += fetch_finnhub_finance(count=5)

    return "\n\n".join(all_articles)

# --------------------------
# SUMMARIZE USING LM STUDIO
# --------------------------

def summarize(text):
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

    final_payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a professional news analyst writing a structured morning briefing in HTML format.\n\n"

                    "STRICT RULES:\n"
                    "- Do NOT include any preamble, explanation, or closing remarks.\n"
                    "- Do NOT repeat instructions or output placeholder text.\n"
                    "- Only summarize real articles provided — do not fabricate stories.\n"
                    "- Output ONLY valid HTML — no markdown, no plain text outside tags.\n\n"

                    "STRUCTURE: Produce exactly 4 sections in this order:\n"
                    "1. General News\n"
                    "2. Accounting\n"
                    "3. Finance\n"
                    "4. Artificial Intelligence\n\n"

                    "Each section must have 3–5 real stories from the provided articles.\n\n"

                    "HTML FORMAT FOR EACH SECTION:\n"
                    "<div style='margin-bottom:32px;'>\n"
                    "  <h2 style='font-size:20px; font-weight:700; color:#1e293b; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-bottom:16px;'>Section Name</h2>\n"
                    "  <ul style='list-style:none; padding:0; margin:0;'>\n"
                    "    <li style='margin-bottom:16px;'>\n"
                    "      <p style='margin:0 0 4px 0;'><b><a href='ACTUAL_ARTICLE_URL' style='color:#1d4ed8; text-decoration:none;'>Real Headline Here</a></b></p>\n"
                    "      <p style='margin:0; color:#475569; font-size:14px;'>2-3 sentence summary of the actual article.</p>\n"
                    "    </li>\n"
                    "  </ul>\n"
                    "</div>\n\n"

                    "Use the actual article URL from the LINK field for each story. "
                    "Every headline must be a clickable hyperlink."
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

def send_email(market_table, market_commentary, news_content):
    today = datetime.now().strftime('%A, %B %d, %Y')
    generated_time = datetime.now().strftime('%I:%M %p')

    html_content = f"""
    <html>
      <body style="margin:0; padding:0; background-color:#f8fafc; font-family: Georgia, 'Times New Roman', serif;">

        <div style="max-width:700px; margin:0 auto; background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; overflow:hidden; margin-top:24px; margin-bottom:24px;">

          <!-- Header -->
          <div style="background:#0f172a; padding:32px 40px 24px 40px;">
            <h1 style="margin:0; font-size:28px; font-weight:700; color:#ffffff; letter-spacing:-0.5px;">
              Morning News Report
            </h1>
            <p style="margin:8px 0 0 0; color:#94a3b8; font-size:14px; font-family:Arial, sans-serif;">
              {today} &nbsp;·&nbsp; Generated at {generated_time}
            </p>
          </div>

          <!-- Body -->
          <div style="padding:32px 40px;">

            <!-- Market Overview Section -->
            <div style="margin-bottom:36px;">
              <h2 style="font-size:20px; font-weight:700; color:#1e293b; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-bottom:16px; font-family:Arial, sans-serif;">
                📈 Market Overview
              </h2>

              {market_table}

              <div style="margin-top:16px; padding:16px; background:#f8fafc; border-left:4px solid #3b82f6; border-radius:4px;">
                <p style="margin:0; color:#334155; font-size:14px; line-height:1.7; font-family:Arial, sans-serif;">
                  {market_commentary}
                </p>
              </div>
            </div>

            <hr style="border:none; border-top:1px solid #e2e8f0; margin:0 0 32px 0;">

            <!-- News Sections -->
            <div style="font-family:Arial, sans-serif; font-size:15px; line-height:1.7; color:#1e293b;">
              {news_content}
            </div>

          </div>

          <!-- Footer -->
          <div style="background:#f8fafc; border-top:1px solid #e2e8f0; padding:16px 40px; text-align:center;">
            <p style="margin:0; font-size:12px; color:#94a3b8; font-family:Arial, sans-serif;">
              Morning News Report · Auto-generated · {today}
            </p>
          </div>

        </div>

      </body>
    </html>
    """

    msg = MIMEText(html_content, "html")
    msg["Subject"] = f"Morning News Report — {datetime.now().strftime('%B %d, %Y')}"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = "YOUR EMAIL"

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)

# --------------------------
# MAIN
# --------------------------

if __name__ == "__main__":
    print("Fetching market data...")
    market_table, market_text = fetch_markets()

    print("Generating market commentary...")
    market_commentary = generate_market_commentary(market_text)

    print("Fetching news...")
    news = fetch_news()

    print("Summarizing news...")
    news_summary = summarize(news)

    print("Sending email...")
    send_email(market_table, market_commentary, news_summary)

    print("Done.")
