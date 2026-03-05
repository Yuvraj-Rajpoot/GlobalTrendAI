import streamlit as st
import feedparser
import requests
import re
import json
import os
from datetime import datetime
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="GlobalTrend AI", layout="wide", page_icon="🌍")

# ====================== PERMANENT READ STORAGE ======================
READ_FILE = "read_history.json"

def load_read_ids():
    if os.path.exists(READ_FILE):
        try:
            with open(READ_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_read_ids(read_ids):
    try:
        with open(READ_FILE, "w", encoding="utf-8") as f:
            json.dump(list(read_ids), f)
    except:
        pass

# ====================== PREMIUM CSS ======================
st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #0f0f1e 0%, #1a1a2e 100%); color: #e0e0ff; }
    .main-header { background: linear-gradient(90deg, #1e3a8a, #3b82f6, #60a5fa); padding: 2rem 0; border-radius: 20px; margin-bottom: 2rem; box-shadow: 0 10px 30px rgba(59, 130, 246, 0.3); position: relative; overflow: hidden; }
    .main-header::before { content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%; background: radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%); animation: shine 8s linear infinite; }
    @keyframes shine { 0% { transform: translateX(-30%) translateY(-30%); } 100% { transform: translateX(30%) translateY(30%); } }
    .title { font-size: 3.2rem; font-weight: 800; background: linear-gradient(90deg, #fff, #a5f3fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; margin: 0; }
    .live-dot { display: inline-block; width: 12px; height: 12px; background: #22c55e; border-radius: 50%; box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.4); animation: pulse 2s infinite; margin-right: 8px; }
    @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.4); } }
    div[data-testid="stContainer"] { background: rgba(255,255,255,0.06) !important; backdrop-filter: blur(20px) !important; border: 1px solid rgba(255,255,255,0.1) !important; border-radius: 20px !important; padding: 1.8rem !important; transition: all 0.4s cubic-bezier(0.4,0,0.2,1) !important; height: 100% !important; position: relative; overflow: hidden; }
    div[data-testid="stContainer"]:hover { transform: translateY(-12px) scale(1.03) !important; box-shadow: 0 25px 50px -12px rgb(59 130 246 / 0.4) !important; }
    .unread-badge { position: absolute; top: 16px; right: 16px; background: linear-gradient(90deg, #facc15, #eab308); color: #1e2937; font-size: 0.75rem; font-weight: 700; padding: 4px 14px; border-radius: 9999px; box-shadow: 0 0 15px rgba(250,204,21,0.6); }
    .new-badge { position: absolute; top: 16px; right: 16px; background: linear-gradient(90deg, #ef4444, #f97316); color: white; font-size: 0.75rem; font-weight: 700; padding: 4px 14px; border-radius: 9999px; box-shadow: 0 0 15px rgba(239,68,68,0.7); animation: newpulse 2s infinite; }
    @keyframes newpulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.08); } }
    .source-pill { display: inline-block; background: rgba(147,197,253,0.15); color: #93c5fd; font-size: 0.75rem; padding: 3px 12px; border-radius: 9999px; margin-bottom: 8px; }
    .article-time { color: #94a3b8; font-size: 0.85rem; margin-bottom: 12px; font-weight: 500; }
    .article-title { font-size: 1.25rem; font-weight: 700; line-height: 1.4; color: #e0f2fe; margin-bottom: 12px; }
    .article-desc { color: #cbd5e1; font-size: 0.95rem; line-height: 1.55; }
    .stLinkButton > button { background: linear-gradient(90deg, #3b82f6, #60a5fa) !important; border-radius: 9999px !important; font-weight: 600 !important; }
    .footer-nav { margin-top: 2rem; padding: 1rem; background: rgba(255,255,255,0.05); border-radius: 15px; text-align: center; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1 class="title"><span class="live-dot"></span> GLOBALTREND AI</h1>
    <p style="text-align:center; color:#bae6fd; margin-top:8px; font-size:1.1rem;">Real time Latest trending news from multiple respected newspapers on a single platform</p>
</div>
""", unsafe_allow_html=True)

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("⚙️ Dashboard Controls")
    articles_per_page = st.slider("Articles per page", 6, 24, 18)
    refresh_seconds = st.slider("Auto-refresh every", 30, 180, 60, step=15)
    groq_api_key = st.text_input("Groq API Key (optional)", type="password")
    
    if st.button("🔄 Refresh View Now", use_container_width=True, type="primary"):
        st.rerun()
    
    if st.button("✅ Mark ALL as Read", use_container_width=True, type="secondary"):
        if "all_news" in st.session_state:
            st.session_state.read_ids.update(a.get("article_id") for a in st.session_state.all_news)
            save_read_ids(st.session_state.read_ids)
            st.toast("All articles marked as read forever!", icon="✅")
    


try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=refresh_seconds * 1000, limit=None, key="newsrefresh")
except:
    st.sidebar.warning("pip install streamlit-autorefresh")

# ====================== FEEDS ======================
FEEDS = [
    {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "Reuters World", "url": "https://feeds.reuters.com/Reuters/worldNews"},
    {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"name": "The Guardian", "url": "https://www.theguardian.com/world/rss"},
    {"name": "France 24", "url": "https://www.france24.com/en/rss"},
    {"name": "CNN World", "url": "http://rss.cnn.com/rss/cnn_world.rss"},
    {"name": "NPR World", "url": "https://feeds.npr.org/1004/rss.xml"},
    {"name": "AP News", "url": "https://apnews.com/rss"},
    {"name": "Deutsche Welle", "url": "https://rss.dw.com/rdf/rss-en-world"},
    {"name": "Euronews", "url": "https://www.euronews.com/rss/rss_en_world.xml"},
    {"name": "NY Times World", "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"},
    {"name": "News18 World", "url": "https://www.news18.com/rss/world.xml"},
    {"name": "Moscow Times", "url": "https://www.themoscowtimes.com/rss/news"},
]

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"}

def get_article_id(article):
    return hashlib.md5((article.get('title','') + article.get('link','')).encode()).hexdigest()[:12]

def get_exact_time(article):
    parsed = article.get('published_parsed')
    if parsed:
        try:
            local_time = time.localtime(time.mktime(parsed))
            return time.strftime("%d %b %Y • %H:%M", local_time)
        except:
            pass
    raw = article.get('published') or article.get('pubDate') or article.get('updated')
    return raw.replace(' GMT', '').replace(' UTC', '').strip()[:60] if raw else "Date not available"

def fetch_single_feed(feed):
    try:
        r = requests.get(feed["url"], headers=headers, timeout=10)
        if r.status_code == 200:
            parsed = feedparser.parse(r.content)
            for entry in parsed.entries:
                entry["source_name"] = feed["name"]
                entry["article_id"] = get_article_id(entry)
            return parsed.entries
    except:
        return []
    return []

@st.cache_data(ttl=120, show_spinner=False)
def fetch_latest_news():
    all_entries = []
    with ThreadPoolExecutor(max_workers=13) as executor:
        future_to_feed = {executor.submit(fetch_single_feed, feed): feed for feed in FEEDS}
        for future in as_completed(future_to_feed):
            entries = future.result()
            if entries:
                all_entries.extend(entries)
    seen = set()
    unique = []
    for item in all_entries:
        aid = item.get("article_id")
        if aid and aid not in seen:
            seen.add(aid)
            unique.append(item)
    unique.sort(key=lambda x: x.get('published_parsed', (0,0,0,0,0,0)), reverse=True)
    return unique[:50]

# ====================== 6-PAGE ROLLING HISTORY ======================
if "all_news" not in st.session_state: st.session_state.all_news = []
if "read_ids" not in st.session_state: st.session_state.read_ids = load_read_ids()
if "previous_ids" not in st.session_state: st.session_state.previous_ids = set()
if 'current_page' not in st.session_state: st.session_state.current_page = 1

latest = fetch_latest_news()

new_articles_list = []
existing_ids = {a.get("article_id") for a in st.session_state.all_news}
for article in latest:
    aid = article.get("article_id")
    if aid and aid not in existing_ids:
        new_articles_list.append(article)

if new_articles_list:
    st.session_state.all_news = new_articles_list + st.session_state.all_news

max_articles = articles_per_page * 6
if len(st.session_state.all_news) > max_articles:
    st.session_state.all_news = st.session_state.all_news[:max_articles]

if len(new_articles_list) > 0 and len(st.session_state.previous_ids) > 0:
    st.toast(f"🔔 {len(new_articles_list)} brand new stories added on Page 1!", icon="🆕")

st.session_state.previous_ids = {a.get("article_id") for a in st.session_state.all_news}

# ====================== DISPLAY ======================
page = st.session_state.current_page
current_page_articles = st.session_state.all_news[(page-1)*articles_per_page : page*articles_per_page]

st.subheader(f"🌐 Page {page}/6 • Live Trending Worldwide • {datetime.now().strftime('%H:%M:%S')} • {len(st.session_state.all_news)}/{max_articles} stored • {sum(1 for a in st.session_state.all_news if a.get('article_id') not in st.session_state.read_ids)} unread")

cols = st.columns(3)
for i, article in enumerate(current_page_articles):
    aid = article.get("article_id")
    is_unread = aid not in st.session_state.read_ids
    
    with cols[i % 3]:
        container = st.container(border=True)
        with container:
            if is_unread:
                st.markdown('<div class="unread-badge">🟡 UNREAD</div>', unsafe_allow_html=True)
            
            st.markdown(f'<div class="source-pill">{article.get("source_name", "News")}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="article-time">📅 {get_exact_time(article)}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="article-title">{article.get("title", "No title")}</div>', unsafe_allow_html=True)
            
            desc = re.sub(r'<[^>]+>', '', article.get("description", "") or "")
            st.markdown(f'<div class="article-desc">{desc[:185]}{"..." if len(desc) > 185 else ""}</div>', unsafe_allow_html=True)
            
            if is_unread:
                if st.button("✓ Mark as Read", key=f"read_{aid}_{page}", use_container_width=True):
                    st.session_state.read_ids.add(aid)
                    save_read_ids(st.session_state.read_ids)
                    st.toast("✅ Marked as read forever!", icon="✅")
                    st.rerun()
        
        if article.get("link"):
            st.link_button("Read Full Story →", article["link"], use_container_width=True)

# ====================== FOOTER WITH PREV / CURRENT / NEXT ======================
st.divider()
st.markdown('<div class="footer-tabs">', unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    if st.button("← Previous", use_container_width=True, disabled=(page == 1)):
        st.session_state.current_page = page - 1
        st.rerun()

with col2:
    st.markdown(f"<h3 style='text-align:center; margin:0;'>Page {page} of 6</h3>", unsafe_allow_html=True)

with col3:
    if st.button("Next →", use_container_width=True, disabled=(page == 6)):
        st.session_state.current_page = page + 1
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# Debug + AI Digest


st.divider()
st.subheader("🤖 GlobalTrend AI")
if groq_api_key and st.session_state.all_news and st.button("✨ Generate Smart World Digest", use_container_width=True):
    try:
        from groq import Groq
        with st.spinner("Analyzing..."):
            client = Groq(api_key=groq_api_key)
            headlines = "\n".join([f"- {a.get('title')}" for a in st.session_state.all_news[:15]])
            prompt = f"""You are a world-class geopolitical analyst. From these headlines only, identify the **top 5 global stories right now**.\n\nHeadlines:\n{headlines}\n\nFormat exactly like this:\n**Story Title**\n1-2 sentence insight + global impact."""
            response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], temperature=0.7, max_tokens=900)
            st.markdown(response.choices[0].message.content)
    except Exception as e:
        st.error(f"AI Error: {e}")
else:
    st.markdown(
    """
    <div style="
        background: linear-gradient(90deg, #1e3a8a, #3b82f6, #60a5fa);
        padding: 0.5rem 1rem;
        border-radius: 30px;
        margin: 1.5rem 0;
        color: white;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 1.1em;">
            <span>~ Yuvraj Rajpoot</span>
            <a href="https://www.instagram.com/_yuvraj__rajpoot_/">
                <img src="https://upload.wikimedia.org/wikipedia/commons/a/a5/Instagram_icon.png" 
                     style="height: 1.3em; width: auto; vertical-align: middle; filter: brightness(1.1);">
            </a>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)
