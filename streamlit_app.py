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
import pandas as pd
import yfinance as yf
import folium
from streamlit_folium import st_folium

# ====================== PERFORMANCE OPTIMIZATIONS ======================
# Reduce timeout and increase workers for faster loading
import socket
socket.setdefaulttimeout(3)  # Faster timeout for hung connections

st.set_page_config(page_title="GlobalTrend AI", layout="wide", page_icon="🌍")

# ====================== PERMANENT READ STORAGE ======================
READ_FILE = "read_history.json"
CACHE_FILE = "news_cache.json"

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

# ====================== PERSISTENT CACHE FOR INSTANT LOADING ======================
def load_cached_news():
    """Load previously cached news for instant display"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_cached_news(news_list):
    """Save news to disk for next session"""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(news_list[:200], f)  # Save top 200
    except:
        pass

# ====================== PREMIUM CSS (with perfect world map fix) ======================
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
    .footer-tabs { margin-top: 2rem; padding: 1rem; background: rgba(255,255,255,0.05); border-radius: 15px; }
    .prediction-card { background: rgba(255,255,255,0.06); border: 1px solid rgba(251,191,36,0.3); border-radius: 16px; padding: 1.4rem; margin-bottom: 1rem; transition: all 0.3s; }
    .prediction-card:hover { transform: translateY(-4px); box-shadow: 0 10px 30px rgba(251,191,36,0.2); }
    .leaflet-container {
        width: 100% !important;
        height: 100% !important;
        border-radius: 20px !important;
        box-shadow: 0 25px 50px -12px rgb(59 130 246 / 0.4) !important;
        overflow: hidden !important;
        background: #0f0f1e !important;
    }
    div[data-testid="stMarkdownContainer"] > div > div > div > div > iframe,
    .stFolium,
    .leaflet-container {
        max-width: 100% !important;
        max-height: 100% !important;
        overflow: hidden !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1 class="title"><span class="live-dot"></span> GLOBALTREND AI</h1>
    <p style="text-align:center; color:#bae6fd; margin-top:8px; font-size:1.1rem;">Everything you need to stay aware — all in one powerful platform. News. Live TV. Market intelligence. World monitoring. Predictions. 🌍📊📡</p>
</div>
""", unsafe_allow_html=True)

# ====================== AUTO REFRESH (MOVE THIS BEFORE TABS) ======================
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=refresh_seconds * 1000, limit=None, key="newsrefresh")
except:
    pass

# ====================== MAIN TABS ======================
tab_news, tab_live, tab_stocks, tab_trending, tab_map, tab_predictions = st.tabs([
    "📰 News Archive",
    "📺 Live YouTube TV Streams",
    "📈 Live Markets",
    "🌦️ Global Weather",
    "🌍 World News Activity Map",
    "🔮 Real Economist Forecasts"
])

# ====================== NEWS ARCHIVE TAB ======================
# ====================== NEWS ARCHIVE TAB ======================
with tab_news:
    
    # ====================== DEFINE FUNCTIONS FIRST ======================
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"}
    
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
    
    def is_within_24_hours(article):
        """Check if article is within the last 24 hours"""
        parsed = article.get('published_parsed')
        if parsed:
            try:
                article_time = time.mktime(parsed)
                current_time = time.time()
                # 24 hours = 86400 seconds
                return (current_time - article_time) <= 86400
            except:
                pass
        # If we can't parse the time, don't include the article (strict filtering)
        return False
    
    def filter_recent_articles(articles):
        """Filter articles to keep only those from the last 24 hours"""
        return [a for a in articles if is_within_24_hours(a)]
    
    def fetch_single_feed(feed):
        try:
            r = requests.get(feed["url"], headers=headers, timeout=5)
            if r.status_code == 200:
                parsed = feedparser.parse(r.content)
                for entry in parsed.entries[:15]:
                    entry["source_name"] = feed["name"]
                    entry["article_id"] = get_article_id(entry)
                return parsed.entries[:15]
        except:
            return []
        return []
    
    @st.cache_data(ttl=120, show_spinner=False)
    def fetch_latest_news():
        all_entries = []
        with ThreadPoolExecutor(max_workers=20) as executor:
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
        return unique[:100]
    
    # ====================== INITIALIZE SESSION STATE WITH CACHE ======================
    if "all_news" not in st.session_state:
        # Load from cache first for instant display, then filter to last 24 hours
        cached = load_cached_news()
        st.session_state.all_news = filter_recent_articles(cached)
    if "read_ids" not in st.session_state: 
        st.session_state.read_ids = load_read_ids()
    if "previous_ids" not in st.session_state: 
        st.session_state.previous_ids = set()
    if 'current_page' not in st.session_state: 
        st.session_state.current_page = 1
    
    # ====================== SIDEBAR ======================
    with st.sidebar:
        st.header("⚙️ Dashboard Controls")
        articles_per_page = st.slider("Articles per page", 6, 24, 18)
        refresh_seconds = st.slider("Auto-refresh every", 30, 180, 60, step=15)
        st.session_state['refresh_seconds'] = refresh_seconds
        groq_api_key = st.text_input("", type="password")
        
        if st.button("🔄 Refresh View Now", use_container_width=True, type="primary"):
            st.cache_data.clear()
            st.rerun()
        
        if st.button("✅ Mark ALL as Read", use_container_width=True, type="secondary"):
            if "all_news" in st.session_state and st.session_state.all_news:
                st.session_state.read_ids.update(a.get("article_id") for a in st.session_state.all_news)
                save_read_ids(st.session_state.read_ids)
                st.toast("All articles marked as read forever!", icon="✅")
                st.rerun()
        
        st.markdown("---")
        st.markdown("~ Yuvraj Rajpoot")
    
    # ====================== FETCH AND MERGE NEWS ======================
    latest = fetch_latest_news()
    
    # Filter latest to only include articles from last 24 hours
    latest = filter_recent_articles(latest)
    
    new_articles_list = [article for article in latest if article.get("article_id") not in {a.get("article_id") for a in st.session_state.all_news}]
    
    if new_articles_list:
        st.session_state.all_news = new_articles_list + st.session_state.all_news
    
    # Filter entire list to keep only last 24 hours of news
    st.session_state.all_news = filter_recent_articles(st.session_state.all_news)
    
    # Also cap at 500 articles max as safety limit
    max_articles = 500
    if len(st.session_state.all_news) > max_articles:
        st.session_state.all_news = st.session_state.all_news[:max_articles]
    
    # Save to cache for next session (non-blocking)
    save_cached_news(st.session_state.all_news)
    
    # Calculate total pages dynamically
    total_pages = max(1, (len(st.session_state.all_news) + articles_per_page - 1) // articles_per_page)
    
    # Ensure current page doesn't exceed available pages
    if st.session_state.current_page > total_pages:
        st.session_state.current_page = total_pages
    if st.session_state.current_page < 1:
        st.session_state.current_page = 1
    
    # Notify about new articles
    if len(new_articles_list) > 0 and len(st.session_state.previous_ids) > 0:
        st.toast(f"🔔 {len(new_articles_list)} brand new stories added!", icon="🆕")
    
    st.session_state.previous_ids = {a.get("article_id") for a in st.session_state.all_news}
    
    # Get current page articles
    page = st.session_state.current_page
    start_idx = (page - 1) * articles_per_page
    end_idx = start_idx + articles_per_page
    current_page_articles = st.session_state.all_news[start_idx:end_idx]
    
    # Calculate unread count
    unread_count = sum(1 for a in st.session_state.all_news if a.get('article_id') not in st.session_state.read_ids)
    
    # ====================== HEADER WITH USER'S LOCAL TIME (FIXED) ======================
    st.markdown(f"""
    <h3 style="margin-bottom: 0;">🌐 Page {page}/{total_pages} • Live Trending Worldwide • 
    <span id="local-clock">{datetime.now().strftime('%H:%M:%S')}</span> • 
    {len(st.session_state.all_news)}/{max_articles} stored (24h) • {unread_count} unread</h3>
    <script>
        function updateClock() {{
            var now = new Date();
            var h = String(now.getHours()).padStart(2, '0');
            var m = String(now.getMinutes()).padStart(2, '0');
            var s = String(now.getSeconds()).padStart(2, '0');
            var el = document.getElementById('local-clock');
            if (el) el.textContent = h + ':' + m + ':' + s;
        }}
        updateClock();
        setInterval(updateClock, 1000);
    </script>
    """, unsafe_allow_html=True)
    
    # Quick stats bar
    stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)
    with stats_col1:
        st.metric("📰 Total Articles", len(st.session_state.all_news))
    with stats_col2:
        st.metric("🆕 Unread", unread_count)
    with stats_col3:
        st.metric("✅ Read", len(st.session_state.all_news) - unread_count)
    with stats_col4:
        st.metric("📄 Total Pages", total_pages)
    
    st.markdown("---")
    
    # ====================== DISPLAY ARTICLES IN GRID ======================
    if current_page_articles:
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
                    
                    btn_label = "✓ Mark as Read" if is_unread else "✓ Marked as Read"
                    btn_type = "primary" if is_unread else "secondary"
                    
                    if st.button(
                        btn_label,
                        key=f"read_{aid}_{page}_{i}",
                        use_container_width=True,
                        disabled=not is_unread,
                        type=btn_type
                    ):
                        if is_unread:
                            st.session_state.read_ids.add(aid)
                            save_read_ids(st.session_state.read_ids)
                            st.toast("✅ Marked as read forever!", icon="✅")
                            st.rerun()
                if article.get("link"):
                    st.link_button("Read Full Story →", article["link"], use_container_width=True)
    else:
        st.info("📭 No articles on this page. Try going to Page 1 or refresh the news.")
    
    st.divider()
    
    # ====================== ENHANCED PAGINATION ======================
    st.markdown('<div class="footer-tabs">', unsafe_allow_html=True)
    
    nav_col1, nav_col2, nav_col3, nav_col4, nav_col5 = st.columns([1, 1, 2, 1, 1])
    
    with nav_col1:
        if st.button("⏮️ First", use_container_width=True, disabled=(page == 1), key="first_page"):
            st.session_state.current_page = 1
            st.rerun()
    
    with nav_col2:
        if st.button("← Prev", use_container_width=True, disabled=(page == 1), key="prev_page"):
            st.session_state.current_page = page - 1
            st.rerun()
    
    with nav_col3:
        st.markdown(f"<h3 style='text-align:center; margin:0; padding: 10px 0;'>Page {page} of {total_pages}</h3>", unsafe_allow_html=True)
    
    with nav_col4:
        if st.button("Next →", use_container_width=True, disabled=(page >= total_pages), key="next_page"):
            st.session_state.current_page = page + 1
            st.rerun()
    
    with nav_col5:
        if st.button("Last ⏭️", use_container_width=True, disabled=(page >= total_pages), key="last_page"):
            st.session_state.current_page = total_pages
            st.rerun()
    
    if total_pages > 1:
        st.markdown("<p style='text-align:center; margin:15px 0 5px 0; color:#94a3b8;'>⚡ Quick Jump to Page:</p>", unsafe_allow_html=True)
        
        if total_pages <= 10:
            page_range = list(range(1, total_pages + 1))
        else:
            start_page = max(1, page - 4)
            end_page = min(total_pages, start_page + 9)
            if end_page - start_page < 9:
                start_page = max(1, end_page - 9)
            page_range = list(range(start_page, end_page + 1))
        
        jump_cols = st.columns(len(page_range))
        for idx, p in enumerate(page_range):
            with jump_cols[idx]:
                btn_style = "primary" if p == page else "secondary"
                if st.button(f"{p}", key=f"jump_{p}", use_container_width=True, type=btn_style):
                    st.session_state.current_page = p
                    st.rerun()
        
        st.markdown("")
        input_col1, input_col2, input_col3 = st.columns([1, 2, 1])
        with input_col2:
            col_a, col_b = st.columns([3, 1])
            with col_a:
                new_page = st.number_input(
                    "Go to page:",
                    min_value=1,
                    max_value=total_pages,
                    value=page,
                    step=1,
                    key="direct_page_input"
                )
            with col_b:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Go", key="go_to_page", type="primary"):
                    if new_page != page:
                        st.session_state.current_page = new_page
                        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    if st.session_state.all_news:
        st.markdown("---")
        time_col1, time_col2, time_col3 = st.columns(3)
        
        with time_col1:
            newest = st.session_state.all_news[0]
            st.markdown(f"**🆕 Newest:** {get_exact_time(newest)}")
        
        with time_col2:
            oldest = st.session_state.all_news[-1]
            st.markdown(f"**📜 Oldest:** {get_exact_time(oldest)}")
        
        with time_col3:
            sources_count = len(set(a.get("source_name", "Unknown") for a in st.session_state.all_news))
            st.markdown(f"**📡 Sources:** {sources_count} active feeds")
    
    st.divider()
    
    if groq_api_key and st.session_state.all_news:
        if st.button("✨ Generate Smart World Digest", use_container_width=True, key="ai_digest"):
            try:
                from groq import Groq
                with st.spinner("🤖 Analyzing global trends..."):
                    client = Groq(api_key=groq_api_key)
                    headlines = "\n".join([f"- {a.get('title')}" for a in st.session_state.all_news[:20]])
                    prompt = f"""You are a world-class geopolitical analyst. From these headlines only, identify the **top 5 global stories right now**.

Headlines:
{headlines}

Format exactly like this:
**Story Title**
1-2 sentence insight + global impact."""
                    response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7,
                        max_tokens=900
                    )
                    st.markdown("### 🤖 AI World Digest")
                    st.markdown(response.choices[0].message.content)
            except Exception as e:
                st.error(f"AI Error: {e}")
    
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

# ====================== LIVE TV TAB ======================
# ====================== LIVE TV TAB ======================
# ====================== LIVE TV TAB ======================
with tab_live:
    st.title("📺 Live YouTube TV Streams")
    st.caption("All streams using verified direct embeds")
    
    # First row - 2 channels
    row1_cols = st.columns(2)
    with row1_cols[0]:
        st.subheader("Al Jazeera English Live")
        st.components.v1.iframe("https://www.youtube.com/embed/gCNeDWCI0vo", height=380, scrolling=False)
        st.caption("Live 24/7 • Refresh page if needed")
    
    with row1_cols[1]:
        st.subheader("France 24 English Live")
        st.components.v1.iframe("https://www.youtube.com/embed/Ap-UM1O9RBU", height=380, scrolling=False)
        st.caption("Live 24/7 • Refresh page if needed")
    
    # Second row - 2 channels
    row2_cols = st.columns(2)
    with row2_cols[0]:
        st.subheader("DW News Live")
        st.components.v1.iframe("https://www.youtube.com/embed/LuKwFajn37U", height=380, scrolling=False)
        st.caption("Live 24/7 • Refresh page if needed")
    
    with row2_cols[1]:
        st.subheader("Euronews Live")
        st.components.v1.iframe("https://www.youtube.com/embed/pykpO5kQJ98", height=380, scrolling=False)
        st.caption("Live 24/7 • Refresh page if needed")
    
    # Third row - 2 channels
    row3_cols = st.columns(2)
    with row3_cols[0]:
        st.subheader("News18")
        st.components.v1.iframe("https://www.youtube.com/embed/nya02XlHG1Q", height=380, scrolling=False)
        st.caption("Live 24/7 • Refresh page if needed")
    
    with row3_cols[1]:
        st.subheader("Tv9 Bharatvarsh")
        st.components.v1.iframe("https://www.youtube.com/embed/nSpwwcHVp80", height=380, scrolling=False)
        st.caption("Live 24/7 • Refresh page if needed")
    
    # Fourth row - Bloomberg and Career 247
    row4_cols = st.columns(2)
    with row4_cols[0]:
        st.subheader("Bloomberg")
        st.components.v1.iframe("https://www.youtube.com/embed/iEpJwprxDdk", height=380, scrolling=False)
        st.caption("Live 24/7 • Refresh page if needed")
    
    with row4_cols[1]:
        st.subheader("Career 247 - Latest Uploads")
        # Using channel uploads playlist (UC -> UU conversion for uploads playlist)
        # Channel ID: UCHyu2gwfAkOXWroIjvxVUCg
        # Uploads Playlist: UUHyu2gwfAkOXWroIjvxVUCg
        st.components.v1.iframe(
            "https://www.youtube.com/embed/videoseries?list=UUHyu2gwfAkOXWroIjvxVUCg",
            height=380,
            scrolling=False
        )
        st.caption("📺 Latest uploads playlist • Click to browse & play videos")
# ====================== STOCK MARKETS TAB ======================
with tab_stocks:
    st.title("📈 Live Markets – Gold, Silver, Crypto & Stocks")
    st.caption("⚡ True real-time stocks and market analysis")
    
    @st.cache_data(ttl=60, show_spinner=False)
    def fetch_market_data():
        assets = {
            "Gold (USD/oz)": "GC=F",
            "Silver (USD/oz)": "SI=F",
            "Bitcoin (USD)": "BTC-USD",
            "Ethereum (USD)": "ETH-USD",
            "US Dollar Index": "DX-Y.NYB",
            "USD/RUB": "USDRUB=X",
            "USD/INR": "USDINR=X",
            "Tesla": "TSLA",
            "Microsoft": "MSFT",
            "Amazon": "AMZN",
            "Reliance": "RELIANCE.NS",
            "WTI Crude Oil": "CL=F",
            "INR/RUB": "INRRUB=X"
        }
        data = []
        
        def fetch_single_asset(name, symbol):
            try:
                ticker = yf.Ticker(symbol)
                fast_info = ticker.fast_info
                current = fast_info.get('lastPrice') or fast_info.get('regularMarketPrice')
                previous = fast_info.get('previousClose')
                
                if current and previous:
                    change = ((current - previous) / previous) * 100
                    return {
                        "Asset": name,
                        "Price": round(float(current), 4),
                        "Change %": round(change, 2)
                    }
            except:
                pass
            return None
        
        with ThreadPoolExecutor(max_workers=13) as executor:
            futures = {executor.submit(fetch_single_asset, name, symbol): name for name, symbol in assets.items()}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    data.append(result)
        
        return data
    
    data = fetch_market_data()
    
    if data:
        df = pd.DataFrame(data)
        styled = df.style.format({"Price": "{:.4f}", "Change %": "{:.2f}"}).apply(
            lambda x: ['color: lime' if v > 0 else 'color: red' for v in x], subset=["Change %"]
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)
        st.caption("🔴 Powered by Yahoo Finance • Cached for 60 seconds for speed")
    else:
        st.info("Loading market data...")

# ====================== GLOBAL WEATHER TAB ======================
with tab_trending:
    st.title("🌍 Live Weather Satellite & Radar Map")
    st.caption("Real-time satellite imagery, precipitation radar, wind patterns, temperature & weather conditions • Click anywhere on the map to get instant weather data for that location • Data from Open-Meteo, RainViewer & ESRI")
    
    @st.cache_data(ttl=300, show_spinner=False)
    def get_rainviewer_frames():
        try:
            r = requests.get("https://api.rainviewer.com/public/weather-maps.json", timeout=10)
            data = r.json()
            past_frames = data.get('radar', {}).get('past', [])
            nowcast_frames = data.get('radar', {}).get('nowcast', [])
            return {
                "past": past_frames,
                "nowcast": nowcast_frames,
                "host": data.get('host', 'https://tilecache.rainviewer.com')
            }
        except:
            return None
    
    @st.cache_data(ttl=600, show_spinner=False)
    def get_global_weather():
        cities = [
            {"name": "New York", "lat": 40.7128, "lon": -74.0060, "country": "USA"},
            {"name": "Los Angeles", "lat": 34.0522, "lon": -118.2437, "country": "USA"},
            {"name": "London", "lat": 51.5074, "lon": -0.1278, "country": "UK"},
            {"name": "Paris", "lat": 48.8566, "lon": 2.3522, "country": "France"},
            {"name": "Berlin", "lat": 52.5200, "lon": 13.4049, "country": "Germany"},
            {"name": "Moscow", "lat": 55.7558, "lon": 37.6173, "country": "Russia"},
            {"name": "Tokyo", "lat": 35.6762, "lon": 139.6503, "country": "Japan"},
            {"name": "Beijing", "lat": 39.9042, "lon": 116.4074, "country": "China"},
            {"name": "Shanghai", "lat": 31.2304, "lon": 121.4737, "country": "China"},
            {"name": "Hong Kong", "lat": 22.3193, "lon": 114.1694, "country": "China"},
            {"name": "Singapore", "lat": 1.3521, "lon": 103.8198, "country": "Singapore"},
            {"name": "Dubai", "lat": 25.2048, "lon": 55.2708, "country": "UAE"},
            {"name": "Mumbai", "lat": 19.0760, "lon": 72.8777, "country": "India"},
            {"name": "Delhi", "lat": 28.6139, "lon": 77.2090, "country": "India"},
            {"name": "Sydney", "lat": -33.8688, "lon": 151.2093, "country": "Australia"},
            {"name": "Melbourne", "lat": -37.8136, "lon": 144.9631, "country": "Australia"},
            {"name": "São Paulo", "lat": -23.5505, "lon": -46.6333, "country": "Brazil"},
            {"name": "Rio de Janeiro", "lat": -22.9068, "lon": -43.1729, "country": "Brazil"},
            {"name": "Mexico City", "lat": 19.4326, "lon": -99.1332, "country": "Mexico"},
            {"name": "Buenos Aires", "lat": -34.6037, "lon": -58.3816, "country": "Argentina"},
            {"name": "Cairo", "lat": 30.0444, "lon": 31.2357, "country": "Egypt"},
            {"name": "Lagos", "lat": 6.5244, "lon": 3.3792, "country": "Nigeria"},
            {"name": "Johannesburg", "lat": -26.2041, "lon": 28.0473, "country": "South Africa"},
            {"name": "Istanbul", "lat": 41.0082, "lon": 28.9784, "country": "Turkey"},
            {"name": "Bangkok", "lat": 13.7563, "lon": 100.5018, "country": "Thailand"},
            {"name": "Seoul", "lat": 37.5665, "lon": 126.9780, "country": "South Korea"},
            {"name": "Jakarta", "lat": -6.2088, "lon": 106.8456, "country": "Indonesia"},
            {"name": "Manila", "lat": 14.5995, "lon": 120.9842, "country": "Philippines"},
            {"name": "Toronto", "lat": 43.6532, "lon": -79.3832, "country": "Canada"},
            {"name": "Madrid", "lat": 40.4168, "lon": -3.7038, "country": "Spain"},
            {"name": "Rome", "lat": 41.9028, "lon": 12.4964, "country": "Italy"},
            {"name": "Vienna", "lat": 48.2082, "lon": 16.3738, "country": "Austria"},
            {"name": "Warsaw", "lat": 52.2297, "lon": 21.0122, "country": "Poland"},
            {"name": "Athens", "lat": 37.9838, "lon": 23.7275, "country": "Greece"},
            {"name": "Stockholm", "lat": 59.3293, "lon": 18.0686, "country": "Sweden"},
            {"name": "Oslo", "lat": 59.9139, "lon": 10.7522, "country": "Norway"},
            {"name": "Helsinki", "lat": 60.1699, "lon": 24.9384, "country": "Finland"},
            {"name": "Reykjavik", "lat": 64.1466, "lon": -21.9426, "country": "Iceland"},
            {"name": "Tel Aviv", "lat": 32.0853, "lon": 34.7818, "country": "Israel"},
            {"name": "Riyadh", "lat": 24.7136, "lon": 46.6753, "country": "Saudi Arabia"},
        ]
        
        weather_data = []
        
        for city in cities:
            try:
                url = f"https://api.open-meteo.com/v1/forecast?latitude={city['lat']}&longitude={city['lon']}&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,precipitation,cloud_cover,surface_pressure&timezone=auto"
                r = requests.get(url, timeout=5)
                data = r.json()
                current = data.get('current', {})
                weather_data.append({
                    "name": city['name'],
                    "country": city['country'],
                    "lat": city['lat'],
                    "lon": city['lon'],
                    "temp": current.get('temperature_2m'),
                    "feels_like": current.get('apparent_temperature'),
                    "humidity": current.get('relative_humidity_2m'),
                    "wind_speed": current.get('wind_speed_10m'),
                    "wind_dir": current.get('wind_direction_10m'),
                    "wind_gusts": current.get('wind_gusts_10m'),
                    "precip": current.get('precipitation'),
                    "clouds": current.get('cloud_cover'),
                    "pressure": current.get('surface_pressure'),
                    "weather_code": current.get('weather_code', 0),
                    "time": current.get('time', '')
                })
            except:
                pass
        return weather_data
    
    def get_weather_for_location(lat, lon):
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,precipitation,cloud_cover,surface_pressure,is_day&hourly=temperature_2m,precipitation_probability,weather_code&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code,sunrise,sunset&timezone=auto&forecast_days=3"
            r = requests.get(url, timeout=10)
            data = r.json()
            return data
        except:
            return None
    
    def get_location_name(lat, lon):
        try:
            url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&zoom=10"
            headers = {"User-Agent": "GlobalTrendAI/1.0"}
            r = requests.get(url, headers=headers, timeout=5)
            data = r.json()
            address = data.get('address', {})
            name = address.get('city') or address.get('town') or address.get('village') or address.get('county') or address.get('state') or address.get('region') or "Unknown Location"
            country = address.get('country', '')
            return name, country
        except:
            return "Unknown Location", ""
    
    def get_weather_info(code):
        weather_codes = {
            0: ("☀️", "Clear Sky", "#FFD700"),
            1: ("🌤️", "Mainly Clear", "#FFE066"),
            2: ("⛅", "Partly Cloudy", "#B0C4DE"),
            3: ("☁️", "Overcast", "#808080"),
            45: ("🌫️", "Fog", "#C0C0C0"),
            48: ("🌫️", "Depositing Rime Fog", "#A9A9A9"),
            51: ("🌦️", "Light Drizzle", "#87CEEB"),
            53: ("🌦️", "Moderate Drizzle", "#6CA6CD"),
            55: ("🌧️", "Dense Drizzle", "#4A708B"),
            56: ("🌨️", "Freezing Drizzle", "#B0E0E6"),
            57: ("🌨️", "Heavy Freezing Drizzle", "#ADD8E6"),
            61: ("🌧️", "Slight Rain", "#6495ED"),
            63: ("🌧️", "Moderate Rain", "#4169E1"),
            65: ("🌧️", "Heavy Rain", "#0000CD"),
            66: ("🌨️", "Freezing Rain", "#00CED1"),
            67: ("🌨️", "Heavy Freezing Rain", "#008B8B"),
            71: ("❄️", "Slight Snow", "#E0FFFF"),
            73: ("❄️", "Moderate Snow", "#AFEEEE"),
            75: ("❄️", "Heavy Snow", "#00FFFF"),
            77: ("🌨️", "Snow Grains", "#F0FFFF"),
            80: ("🌧️", "Slight Showers", "#87CEFA"),
            81: ("🌧️", "Moderate Showers", "#00BFFF"),
            82: ("🌧️", "Violent Showers", "#1E90FF"),
            85: ("🌨️", "Slight Snow Showers", "#E6E6FA"),
            86: ("🌨️", "Heavy Snow Showers", "#D8BFD8"),
            95: ("⛈️", "Thunderstorm", "#FF4500"),
            96: ("⛈️", "Thunderstorm + Hail", "#FF6347"),
            99: ("⛈️", "Severe Thunderstorm", "#DC143C"),
        }
        return weather_codes.get(code, ("🌡️", "Unknown", "#94a3b8"))
    
    def get_wind_direction_arrow(degrees):
        if degrees is None:
            return "○"
        directions = ["↓", "↙", "←", "↖", "↑", "↗", "→", "↘"]
        index = round(degrees / 45) % 8
        return directions[index]
    
    def get_temp_color(temp):
        if temp is None:
            return "#94a3b8"
        if temp < -20:
            return "#7c3aed"
        elif temp < -10:
            return "#3b82f6"
        elif temp < 0:
            return "#06b6d4"
        elif temp < 10:
            return "#22d3ee"
        elif temp < 20:
            return "#22c55e"
        elif temp < 30:
            return "#eab308"
        elif temp < 40:
            return "#f97316"
        else:
            return "#ef4444"
    
    if 'clicked_weather' not in st.session_state:
        st.session_state.clicked_weather = None
    if 'clicked_coords' not in st.session_state:
        st.session_state.clicked_coords = None
    if 'clicked_location_name' not in st.session_state:
        st.session_state.clicked_location_name = None
    
    st.markdown("---")
    ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4, ctrl_col5 = st.columns(5)
    
    with ctrl_col1:
        base_layer = st.selectbox("🗺️ Base Map", ["Satellite", "Dark", "Terrain", "Light", "Streets"], index=0)
    
    with ctrl_col2:
        overlay_type = st.selectbox("🌦️ Weather Overlay", ["None", "Precipitation Radar", "Cloud Cover", "Temperature", "Wind", "Pressure"], index=1)
    
    with ctrl_col3:
        show_weather_stations = st.checkbox("📍 Weather Stations", value=True)
    
    with ctrl_col4:
        show_wind_arrows = st.checkbox("💨 Wind Arrows", value=False)
    
    with ctrl_col5:
        if st.button("🔄 Refresh All Data", use_container_width=True, type="primary"):
            st.cache_data.clear()
            st.session_state.clicked_weather = None
            st.session_state.clicked_coords = None
            st.session_state.clicked_location_name = None
            st.rerun()
    
    st.info("👆 **Click anywhere on the map** to get instant weather data for that exact location! The weather panel will appear below the map.")
    
    radar_data = get_rainviewer_frames()
    selected_frame = None
    radar_opacity = 0.7
    
    if overlay_type == "Precipitation Radar" and radar_data:
        st.markdown("#### 🕐 Radar Timeline")
        all_frames = radar_data.get('past', []) + radar_data.get('nowcast', [])
        
        if all_frames:
            frame_times = []
            for frame in all_frames:
                ts = frame.get('time', 0)
                dt = datetime.fromtimestamp(ts)
                label = dt.strftime("%H:%M")
                if frame in radar_data.get('nowcast', []):
                    label += " (Forecast)"
                frame_times.append(label)
            
            frame_idx = st.select_slider(
                "Select Time",
                options=list(range(len(all_frames))),
                value=len(radar_data.get('past', [])) - 1 if radar_data.get('past') else 0,
                format_func=lambda x: frame_times[x] if x < len(frame_times) else "N/A"
            )
            selected_frame = all_frames[frame_idx]
            
            opacity_col1, opacity_col2 = st.columns([1, 3])
            with opacity_col1:
                st.caption(f"🕐 {frame_times[frame_idx]}")
            with opacity_col2:
                radar_opacity = st.slider("Radar Opacity", 0.3, 1.0, 0.7, 0.1)
    
    base_tiles = {
        "Satellite": {
            "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            "attr": "ESRI World Imagery",
            "name": "Satellite"
        },
        "Dark": {
            "tiles": "CartoDB dark_matter",
            "attr": "CartoDB",
            "name": "Dark"
        },
        "Terrain": {
            "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}",
            "attr": "ESRI Terrain",
            "name": "Terrain"
        },
        "Light": {
            "tiles": "CartoDB positron",
            "attr": "CartoDB",
            "name": "Light"
        },
        "Streets": {
            "tiles": "OpenStreetMap",
            "attr": "OpenStreetMap",
            "name": "Streets"
        }
    }
    
    tile_config = base_tiles[base_layer]
    
    if base_layer in ["Satellite", "Terrain"]:
        m = folium.Map(
            location=[25, 0],
            zoom_start=2,
            tiles=None,
            min_zoom=2,
            max_zoom=12
        )
        folium.TileLayer(
            tiles=tile_config["tiles"],
            attr=tile_config["attr"],
            name=tile_config["name"],
            overlay=False,
            control=True
        ).add_to(m)
    else:
        m = folium.Map(
            location=[25, 0],
            zoom_start=2,
            tiles=tile_config["tiles"],
            min_zoom=2,
            max_zoom=12
        )
    
    if overlay_type == "Precipitation Radar" and radar_data and selected_frame:
        frame_path = selected_frame.get('path', '')
        if frame_path:
            radar_url = f"https://tilecache.rainviewer.com{frame_path}/256/{{z}}/{{x}}/{{y}}/2/1_1.png"
            folium.TileLayer(
                tiles=radar_url,
                attr="RainViewer.com",
                name="Precipitation Radar",
                overlay=True,
                opacity=radar_opacity,
                control=True
            ).add_to(m)
    
    weather_data = get_global_weather()
    
    if show_weather_stations and weather_data:
        for city in weather_data:
            temp = city.get('temp')
            weather_code = city.get('weather_code', 0)
            icon, desc, _ = get_weather_info(weather_code)
            temp_color = get_temp_color(temp)
            wind_arrow = get_wind_direction_arrow(city.get('wind_dir', 0))
            
            popup_html = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-width: 200px; padding: 5px;">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <span style="font-size: 32px; margin-right: 10px;">{icon}</span>
                    <div>
                        <div style="font-weight: 700; font-size: 16px; color: #1e293b;">{city['name']}</div>
                        <div style="font-size: 12px; color: #64748b;">{city['country']}</div>
                    </div>
                </div>
                <div style="font-size: 13px; color: #475569;">{desc}</div>
                <hr style="margin: 10px 0; border: none; border-top: 1px solid #e2e8f0;">
                <table style="width: 100%; font-size: 13px; color: #334155;">
                    <tr>
                        <td>🌡️ Temperature</td>
                        <td style="text-align: right; font-weight: 600;">{temp}°C</td>
                    </tr>
                    <tr>
                        <td>🤒 Feels Like</td>
                        <td style="text-align: right;">{city.get('feels_like', 'N/A')}°C</td>
                    </tr>
                    <tr>
                        <td>💧 Humidity</td>
                        <td style="text-align: right;">{city.get('humidity', 'N/A')}%</td>
                    </tr>
                    <tr>
                        <td>💨 Wind</td>
                        <td style="text-align: right;">{city.get('wind_speed', 'N/A')} km/h {wind_arrow}</td>
                    </tr>
                    <tr>
                        <td>🌬️ Gusts</td>
                        <td style="text-align: right;">{city.get('wind_gusts', 'N/A')} km/h</td>
                    </tr>
                    <tr>
                        <td>☁️ Cloud Cover</td>
                        <td style="text-align: right;">{city.get('clouds', 'N/A')}%</td>
                    </tr>
                    <tr>
                        <td>🌧️ Precipitation</td>
                        <td style="text-align: right;">{city.get('precip', 0)} mm</td>
                    </tr>
                    <tr>
                        <td>📊 Pressure</td>
                        <td style="text-align: right;">{city.get('pressure', 'N/A')} hPa</td>
                    </tr>
                </table>
                <div style="margin-top: 8px; font-size: 11px; color: #94a3b8;">Updated: {city.get('time', 'N/A')}</div>
            </div>
            """
            
            if overlay_type == "Temperature":
                radius = 18
            elif overlay_type == "Wind":
                radius = 15
            else:
                radius = 10
            
            folium.CircleMarker(
                location=[city['lat'], city['lon']],
                radius=radius,
                popup=folium.Popup(popup_html, max_width=280),
                tooltip=f"{city['name']}: {temp}°C {icon}",
                color=temp_color,
                fill=True,
                fill_color=temp_color,
                fill_opacity=0.85,
                weight=2
            ).add_to(m)
            
            if overlay_type == "Temperature" and temp is not None:
                folium.Marker(
                    location=[city['lat'], city['lon']],
                    icon=folium.DivIcon(
                        icon_size=(40, 20),
                        icon_anchor=(20, 10),
                        html=f'<div style="font-size: 11px; font-weight: 700; color: white; text-shadow: 1px 1px 2px black; text-align: center;">{int(temp)}°</div>'
                    )
                ).add_to(m)
    
    if show_wind_arrows and weather_data:
        for city in weather_data:
            wind_speed = city.get('wind_speed', 0)
            wind_dir = city.get('wind_dir', 0)
            
            if wind_speed and wind_speed > 5:
                arrow = get_wind_direction_arrow(wind_dir)
                arrow_size = min(20, 10 + wind_speed / 5)
                
                folium.Marker(
                    location=[city['lat'] + 0.8, city['lon']],
                    icon=folium.DivIcon(
                        icon_size=(30, 30),
                        icon_anchor=(15, 15),
                        html=f'<div style="font-size: {arrow_size}px; color: #60a5fa; text-shadow: 1px 1px 2px black;">{arrow}</div>'
                    )
                ).add_to(m)
    
    if st.session_state.clicked_coords:
        lat, lon = st.session_state.clicked_coords
        folium.Marker(
            location=[lat, lon],
            icon=folium.Icon(color='red', icon='info-sign'),
            popup=f"Selected Location: {lat:.4f}, {lon:.4f}"
        ).add_to(m)
        
        folium.CircleMarker(
            location=[lat, lon],
            radius=20,
            color='#ef4444',
            fill=True,
            fill_color='#ef4444',
            fill_opacity=0.3,
            weight=3
        ).add_to(m)
    
    folium.LayerControl(collapsed=False).add_to(m)
    
    map_data = st_folium(
        m,
        width="100%",
        height=600,
        returned_objects=["last_clicked", "zoom", "center"]
    )
    
    if map_data and map_data.get('last_clicked'):
        clicked_lat = map_data['last_clicked']['lat']
        clicked_lon = map_data['last_clicked']['lng']
        
        if st.session_state.clicked_coords != (clicked_lat, clicked_lon):
            st.session_state.clicked_coords = (clicked_lat, clicked_lon)
            
            with st.spinner("🌍 Fetching weather data for this location..."):
                weather = get_weather_for_location(clicked_lat, clicked_lon)
                location_name, country = get_location_name(clicked_lat, clicked_lon)
                
                st.session_state.clicked_weather = weather
                st.session_state.clicked_location_name = (location_name, country)
            
            st.rerun()
    
    if st.session_state.clicked_weather and st.session_state.clicked_coords:
        weather = st.session_state.clicked_weather
        lat, lon = st.session_state.clicked_coords
        location_name, country = st.session_state.clicked_location_name or ("Unknown", "")
        
        current = weather.get('current', {})
        hourly = weather.get('hourly', {})
        daily = weather.get('daily', {})
        
        weather_code = current.get('weather_code', 0)
        icon, desc, _ = get_weather_info(weather_code)
        temp = current.get('temperature_2m')
        temp_color = get_temp_color(temp)
        
        st.markdown("---")
        st.markdown(f"### 📍 Weather for Clicked Location")
        
        header_col1, header_col2 = st.columns([3, 1])
        with header_col1:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1e3a8a, #3b82f6); padding: 1.5rem; border-radius: 16px; margin-bottom: 1rem;">
                <div style="display: flex; align-items: center;">
                    <span style="font-size: 64px; margin-right: 20px;">{icon}</span>
                    <div>
                        <h2 style="margin: 0; color: white;">{location_name}</h2>
                        <p style="margin: 5px 0; color: #bfdbfe;">{country}</p>
                        <p style="margin: 0; color: #93c5fd; font-size: 0.9rem;">📍 {lat:.4f}°, {lon:.4f}°</p>
                    </div>
                </div>
                <div style="margin-top: 15px;">
                    <span style="font-size: 48px; font-weight: 700; color: white;">{temp}°C</span>
                    <span style="font-size: 18px; color: #bfdbfe; margin-left: 10px;">{desc}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with header_col2:
            if st.button("❌ Clear Selection", use_container_width=True):
                st.session_state.clicked_weather = None
                st.session_state.clicked_coords = None
                st.session_state.clicked_location_name = None
                st.rerun()
        
        st.markdown("#### 🌡️ Current Conditions")
        cond_col1, cond_col2, cond_col3, cond_col4, cond_col5, cond_col6 = st.columns(6)
        
        with cond_col1:
            feels_like = current.get('apparent_temperature', 'N/A')
            st.metric("🤒 Feels Like", f"{feels_like}°C" if feels_like != 'N/A' else 'N/A')
        
        with cond_col2:
            humidity = current.get('relative_humidity_2m', 'N/A')
            st.metric("💧 Humidity", f"{humidity}%" if humidity != 'N/A' else 'N/A')
        
        with cond_col3:
            wind_speed = current.get('wind_speed_10m', 'N/A')
            wind_dir = current.get('wind_direction_10m', 0)
            arrow = get_wind_direction_arrow(wind_dir)
            st.metric("💨 Wind", f"{wind_speed} km/h {arrow}" if wind_speed != 'N/A' else 'N/A')
        
        with cond_col4:
            gusts = current.get('wind_gusts_10m', 'N/A')
            st.metric("🌬️ Gusts", f"{gusts} km/h" if gusts != 'N/A' else 'N/A')
        
        with cond_col5:
            clouds = current.get('cloud_cover', 'N/A')
            st.metric("☁️ Clouds", f"{clouds}%" if clouds != 'N/A' else 'N/A')
        
        with cond_col6:
            pressure = current.get('surface_pressure', 'N/A')
            st.metric("📊 Pressure", f"{pressure} hPa" if pressure != 'N/A' else 'N/A')
        
        if daily:
            st.markdown("#### 📅 3-Day Forecast")
            forecast_cols = st.columns(3)
            
            dates = daily.get('time', [])[:3]
            max_temps = daily.get('temperature_2m_max', [])[:3]
            min_temps = daily.get('temperature_2m_min', [])[:3]
            precip = daily.get('precipitation_sum', [])[:3]
            codes = daily.get('weather_code', [])[:3]
            sunrise = daily.get('sunrise', [])[:3]
            sunset = daily.get('sunset', [])[:3]
            
            for i, col in enumerate(forecast_cols):
                if i < len(dates):
                    with col:
                        day_icon, day_desc, _ = get_weather_info(codes[i] if i < len(codes) else 0)
                        day_date = datetime.strptime(dates[i], "%Y-%m-%d")
                        day_name = day_date.strftime("%A")
                        
                        sr_time = sunrise[i].split('T')[1][:5] if i < len(sunrise) and sunrise[i] else "N/A"
                        ss_time = sunset[i].split('T')[1][:5] if i < len(sunset) and sunset[i] else "N/A"
                        
                        st.markdown(f"""
                        <div style="background: rgba(255,255,255,0.05); padding: 1rem; border-radius: 12px; text-align: center; border: 1px solid rgba(255,255,255,0.1);">
                            <div style="font-weight: 600; color: #93c5fd;">{day_name}</div>
                            <div style="font-size: 12px; color: #64748b;">{dates[i]}</div>
                            <div style="font-size: 48px; margin: 10px 0;">{day_icon}</div>
                            <div style="font-size: 14px; color: #cbd5e1;">{day_desc}</div>
                            <div style="margin-top: 10px;">
                                <span style="color: #ef4444; font-weight: 600;">↑{max_temps[i] if i < len(max_temps) else 'N/A'}°</span>
                                <span style="color: #64748b;"> / </span>
                                <span style="color: #3b82f6; font-weight: 600;">↓{min_temps[i] if i < len(min_temps) else 'N/A'}°</span>
                            </div>
                            <div style="font-size: 12px; color: #94a3b8; margin-top: 8px;">
                                🌧️ {precip[i] if i < len(precip) else 0} mm
                            </div>
                            <div style="font-size: 11px; color: #64748b; margin-top: 5px;">
                                🌅 {sr_time} | 🌇 {ss_time}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
        
        if hourly:
            st.markdown("#### ⏰ Hourly Forecast (Next 12 Hours)")
            
            hours = hourly.get('time', [])[:12]
            hour_temps = hourly.get('temperature_2m', [])[:12]
            hour_precip_prob = hourly.get('precipitation_probability', [])[:12]
            hour_codes = hourly.get('weather_code', [])[:12]
            
            hourly_data = []
            for i in range(min(12, len(hours))):
                hr_icon, _, _ = get_weather_info(hour_codes[i] if i < len(hour_codes) else 0)
                hr_time = hours[i].split('T')[1][:5] if i < len(hours) else "N/A"
                hourly_data.append({
                    "Time": hr_time,
                    "": hr_icon,
                    "Temp (°C)": hour_temps[i] if i < len(hour_temps) else "N/A",
                    "Rain %": f"{hour_precip_prob[i]}%" if i < len(hour_precip_prob) and hour_precip_prob[i] is not None else "N/A"
                })
            
            if hourly_data:
                df_hourly = pd.DataFrame(hourly_data)
                st.dataframe(df_hourly, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    legend_col1, legend_col2, legend_col3 = st.columns(3)
    
    with legend_col1:
        st.markdown("""
        **🌡️ Temperature Scale**
        - 🟣 Below -20°C (Extreme Cold)
        - 🔵 -20 to -10°C (Very Cold)
        - 🩵 -10 to 0°C (Cold)
        - 🌊 0 to 10°C (Cool)
        - 🟢 10 to 20°C (Mild)
        - 🟡 20 to 30°C (Warm)
        - 🟠 30 to 40°C (Hot)
        - 🔴 Above 40°C (Extreme Heat)
        """)
    
    with legend_col2:
        st.markdown("""
        **🌧️ Radar Colors**
        - 🟦 Light precipitation
        - 🟩 Light-moderate rain
        - 🟨 Moderate rain
        - 🟧 Heavy rain
        - 🟥 Very heavy / storms
        - 🟪 Extreme / hail
        """)
    
    with legend_col3:
        st.markdown("""
        **💨 Wind Arrows**
        - ↓ North wind (blowing south)
        - ↑ South wind (blowing north)
        - ← East wind (blowing west)
        - → West wind (blowing east)
        - Arrow size = wind strength
        """)
    
    with st.expander("📊 View All Weather Station Data", expanded=False):
        if weather_data:
            df_weather = pd.DataFrame(weather_data)
            df_weather = df_weather[['name', 'country', 'temp', 'feels_like', 'humidity', 'wind_speed', 'wind_gusts', 'clouds', 'precip', 'pressure']]
            df_weather.columns = ['City', 'Country', 'Temp (°C)', 'Feels Like (°C)', 'Humidity (%)', 'Wind (km/h)', 'Gusts (km/h)', 'Clouds (%)', 'Precip (mm)', 'Pressure (hPa)']
            
            def color_temp(val):
                if pd.isna(val):
                    return ''
                try:
                    val = float(val)
                    if val < 0:
                        return 'color: #3b82f6'
                    elif val < 15:
                        return 'color: #22d3ee'
                    elif val < 25:
                        return 'color: #22c55e'
                    elif val < 35:
                        return 'color: #eab308'
                    else:
                        return 'color: #ef4444'
                except:
                    return ''
            
            styled_df = df_weather.style.applymap(color_temp, subset=['Temp (°C)', 'Feels Like (°C)']).format({
                'Temp (°C)': '{:.1f}',
                'Feels Like (°C)': '{:.1f}',
                'Wind (km/h)': '{:.1f}',
                'Gusts (km/h)': '{:.1f}',
                'Precip (mm)': '{:.1f}',
                'Pressure (hPa)': '{:.0f}'
            }, na_rep='N/A')
            
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    if weather_data:
        st.markdown("### 🌍 Global Weather Summary")
        stat_col1, stat_col2, stat_col3, stat_col4, stat_col5 = st.columns(5)
        
        temps = [c['temp'] for c in weather_data if c.get('temp') is not None]
        winds = [c['wind_speed'] for c in weather_data if c.get('wind_speed') is not None]
        
        with stat_col1:
            if temps:
                hottest = max(weather_data, key=lambda x: x.get('temp', -999) if x.get('temp') else -999)
                st.metric("🔥 Hottest", f"{hottest['temp']}°C", hottest['name'])
        
        with stat_col2:
            if temps:
                coldest = min(weather_data, key=lambda x: x.get('temp', 999) if x.get('temp') else 999)
                st.metric("❄️ Coldest", f"{coldest['temp']}°C", coldest['name'])
        
        with stat_col3:
            if winds:
                windiest = max(weather_data, key=lambda x: x.get('wind_speed', 0) if x.get('wind_speed') else 0)
                st.metric("💨 Windiest", f"{windiest['wind_speed']} km/h", windiest['name'])
        
        with stat_col4:
            if temps:
                avg_temp = sum(temps) / len(temps)
                st.metric("🌡️ Global Avg", f"{avg_temp:.1f}°C", f"{len(temps)} cities")
        
        with stat_col5:
            rainy_cities = len([c for c in weather_data if c.get('precip', 0) and c.get('precip', 0) > 0])
            st.metric("🌧️ Raining In", f"{rainy_cities} cities", f"of {len(weather_data)}")
    
    st.caption("📡 Data Sources: ESRI World Imagery • RainViewer Radar API • Open-Meteo Weather API • OpenStreetMap Nominatim • Click anywhere for instant weather!")


# ====================== WORLD NEWS ACTIVITY MAP TAB (PERFECTLY IMPROVED) # # ====================== WORLD NEWS ACTIVITY MAP TAB ======================
with tab_map:
    st.markdown("""
    <style>
        .folium-map {
            width: 100% !important;
            height: 600px !important;
            max-height: 600px !important;
            border-radius: 16px !important;
            overflow: hidden !important;
        }
        iframe[title="streamlit_folium.st_folium"] {
            border-radius: 16px !important;
            overflow: hidden !important;
        }
        .stFolium {
            border-radius: 16px !important;
            overflow: hidden !important;
            box-shadow: 0 25px 50px -12px rgba(59, 130, 246, 0.3) !important;
        }
        .leaflet-container {
            overflow: hidden !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.title("🌍 Real-Time World News Activity Map")
    st.caption("Live global monitoring of conflicts, disasters, protests, political events & unusual activity worldwide • Color-coded by event type • Click any signal for details")
    
    GLOBAL_LOCATIONS = {
        "USA": [37.0902, -95.7129], "United States": [37.0902, -95.7129],
        "Washington": [38.9072, -77.0369], "Washington DC": [38.9072, -77.0369],
        "New York": [40.7128, -74.0060], "NYC": [40.7128, -74.0060],
        "Los Angeles": [34.0522, -118.2437], "LA": [34.0522, -118.2437],
        "Chicago": [41.8781, -87.6298],
        "Houston": [29.7604, -95.3698],
        "Phoenix": [33.4484, -112.0740],
        "Philadelphia": [39.9526, -75.1652],
        "San Antonio": [29.4241, -98.4936],
        "San Diego": [32.7157, -117.1611],
        "Dallas": [32.7767, -96.7970],
        "San Francisco": [37.7749, -122.4194],
        "Austin": [30.2672, -97.7431],
        "Seattle": [47.6062, -122.3321],
        "Denver": [39.7392, -104.9903],
        "Boston": [42.3601, -71.0589],
        "Miami": [25.7617, -80.1918],
        "Atlanta": [33.7490, -84.3880],
        "Detroit": [42.3314, -83.0458],
        "Minneapolis": [44.9778, -93.2650],
        "Las Vegas": [36.1699, -115.1398],
        "Portland": [45.5152, -122.6784],
        "Canada": [56.1304, -106.3468],
        "Toronto": [43.6532, -79.3832],
        "Vancouver": [49.2827, -123.1207],
        "Montreal": [45.5017, -73.5673],
        "Ottawa": [45.4215, -75.6972],
        "Mexico": [23.6345, -102.5528],
        "Mexico City": [19.4326, -99.1332],
        "Brazil": [-14.2350, -51.9253],
        "São Paulo": [-23.5505, -46.6333], "Sao Paulo": [-23.5505, -46.6333],
        "Rio de Janeiro": [-22.9068, -43.1729],
        "Argentina": [-38.4161, -63.6167],
        "Buenos Aires": [-34.6037, -58.3816],
        "Chile": [-35.6751, -71.5430],
        "Santiago": [-33.4489, -70.6693],
        "Colombia": [4.5709, -74.2973],
        "Bogota": [4.7110, -74.0721],
        "Peru": [-9.1900, -75.0152],
        "Lima": [-12.0464, -77.0428],
        "Venezuela": [6.4238, -66.5897],
        "Caracas": [10.4806, -66.9036],
        "UK": [55.3781, -3.4360], "Britain": [55.3781, -3.4360], "United Kingdom": [55.3781, -3.4360],
        "London": [51.5074, -0.1278],
        "Manchester": [53.4808, -2.2426],
        "Birmingham": [52.4862, -1.8904],
        "France": [46.2276, 2.2137],
        "Paris": [48.8566, 2.3522],
        "Germany": [51.1657, 10.4515],
        "Berlin": [52.5200, 13.4050],
        "Munich": [48.1351, 11.5820],
        "Frankfurt": [50.1109, 8.6821],
        "Italy": [41.8719, 12.5674],
        "Rome": [41.9028, 12.4964],
        "Milan": [45.4642, 9.1900],
        "Spain": [40.4637, -3.7492],
        "Madrid": [40.4168, -3.7038],
        "Barcelona": [41.3851, 2.1734],
        "Portugal": [39.3999, -8.2245],
        "Lisbon": [38.7223, -9.1393],
        "Netherlands": [52.1326, 5.2913],
        "Amsterdam": [52.3676, 4.9041],
        "Belgium": [50.5039, 4.4699],
        "Brussels": [50.8503, 4.3517],
        "Switzerland": [46.8182, 8.2275],
        "Zurich": [47.3769, 8.5417],
        "Geneva": [46.2044, 6.1432],
        "Austria": [47.5162, 14.5501],
        "Vienna": [48.2082, 16.3738],
        "Poland": [51.9194, 19.1451],
        "Warsaw": [52.2297, 21.0122],
        "Czech Republic": [49.8175, 15.4730],
        "Prague": [50.0755, 14.4378],
        "Hungary": [47.1625, 19.5033],
        "Budapest": [47.4979, 19.0402],
        "Romania": [45.9432, 24.9668],
        "Bucharest": [44.4268, 26.1025],
        "Bulgaria": [42.7339, 25.4858],
        "Sofia": [42.6977, 23.3219],
        "Greece": [39.0742, 21.8243],
        "Athens": [37.9838, 23.7275],
        "Turkey": [38.9637, 35.2433],
        "Istanbul": [41.0082, 28.9784],
        "Ankara": [39.9334, 32.8597],
        "Sweden": [60.1282, 18.6435],
        "Stockholm": [59.3293, 18.0686],
        "Norway": [60.4720, 8.4689],
        "Oslo": [59.9139, 10.7522],
        "Denmark": [56.2639, 9.5018],
        "Copenhagen": [55.6761, 12.5683],
        "Finland": [61.9241, 25.7482],
        "Helsinki": [60.1699, 24.9384],
        "Iceland": [64.9631, -19.0208],
        "Reykjavik": [64.1466, -21.9426],
        "Ireland": [53.1424, -7.6921],
        "Dublin": [53.3498, -6.2603],
        "Serbia": [44.0165, 21.0059],
        "Belgrade": [44.7866, 20.4489],
        "Croatia": [45.1000, 15.2000],
        "Zagreb": [45.8150, 15.9819],
        "Bosnia": [43.9159, 17.6791],
        "Sarajevo": [43.8563, 18.4131],
        "Kosovo": [42.6026, 20.9030],
        "Pristina": [42.6629, 21.1655],
        "Albania": [41.1533, 20.1683],
        "Tirana": [41.3275, 19.8187],
        "Moldova": [47.4116, 28.3699],
        "Chisinau": [47.0105, 28.8638],
        "Lithuania": [55.1694, 23.8813],
        "Vilnius": [54.6872, 25.2797],
        "Latvia": [56.8796, 24.6032],
        "Riga": [56.9496, 24.1052],
        "Estonia": [58.5953, 25.0136],
        "Tallinn": [59.4370, 24.7536],
        "Belarus": [53.7098, 27.9534],
        "Minsk": [53.9006, 27.5590],
        "Russia": [61.5240, 105.3188],
        "Moscow": [55.7558, 37.6173],
        "St. Petersburg": [59.9311, 30.3609],
        "Novosibirsk": [55.0084, 82.9357],
        "Vladivostok": [43.1332, 131.9113],
        "Crimea": [44.9521, 34.1024],
        "Sevastopol": [44.6166, 33.5254],
        "Ukraine": [48.3794, 31.1656],
        "Kyiv": [50.4501, 30.5234], "Kiev": [50.4501, 30.5234],
        "Kharkiv": [49.9935, 36.2304],
        "Odesa": [46.4825, 30.7233], "Odessa": [46.4825, 30.7233],
        "Dnipro": [48.4647, 35.0462],
        "Donetsk": [48.0159, 37.8029],
        "Luhansk": [48.5740, 39.3078],
        "Zaporizhzhia": [47.8388, 35.1396],
        "Lviv": [49.8397, 24.0297],
        "Mariupol": [47.0958, 37.5433],
        "Kherson": [46.6354, 32.6169],
        "Bakhmut": [48.5953, 38.0003],
        "Georgia": [42.3154, 43.3569],
        "Tbilisi": [41.7151, 44.8271],
        "Armenia": [40.0691, 45.0382],
        "Yerevan": [40.1792, 44.4991],
        "Azerbaijan": [40.1431, 47.5769],
        "Baku": [40.4093, 49.8671],
        "Kazakhstan": [48.0196, 66.9237],
        "Astana": [51.1801, 71.4460],
        "Almaty": [43.2220, 76.8512],
        "Uzbekistan": [41.3775, 64.5853],
        "Tashkent": [41.2995, 69.2401],
        "Israel": [31.0461, 34.8516],
        "Tel Aviv": [32.0853, 34.7818],
        "Jerusalem": [31.7683, 35.2137],
        "Gaza": [31.3547, 34.3088], "Gaza Strip": [31.3547, 34.3088],
        "Palestine": [31.9522, 35.2332], "West Bank": [31.9464, 35.3026],
        "Rafah": [31.2893, 34.2504],
        "Lebanon": [33.8547, 35.8623],
        "Beirut": [33.8938, 35.5018],
        "Syria": [34.8021, 38.9968],
        "Damascus": [33.5138, 36.2765],
        "Aleppo": [36.2021, 37.1343],
        "Idlib": [35.9306, 36.6339],
        "Jordan": [30.5852, 36.2384],
        "Amman": [31.9454, 35.9284],
        "Iraq": [33.2232, 43.6793],
        "Baghdad": [33.3152, 44.3661],
        "Mosul": [36.3350, 43.1189],
        "Erbil": [36.1912, 44.0094],
        "Iran": [32.4279, 53.6880],
        "Tehran": [35.6892, 51.3890],
        "Isfahan": [32.6546, 51.6680],
        "Saudi Arabia": [23.8859, 45.0792],
        "Riyadh": [24.7136, 46.6753],
        "Jeddah": [21.4858, 39.1925],
        "Mecca": [21.3891, 39.8579],
        "UAE": [23.4241, 53.8478],
        "Dubai": [25.2048, 55.2708],
        "Abu Dhabi": [24.4539, 54.3773],
        "Qatar": [25.3548, 51.1839],
        "Doha": [25.2854, 51.5310],
        "Kuwait": [29.3117, 47.4818],
        "Bahrain": [26.0667, 50.5577],
        "Oman": [21.4735, 55.9754],
        "Muscat": [23.5880, 58.3829],
        "Yemen": [15.5527, 48.5164],
        "Sanaa": [15.3694, 44.1910],
        "Aden": [12.7797, 45.0095],
        "Egypt": [26.8206, 30.8025],
        "Cairo": [30.0444, 31.2357],
        "Alexandria": [31.2156, 29.9553],
        "Libya": [26.3351, 17.2283],
        "Tripoli": [32.8872, 13.1913],
        "Tunisia": [33.8869, 9.5375],
        "Tunis": [36.8065, 10.1815],
        "Algeria": [28.0339, 1.6596],
        "Algiers": [36.7372, 3.0868],
        "Morocco": [31.7917, -7.0926],
        "Rabat": [34.0209, -6.8416],
        "Casablanca": [33.5731, -7.5898],
        "Sudan": [12.8628, 30.2176],
        "Khartoum": [15.5007, 32.5599],
        "South Sudan": [6.8770, 31.3070],
        "Juba": [4.8594, 31.5713],
        "Ethiopia": [9.1450, 40.4897],
        "Addis Ababa": [9.0300, 38.7400],
        "Somalia": [5.1521, 46.1996],
        "Mogadishu": [2.0469, 45.3182],
        "Kenya": [-0.0236, 37.9062],
        "Nairobi": [-1.2921, 36.8219],
        "Uganda": [1.3733, 32.2903],
        "Kampala": [0.3476, 32.5825],
        "Tanzania": [-6.3690, 34.8888],
        "Dar es Salaam": [-6.7924, 39.2083],
        "Rwanda": [-1.9403, 29.8739],
        "Kigali": [-1.9706, 30.1044],
        "Democratic Republic of Congo": [-4.0383, 21.7587], "DRC": [-4.0383, 21.7587], "Congo": [-4.0383, 21.7587],
        "Kinshasa": [-4.4419, 15.2663],
        "Nigeria": [9.0820, 8.6753],
        "Lagos": [6.5244, 3.3792],
        "Abuja": [9.0765, 7.3986],
        "Ghana": [7.9465, -1.0232],
        "Accra": [5.6037, -0.1870],
        "Senegal": [14.4974, -14.4524],
        "Dakar": [14.6928, -17.4467],
        "Mali": [17.5707, -3.9962],
        "Bamako": [12.6392, -8.0029],
        "South Africa": [-30.5595, 22.9375],
        "Johannesburg": [-26.2041, 28.0473],
        "Cape Town": [-33.9249, 18.4241],
        "Pretoria": [-25.7479, 28.2293],
        "Zimbabwe": [-19.0154, 29.1549],
        "Harare": [-17.8252, 31.0335],
        "China": [35.8617, 104.1954],
        "Beijing": [39.9042, 116.4074],
        "Shanghai": [31.2304, 121.4737],
        "Guangzhou": [23.1291, 113.2644],
        "Shenzhen": [22.5431, 114.0579],
        "Wuhan": [30.5928, 114.3055],
        "Hong Kong": [22.3193, 114.1694],
        "Taiwan": [23.6978, 120.9605],
        "Taipei": [25.0330, 121.5654],
        "Tibet": [29.6500, 91.1000],
        "Lhasa": [29.6500, 91.1000],
        "Xinjiang": [41.1129, 85.2401],
        "Japan": [36.2048, 138.2529],
        "Tokyo": [35.6762, 139.6503],
        "Osaka": [34.6937, 135.5023],
        "South Korea": [35.9078, 127.7669], "Korea": [35.9078, 127.7669],
        "Seoul": [37.5665, 126.9780],
        "North Korea": [40.3399, 127.5101], "DPRK": [40.3399, 127.5101],
        "Pyongyang": [39.0392, 125.7625],
        "India": [20.5937, 78.9629],
        "Delhi": [28.6139, 77.2090], "New Delhi": [28.6139, 77.2090],
        "Mumbai": [19.0760, 72.8777],
        "Bangalore": [12.9716, 77.5946],
        "Chennai": [13.0827, 80.2707],
        "Kolkata": [22.5726, 88.3639],
        "Hyderabad": [17.3850, 78.4867],
        "Kashmir": [33.7782, 76.5762],
        "Pakistan": [30.3753, 69.3451],
        "Islamabad": [33.6844, 73.0479],
        "Karachi": [24.8607, 67.0011],
        "Lahore": [31.5204, 74.3587],
        "Bangladesh": [23.6850, 90.3563],
        "Dhaka": [23.8103, 90.4125],
        "Sri Lanka": [7.8731, 80.7718],
        "Colombo": [6.9271, 79.8612],
        "Nepal": [28.3949, 84.1240],
        "Kathmandu": [27.7172, 85.3240],
        "Afghanistan": [33.9391, 67.7097],
        "Kabul": [34.5553, 69.2075],
        "Kandahar": [31.6289, 65.7372],
        "Myanmar": [21.9162, 95.9560], "Burma": [21.9162, 95.9560],
        "Yangon": [16.8661, 96.1951],
        "Thailand": [15.8700, 100.9925],
        "Bangkok": [13.7563, 100.5018],
        "Vietnam": [14.0583, 108.2772],
        "Hanoi": [21.0285, 105.8542],
        "Ho Chi Minh City": [10.8231, 106.6297],
        "Cambodia": [12.5657, 104.9910],
        "Phnom Penh": [11.5564, 104.9282],
        "Malaysia": [4.2105, 101.9758],
        "Kuala Lumpur": [3.1390, 101.6869],
        "Singapore": [1.3521, 103.8198],
        "Indonesia": [-0.7893, 113.9213],
        "Jakarta": [-6.2088, 106.8456],
        "Bali": [-8.3405, 115.0920],
        "Philippines": [12.8797, 121.7740],
        "Manila": [14.5995, 120.9842],
        "Australia": [-25.2744, 133.7751],
        "Sydney": [-33.8688, 151.2093],
        "Melbourne": [-37.8136, 144.9631],
        "Brisbane": [-27.4705, 153.0260],
        "Perth": [-31.9505, 115.8605],
        "Canberra": [-35.2809, 149.1300],
        "New Zealand": [-40.9006, 174.8860],
        "Auckland": [-36.8509, 174.7645],
        "Wellington": [-41.2866, 174.7756],
        "South China Sea": [12.0000, 114.0000],
        "Taiwan Strait": [24.0000, 119.0000],
        "Red Sea": [20.0000, 38.0000],
        "Persian Gulf": [26.0000, 52.0000],
        "Strait of Hormuz": [26.5000, 56.5000],
        "Suez Canal": [30.4550, 32.3500],
        "Black Sea": [43.0000, 34.0000],
        "Mediterranean": [35.0000, 18.0000],
        "Baltic Sea": [58.0000, 20.0000],
        "Arctic Ocean": [85.0000, 0.0000],
        "Golan Heights": [33.0000, 35.8000],
        "DMZ": [38.0000, 127.0000],
        "Donbas": [48.0000, 38.0000],
        "Sahel": [15.0000, 0.0000],
        "Horn of Africa": [8.0000, 46.0000],
        "Europe": [54.5260, 15.2551],
        "Middle East": [25.0000, 45.0000],
        "Africa": [8.7832, 34.5085],
        "Asia": [34.0479, 100.6197],
        "North America": [45.0000, -100.0000],
        "South America": [-15.0000, -60.0000],
        "Oceania": [-15.0000, 140.0000],
    }
    
    EVENT_CATEGORIES = {
        "⚔️ Conflict/War": {
            "keywords": ["war", "military", "attack", "strike", "bomb", "missile", "troops", "army", "soldier", "combat", "battle", "offensive", "invasion", "airstrike", "drone", "artillery", "shelling", "fighting", "hostilities", "ceasefire", "warfare", "armed", "weapons", "killed", "deaths", "casualties", "wounded", "frontline", "siege", "occupation", "raid", "ambush", "clashes"],
            "color": "#ef4444",
            "priority": 1
        },
        "💥 Terrorism": {
            "keywords": ["terrorist", "terrorism", "terror", "isis", "al-qaeda", "extremist", "militant", "jihadist", "suicide bomber", "car bomb", "ied", "hostage", "kidnapping", "beheading", "radical", "insurgent", "guerrilla"],
            "color": "#dc2626",
            "priority": 1
        },
        "🔥 Disaster/Emergency": {
            "keywords": ["earthquake", "tsunami", "flood", "flooding", "hurricane", "typhoon", "cyclone", "tornado", "wildfire", "fire", "volcano", "eruption", "landslide", "avalanche", "drought", "famine", "disaster", "emergency", "evacuate", "rescue", "survivors", "devastation", "destruction", "catastrophe", "collapse", "explosion"],
            "color": "#f97316",
            "priority": 1
        },
        "✊ Protest/Unrest": {
            "keywords": ["protest", "demonstration", "rally", "march", "riot", "unrest", "uprising", "revolution", "dissent", "activists", "strike", "walkout", "occupy", "civil disobedience", "tear gas", "water cannon", "crackdown", "arrests", "detained", "opposition", "resistance", "movement"],
            "color": "#eab308",
            "priority": 2
        },
        "🏛️ Political Crisis": {
            "keywords": ["coup", "overthrow", "impeachment", "resign", "election fraud", "disputed", "constitutional crisis", "martial law", "state of emergency", "sanctions", "diplomatic", "summit", "treaty", "negotiations", "talks", "agreement", "alliance", "tensions", "standoff"],
            "color": "#8b5cf6",
            "priority": 2
        },
        "💰 Economic Crisis": {
            "keywords": ["economic crisis", "recession", "inflation", "currency crash", "debt default", "bankruptcy", "stock crash", "market crash", "financial crisis", "bank collapse", "unemployment", "poverty", "shortage", "supply chain"],
            "color": "#6366f1",
            "priority": 3
        },
        "🦠 Health Emergency": {
            "keywords": ["pandemic", "epidemic", "outbreak", "virus", "disease", "covid", "ebola", "cholera", "malaria", "infection", "quarantine", "lockdown", "vaccine", "health emergency", "who", "hospital", "deaths", "cases"],
            "color": "#22c55e",
            "priority": 2
        },
        "🚨 Crime/Security": {
            "keywords": ["shooting", "murder", "assassination", "crime", "criminal", "gang", "cartel", "drug", "trafficking", "smuggling", "corruption", "fraud", "hacking", "cyber attack", "breach", "espionage", "spy", "intelligence"],
            "color": "#f43f5e",
            "priority": 2
        },
        "📰 Breaking News": {
            "keywords": ["breaking", "urgent", "alert", "just in", "developing", "update", "live", "happening now", "latest"],
            "color": "#a855f7",
            "priority": 2
        }
    }
    
    def detect_locations_and_events(text):
        text_lower = text.lower()
        results = []
        
        for location, coords in GLOBAL_LOCATIONS.items():
            if location.lower() in text_lower:
                event_type = "📌 General News"
                event_color = "#94a3b8"
                priority = 5
                
                for category, data in EVENT_CATEGORIES.items():
                    for keyword in data["keywords"]:
                        if keyword.lower() in text_lower:
                            if data["priority"] < priority:
                                event_type = category
                                event_color = data["color"]
                                priority = data["priority"]
                            break
                
                results.append({
                    "location": location,
                    "coords": coords,
                    "event_type": event_type,
                    "color": event_color,
                    "priority": priority
                })
        
        return results
    
    st.markdown("---")
    ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns(4)
    
    with ctrl_col1:
        map_style = st.selectbox("🗺️ Map Style", ["Dark", "Satellite", "Light", "Terrain"], index=0, key="activity_map_style")
    
    with ctrl_col2:
        show_all_categories = st.checkbox("Show All Categories", value=True, key="show_all_cat")
    
    with ctrl_col3:
        if not show_all_categories:
            selected_categories = st.multiselect(
                "Filter by Event Type",
                options=list(EVENT_CATEGORIES.keys()),
                default=list(EVENT_CATEGORIES.keys())[:3],
                key="selected_cat"
            )
        else:
            selected_categories = list(EVENT_CATEGORIES.keys())
    
    with ctrl_col4:
        if st.button("🔄 Refresh Map", use_container_width=True, type="primary", key="refresh_activity_map"):
            st.cache_data.clear()
            st.rerun()
    
    if "all_news" in st.session_state and st.session_state.all_news:
        location_signals = {}
        
        for article in st.session_state.all_news:
            title = article.get("title", "")
            desc = article.get("description", "") or ""
            source = article.get("source_name", "News")
            full_text = f"{title} {desc}"
            
            detections = detect_locations_and_events(full_text)
            
            for detection in detections:
                key = (detection["coords"][0], detection["coords"][1])
                
                if key not in location_signals:
                    location_signals[key] = {
                        "lat": detection["coords"][0],
                        "lon": detection["coords"][1],
                        "location": detection["location"],
                        "events": [],
                        "headlines": [],
                        "sources": set(),
                        "priority": 5,
                        "color": "#94a3b8",
                        "event_type": "📌 General News"
                    }
                
                location_signals[key]["headlines"].append(title[:150])
                location_signals[key]["sources"].add(source)
                location_signals[key]["events"].append(detection["event_type"])
                
                if detection["priority"] < location_signals[key]["priority"]:
                    location_signals[key]["priority"] = detection["priority"]
                    location_signals[key]["color"] = detection["color"]
                    location_signals[key]["event_type"] = detection["event_type"]
        
        if not show_all_categories:
            location_signals = {
                k: v for k, v in location_signals.items()
                if v["event_type"] in selected_categories or v["event_type"] == "📌 General News"
            }
        
        if location_signals:
            map_tiles = {
                "Dark": "CartoDB dark_matter",
                "Satellite": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                "Light": "CartoDB positron",
                "Terrain": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}"
            }
            
            world_bounds = [[-85, -180], [85, 180]]
            
            if map_style in ["Satellite", "Terrain"]:
                m = folium.Map(
                    location=[20, 0],
                    zoom_start=2,
                    tiles=None,
                    min_zoom=2,
                    max_zoom=10,
                    max_bounds=True,
                    no_wrap=True,
                    world_copy_jump=False
                )
                folium.TileLayer(
                    tiles=map_tiles[map_style],
                    attr="ESRI",
                    name=map_style,
                    overlay=False,
                    control=True,
                    no_wrap=True
                ).add_to(m)
            else:
                m = folium.Map(
                    location=[20, 0],
                    zoom_start=2,
                    tiles=map_tiles[map_style],
                    min_zoom=2,
                    max_zoom=10,
                    max_bounds=True,
                    no_wrap=True,
                    world_copy_jump=False
                )
            
            m.fit_bounds(world_bounds)
            
            sorted_signals = sorted(location_signals.values(), key=lambda x: x["priority"])
            
            for signal in sorted_signals:
                num_events = len(signal["headlines"])
                radius = min(25, max(8, 6 + num_events * 2))
                
                events_html = "".join([f"<span style='background:{EVENT_CATEGORIES.get(e, {}).get('color', '#94a3b8')}; color:white; padding:2px 6px; border-radius:4px; margin:2px; font-size:10px; display:inline-block;'>{e}</span>" for e in set(signal["events"])])
                
                headlines_html = "".join([f"<li style='margin:5px 0; font-size:12px;'>{h[:100]}{'...' if len(h) > 100 else ''}</li>" for h in signal["headlines"][:5]])
                
                popup_html = f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-width: 280px; max-width: 350px; padding: 10px;">
                    <h3 style="margin:0 0 10px 0; color: {signal['color']}; border-bottom: 2px solid {signal['color']}; padding-bottom: 8px;">
                        📍 {signal['location']}
                    </h3>
                    <div style="margin-bottom: 10px;">
                        {events_html}
                    </div>
                    <div style="font-size: 11px; color: #64748b; margin-bottom: 8px;">
                        📊 {num_events} related stories • Sources: {', '.join(list(signal['sources'])[:3])}
                    </div>
                    <hr style="margin: 10px 0; border: none; border-top: 1px solid #e2e8f0;">
                    <div style="font-weight: 600; margin-bottom: 5px; color: #334155;">Latest Headlines:</div>
                    <ul style="margin: 0; padding-left: 15px; color: #475569;">
                        {headlines_html}
                    </ul>
                    {f"<div style='font-size:11px; color:#94a3b8; margin-top:8px;'>+ {num_events - 5} more stories</div>" if num_events > 5 else ""}
                </div>
                """
                
                if signal["priority"] <= 2:
                    folium.CircleMarker(
                        location=[signal["lat"], signal["lon"]],
                        radius=radius + 8,
                        color=signal["color"],
                        fill=True,
                        fill_color=signal["color"],
                        fill_opacity=0.2,
                        weight=1,
                        opacity=0.5
                    ).add_to(m)
                
                folium.CircleMarker(
                    location=[signal["lat"], signal["lon"]],
                    radius=radius,
                    popup=folium.Popup(popup_html, max_width=380),
                    tooltip=f"{signal['event_type']} • {signal['location']} ({num_events} stories)",
                    color=signal["color"],
                    fill=True,
                    fill_color=signal["color"],
                    fill_opacity=0.85,
                    weight=3
                ).add_to(m)
            
            st_folium(m, width="100%", height=550, returned_objects=[])
            
            st.markdown("### 🎯 Event Type Legend")
            
            legend_cols = st.columns(4)
            categories_list = list(EVENT_CATEGORIES.items())
            
            for i, (category, data) in enumerate(categories_list):
                with legend_cols[i % 4]:
                    count = len([s for s in location_signals.values() if category in s["events"]])
                    st.markdown(f"""
                    <div style="display: flex; align-items: center; margin: 5px 0;">
                        <div style="width: 16px; height: 16px; border-radius: 50%; background: {data['color']}; margin-right: 8px; box-shadow: 0 0 8px {data['color']};"></div>
                        <span style="font-size: 13px;">{category} ({count})</span>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("### 📊 Global Activity Summary")
            
            stat_col1, stat_col2, stat_col3, stat_col4, stat_col5 = st.columns(5)
            
            with stat_col1:
                total_signals = len(location_signals)
                st.metric("🌍 Active Locations", total_signals)
            
            with stat_col2:
                conflict_count = len([s for s in location_signals.values() if "⚔️ Conflict/War" in s["events"] or "💥 Terrorism" in s["events"]])
                st.metric("⚔️ Conflict Zones", conflict_count)
            
            with stat_col3:
                disaster_count = len([s for s in location_signals.values() if "🔥 Disaster/Emergency" in s["events"]])
                st.metric("🔥 Disasters", disaster_count)
            
            with stat_col4:
                protest_count = len([s for s in location_signals.values() if "✊ Protest/Unrest" in s["events"]])
                st.metric("✊ Protests", protest_count)
            
            with stat_col5:
                critical_count = len([s for s in location_signals.values() if s["priority"] <= 2])
                st.metric("🚨 Critical Events", critical_count)
            
            with st.expander("📋 View All Active Hotspots", expanded=False):
                hotspot_data = []
                for signal in sorted_signals[:50]:
                    hotspot_data.append({
                        "Location": signal["location"],
                        "Event Type": signal["event_type"],
                        "Stories": len(signal["headlines"]),
                        "Sources": ", ".join(list(signal["sources"])[:3]),
                        "Top Headline": signal["headlines"][0][:80] + "..." if signal["headlines"] else "N/A"
                    })
                
                if hotspot_data:
                    df_hotspots = pd.DataFrame(hotspot_data)
                    st.dataframe(df_hotspots, use_container_width=True, hide_index=True)
            
            st.caption(f"📡 Monitoring {len(location_signals)} active locations worldwide • {sum(len(s['headlines']) for s in location_signals.values())} total news signals • Updates with every news refresh")
        
        else:
            st.info("No location-specific events detected. Refresh news to see more signals.")
    else:
        st.info("⏳ Waiting for news data... Go to 'News Archive' tab and let it load, then return here to see the activity map.")

# ====================== REAL ECONOMIST FORECASTS TAB ======================
# ====================== REAL WORLD PREDICTIONS TAB ======================
with tab_predictions:
    st.title("🔮 Top 10 World Predictions for 2025-2026")
    st.caption("Real predictions from the world's most respected leaders, billionaires, scientists & analysts • From interviews, news, books & speeches • Spanning AI, Economy, Geopolitics, Climate, Space & more")
    
    # Category filter
    pred_col1, pred_col2 = st.columns([3, 1])
    with pred_col2:
        category_filter = st.selectbox(
            "Filter by Category",
            ["🌐 All Categories", "🤖 AI & Technology", "💰 Economy & Finance", "🌍 Geopolitics", "🌡️ Climate & Energy", "🚀 Space & Science", "🏥 Health & Medicine"],
            index=0
        )
    
    real_predictions = [
        {
            "rank": 1,
            "person": "Elon Musk",
            "title": "CEO of Tesla, SpaceX, xAI",
            "image": "🚀",
            "category": "🤖 AI & Technology",
            "prediction": "AGI (Artificial General Intelligence) will arrive by end of 2025 or 2026",
            "detail": "In multiple interviews and X posts (2024-2025), Musk stated that AI smarter than any single human will exist by late 2025, and smarter than all humans combined by 2028. He predicts 1 billion humanoid robots by 2040.",
            "source": "X/Twitter posts, Lex Fridman Podcast, Tesla Shareholder Meetings",
            "timeframe": "2025-2026"
        },
        {
            "rank": 2,
            "person": "Sam Altman",
            "title": "CEO of OpenAI",
            "image": "🧠",
            "category": "🤖 AI & Technology",
            "prediction": "AI agents will join the workforce in 2025, fundamentally changing how work gets done",
            "detail": "Altman predicts 2025 will see AI agents that can independently complete complex tasks, manage projects, and work alongside humans. He expects GPT-5 to show 'significant' leaps in reasoning.",
            "source": "OpenAI DevDay 2024, Reddit AMA, WEF Davos 2025",
            "timeframe": "2025"
        },
        {
            "rank": 3,
            "person": "Jamie Dimon",
            "title": "CEO of JPMorgan Chase",
            "image": "🏦",
            "category": "💰 Economy & Finance",
            "prediction": "Global economy faces 'most dangerous time in decades' with possible recession in 2025-2026",
            "detail": "Dimon warned of geopolitical tensions, persistent inflation, and unsustainable government debt levels. He sees AI as both a massive opportunity and potential job disruptor affecting 50%+ of banking roles.",
            "source": "JPMorgan Annual Letter 2024, CNBC Interview, Bloomberg",
            "timeframe": "2025-2026"
        },
        {
            "rank": 4,
            "person": "Ray Dalio",
            "title": "Founder of Bridgewater Associates",
            "image": "📊",
            "category": "💰 Economy & Finance",
            "prediction": "The world is in a 'great powers conflict' - US-China tensions will escalate significantly by 2026",
            "detail": "Dalio predicts increasing probability of major conflict (economic or military) over Taiwan, with 2025-2026 being critical years. He also warns of a 'debt crisis' in developed nations.",
            "source": "Book: 'Principles for Dealing with the Changing World Order', LinkedIn, Bloomberg",
            "timeframe": "2025-2027"
        },
        {
            "rank": 5,
            "person": "Jensen Huang",
            "title": "CEO of NVIDIA",
            "image": "💻",
            "category": "🤖 AI & Technology",
            "prediction": "Physical AI and humanoid robots will be the next major wave starting 2025",
            "detail": "Huang predicts robots that understand and interact with the physical world will become commercially viable. He sees AI computing demand growing 100x over the next decade.",
            "source": "NVIDIA GTC 2024, CES 2025, Earnings Calls",
            "timeframe": "2025-2030"
        },
        {
            "rank": 6,
            "person": "Bill Gates",
            "title": "Co-founder of Microsoft, Philanthropist",
            "image": "💡",
            "category": "🏥 Health & Medicine",
            "prediction": "AI will revolutionize healthcare - diagnosing diseases faster than doctors by 2025-2026",
            "detail": "Gates predicts AI will dramatically improve healthcare in developing nations, making quality diagnosis accessible globally. He also expects major breakthroughs in Alzheimer's treatment.",
            "source": "GatesNotes Blog 2024, Netflix Documentary, TED Talks",
            "timeframe": "2025-2026"
        },
        {
            "rank": 7,
            "person": "Christine Lagarde",
            "title": "President of European Central Bank",
            "image": "🇪🇺",
            "category": "💰 Economy & Finance",
            "prediction": "Eurozone inflation will stabilize at 2% target by mid-2025, but growth remains fragile",
            "detail": "Lagarde expects gradual rate cuts through 2025 but warns of geopolitical shocks that could derail recovery. She sees digital euro launching pilot phase by 2025.",
            "source": "ECB Press Conferences 2024, IMF Annual Meeting, Reuters",
            "timeframe": "2025"
        },
        {
            "rank": 8,
            "person": "Dr. Fatih Birol",
            "title": "Executive Director, International Energy Agency (IEA)",
            "image": "⚡",
            "category": "🌡️ Climate & Energy",
            "prediction": "Global oil demand will peak before 2030, possibly as early as 2025-2026",
            "detail": "The IEA predicts electric vehicle adoption, solar/wind expansion, and efficiency gains will cause oil demand to plateau. Coal demand may have already peaked globally.",
            "source": "IEA World Energy Outlook 2024, COP29, Financial Times",
            "timeframe": "2025-2030"
        },
        {
            "rank": 9,
            "person": "Cathie Wood",
            "title": "CEO of ARK Invest",
            "image": "📈",
            "category": "💰 Economy & Finance",
            "prediction": "Bitcoin will reach $1 million by 2030, with significant gains in 2025-2026",
            "detail": "Wood predicts Bitcoin ETF approval acceleration, institutional adoption, and its role as 'digital gold' will drive prices. She also expects Tesla stock to hit $2,600 by 2029.",
            "source": "ARK Big Ideas 2024, Bloomberg Interview, CNBC",
            "timeframe": "2025-2030"
        },
        {
            "rank": 10,
            "person": "António Guterres",
            "title": "Secretary-General of United Nations",
            "image": "🌍",
            "category": "🌡️ Climate & Energy",
            "prediction": "2025 will be critical for climate action - we're on track for 2.7°C warming",
            "detail": "Guterres warns that without immediate action, climate impacts will be 'catastrophic'. He predicts more extreme weather events, food insecurity, and climate migration in 2025-2026.",
            "source": "UN General Assembly 2024, COP29, Reuters",
            "timeframe": "2025-2030"
        },
        {
            "rank": 11,
            "person": "Warren Buffett",
            "title": "CEO of Berkshire Hathaway",
            "image": "🎯",
            "category": "💰 Economy & Finance",
            "prediction": "US economy will remain resilient, but 'easy money' era is over for investors",
            "detail": "Buffett has been accumulating record cash ($189B+) and selling stocks including Apple, suggesting caution about valuations. He predicts AI will reduce employment in certain sectors.",
            "source": "Berkshire Hathaway Annual Meeting 2024, CNBC",
            "timeframe": "2025-2026"
        },
        {
            "rank": 12,
            "person": "Sundar Pichai",
            "title": "CEO of Google/Alphabet",
            "image": "🔍",
            "category": "🤖 AI & Technology",
            "prediction": "Search will be completely transformed by AI within 2 years - Gemini will surpass GPT",
            "detail": "Pichai predicts Google Search will become conversational, with AI understanding context and intent. He sees AI assistants handling most routine tasks by 2026.",
            "source": "Google I/O 2024, Code Conference, The Verge",
            "timeframe": "2025-2026"
        },
        {
            "rank": 13,
            "person": "Larry Fink",
            "title": "CEO of BlackRock",
            "image": "🏢",
            "category": "💰 Economy & Finance",
            "prediction": "Private markets and infrastructure will dominate investing in 2025-2030",
            "detail": "Fink predicts a massive shift from public to private markets. He sees infrastructure (data centers, energy transition) as the biggest investment opportunity of the decade.",
            "source": "BlackRock Annual Letter 2024, WEF Davos 2025, Bloomberg",
            "timeframe": "2025-2030"
        },
        {
            "rank": 14,
            "person": "Mark Zuckerberg",
            "title": "CEO of Meta",
            "image": "👓",
            "category": "🤖 AI & Technology",
            "prediction": "Smart glasses will replace phones as primary computing device by 2030",
            "detail": "Zuckerberg predicts Meta's Ray-Ban smart glasses and future AR devices will make smartphones obsolete. He sees Llama AI models competing with GPT by late 2025.",
            "source": "Meta Connect 2024, Lex Fridman Podcast, The Verge",
            "timeframe": "2025-2030"
        },
        {
            "rank": 15,
            "person": "Nouriel Roubini",
            "title": "Economist ('Dr. Doom')",
            "image": "⚠️",
            "category": "🌍 Geopolitics",
            "prediction": "Multiple 'megathreats' will converge in 2025-2026 - debt crises, conflicts, climate disasters",
            "detail": "Roubini predicts a 'polycrisis' where economic, geopolitical, and environmental shocks amplify each other. He sees potential stagflation in developed economies.",
            "source": "Book: 'Megathreats', Project Syndicate, Bloomberg",
            "timeframe": "2025-2026"
        },
        {
            "rank": 16,
            "person": "Gwynne Shotwell",
            "title": "President of SpaceX",
            "image": "🛸",
            "category": "🚀 Space & Science",
            "prediction": "Starship will enable humans to reach Mars by 2028-2030, with prep missions in 2025-2026",
            "detail": "Shotwell predicts Starship will complete multiple successful orbital flights in 2025, followed by Moon missions. SpaceX plans to send cargo to Mars during the 2026 window.",
            "source": "SpaceX Updates, TED Talk, Space Symposium",
            "timeframe": "2025-2030"
        },
        {
            "rank": 17,
            "person": "Dr. Eric Topol",
            "title": "Cardiologist & AI Researcher, Scripps Research",
            "image": "🩺",
            "category": "🏥 Health & Medicine",
            "prediction": "AI will enable 'medicine without doctors' for routine diagnoses by 2026",
            "detail": "Topol predicts AI will diagnose skin conditions, read scans, and prescribe treatments better than average doctors. He sees major breakthroughs in personalized medicine.",
            "source": "Book: 'Deep Medicine', Nature Medicine papers, STAT News",
            "timeframe": "2025-2026"
        },
        {
            "rank": 18,
            "person": "Xi Jinping",
            "title": "President of China",
            "image": "🇨🇳",
            "category": "🌍 Geopolitics",
            "prediction": "China will achieve 'technological self-reliance' in semiconductors by 2027",
            "detail": "Xi has directed massive investment in domestic chip production to counter US sanctions. Analysts predict China may achieve 7nm or better chip production by 2025-2026.",
            "source": "CCP Congress 2024, State Media, Reuters",
            "timeframe": "2025-2027"
        },
        {
            "rank": 19,
            "person": "Demis Hassabis",
            "title": "CEO of Google DeepMind",
            "image": "🧬",
            "category": "🤖 AI & Technology",
            "prediction": "AI will solve major scientific problems - new materials, drug discovery, fusion energy",
            "detail": "Hassabis predicts AlphaFold-like breakthroughs in materials science and energy. He sees AI accelerating scientific discovery by 10-100x in the next 5 years.",
            "source": "Nobel Prize Acceptance 2024, Nature interviews, The Economist",
            "timeframe": "2025-2030"
        },
        {
            "rank": 20,
            "person": "Peter Zeihan",
            "title": "Geopolitical Strategist & Author",
            "image": "🗺️",
            "category": "🌍 Geopolitics",
            "prediction": "Global supply chains will fragment further - 2025-2026 will see 'reshoring boom'",
            "detail": "Zeihan predicts China's demographic collapse and global instability will force manufacturing back to North America and Europe. He sees major food supply disruptions possible.",
            "source": "Books: 'The End of the World Is Just the Beginning', YouTube, Podcasts",
            "timeframe": "2025-2030"
        }
    ]
    
    # Filter by category
    if category_filter != "🌐 All Categories":
        filtered_predictions = [p for p in real_predictions if p["category"] == category_filter]
    else:
        filtered_predictions = real_predictions[:10]  # Show top 10 by default
    
    st.markdown("---")
    
    # Display predictions
    for pred in filtered_predictions:
        with st.container(border=True):
            col1, col2 = st.columns([1, 15])
            
            with col1:
                st.markdown(f"<div style='font-size: 48px; text-align: center;'>{pred['image']}</div>", unsafe_allow_html=True)
            
            with col2:
                # Header with rank and category
                st.markdown(f"""
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="background: linear-gradient(90deg, #3b82f6, #60a5fa); color: white; padding: 4px 12px; border-radius: 20px; font-weight: 700; font-size: 14px;">#{pred['rank']}</span>
                    <span style="background: rgba(255,255,255,0.1); color: #94a3b8; padding: 4px 12px; border-radius: 20px; font-size: 12px;">{pred['category']}</span>
                </div>
                """, unsafe_allow_html=True)
                
                # Person info
                st.markdown(f"""
                <div style="margin-bottom: 10px;">
                    <span style="font-size: 1.3rem; font-weight: 700; color: #e0f2fe;">{pred['person']}</span>
                    <span style="color: #64748b; font-size: 0.9rem;"> — {pred['title']}</span>
                </div>
                """, unsafe_allow_html=True)
                
                # Prediction
                st.markdown(f"""
                <div style="background: rgba(59, 130, 246, 0.1); border-left: 4px solid #3b82f6; padding: 12px 16px; border-radius: 0 8px 8px 0; margin-bottom: 12px;">
                    <div style="font-size: 1.1rem; font-weight: 600; color: #fbbf24;">"{pred['prediction']}"</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Details
                st.markdown(f"""
                <div style="color: #cbd5e1; font-size: 0.95rem; line-height: 1.6; margin-bottom: 10px;">
                    {pred['detail']}
                </div>
                """, unsafe_allow_html=True)
                
                # Source and timeframe
                st.markdown(f"""
                <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem;">
                    <span style="color: #64748b;">📚 <strong>Source:</strong> {pred['source']}</span>
                    <span style="background: rgba(34, 197, 94, 0.2); color: #22c55e; padding: 3px 10px; border-radius: 12px;">⏱️ {pred['timeframe']}</span>
                </div>
                """, unsafe_allow_html=True)
    
    # Show more button
    if category_filter == "🌐 All Categories":
        st.markdown("---")
        with st.expander("📋 View All 20 Predictions", expanded=False):
            for pred in real_predictions[10:]:
                st.markdown(f"""
                <div style="background: rgba(255,255,255,0.03); padding: 15px; border-radius: 10px; margin-bottom: 10px; border: 1px solid rgba(255,255,255,0.1);">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span><strong>#{pred['rank']} {pred['person']}</strong> — {pred['title']}</span>
                        <span style="color: #64748b; font-size: 0.85rem;">{pred['category']}</span>
                    </div>
                    <div style="color: #fbbf24; margin-bottom: 8px;">"{pred['prediction']}"</div>
                    <div style="color: #94a3b8; font-size: 0.9rem;">{pred['detail']}</div>
                    <div style="color: #64748b; font-size: 0.8rem; margin-top: 8px;">📚 {pred['source']} | ⏱️ {pred['timeframe']}</div>
                </div>
                """, unsafe_allow_html=True)
    
    # Summary stats
    st.markdown("---")
    st.markdown("### 📊 Predictions by Category")
    
    cat_counts = {}
    for pred in real_predictions:
        cat = pred["category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    
    cat_cols = st.columns(len(cat_counts))
    for i, (cat, count) in enumerate(cat_counts.items()):
        with cat_cols[i]:
            st.metric(cat, f"{count} predictions")
    
    # Disclaimer
    st.markdown("---")
    st.caption("""
    ⚠️ **Disclaimer:** These predictions are sourced from public statements, interviews, books, and official communications from the individuals mentioned. 
    Predictions are inherently uncertain and should not be taken as investment or life advice. Sources include major news outlets (Bloomberg, Reuters, CNBC, Financial Times), 
    official company communications, published books, podcasts, and social media posts from verified accounts. Last updated: March 2025.
    """)

st.caption("GlobalTrend AI • Complete real-time global dashboard")
