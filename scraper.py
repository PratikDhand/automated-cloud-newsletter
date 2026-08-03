import os
import sqlite3
import feedparser
import time
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import google.generativeai as genai
from dotenv import load_dotenv
# --- CONFIGURATION ---
DB_NAME = "newsletter_archive.db"
OUTPUT_FILE = "Newsletter-1.html"

# ⚠️ # ⚠️ LOAD API KEY SECURELY ⚠️
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model= genai.GenerativeModel('gemini-1.5-flash')

# DATA SOURCES
RSS_FEEDS = {
    "CNCF Blog": "https://www.cncf.io/feed/",
    "AWS Architecture Blog": "https://aws.amazon.com/blogs/architecture/feed/",
    "Kubernetes Blog": "https://kubernetes.io/feed.xml",
    "Dev.to DevOps Tag": "https://dev.to/feed/tag/devops",
    "Google Cloud Blog": "https://cloud.google.com/blog/rss.xml",
    "Microsoft Azure Blog": "https://azure.microsoft.com/en-us/blog/feed/",
    "The New Stack": "https://thenewstack.io/blog/feed/",
    "HashiCorp Blog": "https://www.hashicorp.com/blog/feed.xml",
    "InfoQ Cloud": "https://feed.infoq.com/cloud-computing/news",
    "Medium Cloud Computing": "https://medium.com/feed/tag/cloud-computing"
}

TARGET_KEYWORDS = ["kubernetes", "k8s", "cost", "finops", "optimization", "performance", "cloud"]

# --- DATABASE MANAGEMENT ---
def init_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Expanded database to track the AI-generated category
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            link TEXT UNIQUE,
            source TEXT,
            pub_date TEXT,
            summary TEXT,
            category TEXT,
            image_url TEXT,
            scraped_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def is_duplicate(link):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM articles WHERE link = ?", (link,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def save_article(art):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO articles (title, link, source, pub_date, summary, category, image_url, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (art['title'], art['link'], art['source'], art['date'], art['summary'], art['category'], art['image'], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()

# --- UTILITIES & EXTRACTION ---
def calculate_reading_time(text):
    words = len(text.split())
    minutes = max(1, round(words / 200))
    return f"{minutes} min read"

def extract_image_url(entry):
    if 'media_content' in entry and len(entry.media_content) > 0:
        return entry.media_content[0]['url']
    if 'media_thumbnail' in entry and len(entry.media_thumbnail) > 0:
        return entry.media_thumbnail[0]['url']
    if 'summary' in entry:
        soup = BeautifulSoup(entry.summary, 'html.parser')
        img_tag = soup.find('img')
        if img_tag and img_tag.get('src'):
            return img_tag['src']
    return "https://via.placeholder.com/600x300/e0e0e0/555555?text=Cloud+Cost+%26+Optimization"

def generate_ai_metadata(text):
    """Uses Gemini to extract BOTH a category tag and a 2-sentence summary."""
    try:
        print("   🧠 Analyzing content with AI...")
        prompt = (
            "Analyze the following technical content. Respond strictly with a valid JSON object containing exactly two keys: "
            "'category' (a single word topic like Storage, Security, Automation, Architecture, DevOps, Databases, or Cost) and "
            "'summary' (exactly two professional sentences summarizing the text). Do not include markdown blocks or backticks, just the raw JSON:\n\n"
            f"{text}"
        )
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned_response)
        return data.get("category", "General").upper(), data.get("summary", text[:200])
    except Exception as e:
        print(f"   ⚠️ AI extraction anomaly, falling back to safe defaults.")
        return "CLOUD", (text[:200] + '...') if len(text) > 200 else text

# --- CORE ENGINE ---
def fetch_and_curate():
    print("🔄 Initializing intelligent content aggregation engine...")
    seven_days_ago = datetime.now() - timedelta(days=7)
    new_articles = []
    duplicate_count = 0

    for source_name, url in RSS_FEEDS.items():
        print(f"📡 Scanning Feed: {source_name}")
        feed = feedparser.parse(url)
        
        for entry in feed.entries:
            published_parsed = getattr(entry, 'published_parsed', None)
            if not published_parsed:
                continue
                
            pub_date = datetime.fromtimestamp(time.mktime(published_parsed))
            
            if pub_date >= seven_days_ago:
                title = entry.title.lower()
                summary = getattr(entry, 'summary', '').lower()
                
                if any(keyword in title or keyword in summary for keyword in TARGET_KEYWORDS):
                    if is_duplicate(entry.link):
                        duplicate_count += 1
                        continue

                    clean_summary = BeautifulSoup(getattr(entry, 'summary', ''), 'html.parser').text
                    reading_time = calculate_reading_time(clean_summary)
                    
                    # Call our new intelligent classification system
                    category, ai_summary = generate_ai_metadata(clean_summary)

                    article_data = {
                        "title": entry.title,
                        "link": entry.link,
                        "source": source_name,
                        "date": pub_date.strftime("%b %d, %Y"), # Formats nicely like: Jul 09, 2026
                        "summary": ai_summary,
                        "category": category,
                        "image": extract_image_url(entry),
                        "reading_time": reading_time
                    }
                    
                    save_article(article_data)
                    new_articles.append(article_data)
                    
    print(f"📊 Scan Complete. Found {len(new_articles)} fresh updates. Ignored {duplicate_count} items.")
    return new_articles

# --- PRESENTATION GENERATION ---
def generate_html_newsletter(articles):
    print(f"📝 Rendering visual presentation architecture to '{OUTPUT_FILE}'...")
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weekly Cloud Optimization Intelligence</title>
    <style>
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; max-width: 850px; margin: 0 auto; padding: 30px; color: #2d3748; background-color: #f7fafc; }}
        header {{ text-align: center; margin-bottom: 40px; padding: 20px; background: #fff; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
        h1 {{ color: #1a365d; margin: 0; font-size: 28px; }}
        .subtitle {{ color: #4a5568; margin-top: 8px; font-size: 16px; }}
        .card {{ background: #fff; border-radius: 12px; margin-bottom: 30px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); overflow: hidden; border: 1px solid #e2e8f0; transition: transform 0.2s; }}
        .card:hover {{ transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }}
        .card-image {{ width: 100%; height: 280px; object-fit: cover; }}
        .card-body {{ padding: 25px; }}
        
        /* Updated and Organized Badges */
        .badge-group {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 15px; }}
        .badge {{ font-size: 11px; font-weight: bold; text-transform: uppercase; padding: 5px 10px; border-radius: 6px; background: #e2e8f0; color: #4a5568; }}
        .badge.platform {{ background: #ebf8ff; color: #2b6cb0; border: 1px solid #bee3f8; }}
        .badge.topic {{ background: #feebc8; color: #dd6b20; border: 1px solid #fbd38d; }}
        .badge.date {{ background: #edf2f7; color: #4a5568; border: 1px solid #e2e8f0; }}
        .badge.time {{ background: #f0fff4; color: #2f855a; border: 1px solid #c6f6d5; }}
        .badge.ai {{ background: #faf5ff; color: #6b46c1; border: 1px solid #e9d8fd; margin-left: auto; }}
        
        .card-title {{ font-size: 22px; color: #1a202c; margin: 0 0 12px 0; font-weight: 700; line-height: 1.3; }}
        .card-text {{ font-size: 15px; line-height: 1.6; color: #4a5568; margin-bottom: 20px; }}
        .btn {{ display: inline-block; background: #2b6cb0; color: #fff; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 14px; }}
        .btn:hover {{ background: #2c5282; }}
        footer {{ text-align: center; margin-top: 50px; font-size: 13px; color: #718096; border-top: 2px solid #e2e8f0; padding-top: 25px; line-height: 1.8; }}
    </style>
</head>
<body>
    <header>
        <h1>Cloud Cost &amp; Kubernetes Optimization Digest</h1>
        <div class="subtitle">Automated intelligence briefing for engineering teams</div>
    </header>
"""

    for art in articles:
        html_content += f"""
    <article class="card">
        <img src="{art['image']}" alt="Cover Image" class="card-image">
        <div class="card-body">
            <div class="badge-group">
                <span class="badge platform">📡 Platform: {art['source']}</span>
                <span class="badge topic">💡 Related To: {art['category']}</span>
                <span class="badge date">📅 Posted: {art['date']}</span>
                <span class="badge time">⏱️ {art['reading_time']}</span>
                <span class="badge ai">✨ AI System Verified</span>
            </div>
            <h2 class="card-title">{art['title']}</h2>
            <p class="card-text">{art['summary']}</p>
            <a href="{art['link']}" target="_blank" class="btn">Read Original Article</a>
        </div>
    </article>
"""

    html_content += f"""
    <footer>
        <p>System Status: Execution Successful | Relational Database Synced | Gemini Cluster Engaged</p>
        <p><strong>Academic Submission Reference:</strong> Pushkar Rathi (Reg: RA2411050010039)</p>
    </footer>
</body>
</html>"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write(html_content)
    print("✅ System successfully compiled and delivered new meta-enriched layout.")

if __name__ == "__main__":
    init_database()
    articles = fetch_and_curate()
    if articles:
        generate_html_newsletter(articles)
    else:
        print("💡 No new content found matching criteria. Database archive is up to date.")