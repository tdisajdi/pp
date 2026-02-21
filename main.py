import os
import json
import datetime
import time
import requests
import feedparser
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai 
import re
import html
from bs4 import BeautifulSoup

# --- 설정값 ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")

# 구형 SDK 방식으로 설정 (GitHub Actions 환경 호환성 유지)
genai.configure(api_key=GEMINI_API_KEY)

# --- 0. 히스토리 관리 ---
def load_history(filepath):
    if not os.path.exists(filepath): return []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return []

def save_history(filepath, history, new_items):
    cutoff = datetime.datetime.now() - datetime.timedelta(days=30)
    cleaned = []
    
    for item in history:
        try:
            d = datetime.datetime.strptime(item.get('date', '2000-01-01'), "%Y-%m-%d")
            if d >= cutoff: cleaned.append(item)
        except: continue
        
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    for item in new_items:
        cleaned.append({"id": item['id'], "title": item['title'], "date": today})
        
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=4)

# --- 1. 데이터 수집 ---
def scrape_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.get(url, headers=headers, timeout=5)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        paragraphs = soup.find_all('p')
        text = " ".join([p.get_text() for p in paragraphs])
        return text[:3000] if len(text) > 100 else None 
    except Exception as e:
        print(f"Scraping failed for {url}: {e}")
        return None

def fetch_rss(url, category):
    items = []
    try:
        feed = feedparser.parse(url)
        cutoff = datetime.datetime.now() - datetime.timedelta(days=7)
        for entry in feed.entries:
            if 'published_parsed' in entry and entry.published_parsed:
                pub_date = datetime.datetime.fromtimestamp(time.mktime(entry.published_parsed))
                if pub_date < cutoff: continue
            
            print(f"Scraping: {entry.title}")
            raw_text = scrape_article_text(entry.link)
            if not raw_text:
                raw_text = (entry.summary if 'summary' in entry else entry.title)[:2000]
            
            items.append({
                "id": entry.link,
                "title": entry.title,
                "type": category,
                "raw": raw_text
            })
    except Exception as e:
        print(f"RSS Error ({url}): {e}")
    return items

def get_candidates(mode):
    items = []
    if mode == "TECH":
        urls = ["https://www.theverge.com/rss/index.xml", "https://techcrunch.com/feed/"]
    elif mode == "BIO":
        urls = ["https://news.google.com/rss/search?q=Biotech+OR+%22FDA+approval%22+OR+%22Clinical+Trial%22&hl=en-US&gl=US&ceid=US:en"]
    elif mode == "PATENT":
        urls = ["https://news.google.com/rss/search?q=Patent+OR+%22Technology+Innovation%22+OR+%22Future+Tech%22&hl=en-US&gl=US&ceid=US:en"]
    
    for u in urls: items.extend(fetch_rss(u, mode))
    return items

# --- 2. 주제 선정 ---
def select_top_2(candidates, history, category_name):
    history_ids = [h['id'] for h in history]
    filtered = [c for c in candidates if c['id'] not in history_ids]
    
    if len(filtered) < 2: return filtered[:2]
    
    cand_txt = "\n".join([f"{i}. {c['title']}" for i, c in enumerate(filtered[:15])])
    
    prompt = f"""
    역할: 전문 투자/기술 블로그 편집장 '스포(spo)'.
    목표: {category_name} 분야에서 심층 분석이 가능하고 투자자들의 관심이 집중될 뉴스 2개 선정.
    [후보군]
    {cand_txt}
    조건: 오직 숫자 2개만 반환 (예: 1, 4).
    """
    try:
        model = genai.GenerativeModel('gemini-3.0-flash-preview')
        res = model.generate_content(prompt)
        nums = [int(s) for s in re.findall(r'\b\d+\b', res.text)]
        if len(nums) >= 2:
            return [filtered[nums[0]], filtered[nums[1]]]
    except: pass
    return filtered[:2]

# --- 3. 글 작성 ---
def write_blog_post(topic1, topic2, category_name):
    print(f"Writing {category_name} Post with Gemini 3 Flash Preview...")
    model = genai.GenerativeModel('gemini-3.0-flash-preview')
    
    structure_instruction = """
    각 주제별로 반드시 아래 5가지 섹션을 포함:
    1. <h2>1. 배경 및 개요 (The Context)</h2> : 3줄 요약 리스트.
    2. <h2>2. 기술적 메커니즘 (Technical Deep-Dive)</h2> : HTML <table> 포함.
    3. <h2>3. 시장 판도 및 경쟁사 분석 (Market Dynamics)</h2> : 수치/데이터 포함.
    4. <h2>4. 리스크 및 한계점 (Risk Factors)</h2>
    5. <h2>5. 스포(spo)의 인사이트 (Actionable Insights)</h2>
    """

    outline = model.generate_content(f"주제1: {topic1['title']}\n주제2: {topic2['title']}\n위 두 주제로 '{category_name} 심층 분석' 블로그 글 개요 작성.").text
    
    p1_prompt = f"역할: 전문 테크 분석가 '스포'. 개요: {outline}\n주제 1: {topic1['title']} / 원문: {topic1['raw']}\n\n[지침]\n- HTML 태그만 출력.\n- <h1>[{category_name} 심층분석] {topic1['title']}</h1>\n- [IMAGE_PLACEHOLDER_1]\n{structure_instruction}\n- [IMAGE_PLACEHOLDER_2]"
    part1 = re.sub(r"```[a-zA-Z]*\n?|```", "", model.generate_content(p1_prompt).text).strip()
    
    p2_prompt = f"앞부분: {part1}\n주제 2: {topic2['title']} / 원문: {topic2['raw']}\n\n[지침]\n- 자연스럽게 이어 작성.\n- <h1>[{category_name} 심층분석] {topic2['title']}</h1>\n- [IMAGE_PLACEHOLDER_3]\n{structure_instruction}\n- [IMAGE_PLACEHOLDER_4]\n- 마무리 섹션(통합 인사이트, 오늘의 용어 정리, SEO 정보) 포함."
    part2 = re.sub(r"```[a-zA-Z]*\n?|```", "", model.generate_content(p2_prompt).text).strip()
    
    return part1 + "\n" + part2

# --- 4. 이미지 및 이메일 전송 ---
def get_image_tag(keyword, alt_text=""):
    url = f"https://api.unsplash.com/search/photos?query={keyword}&per_page=1&orientation=landscape&client_id={UNSPLASH_ACCESS_KEY}"
    try:
        data = requests.get(url, timeout=5).json()
        img_url = data['results'][0]['urls']['regular']
        return f"<figure style='margin:30px 0;'><img src='{img_url}' alt='{alt_text}' style='width:100%; border-radius:12px;'><figcaption style='text-align:center; color:#666;'>Source: Unsplash</figcaption></figure>"
    except: return ""

def inject_images(html_text, t1, t2):
    model = genai.GenerativeModel('gemini-3.0-flash-preview')
    try:
        k1 = model.generate_content(f"Extract 1 keyword from: {t1['title']}").text.strip()
        k2 = model.generate_content(f"Extract 1 keyword from: {t2['title']}").text.strip()
    except: k1, k2 = "tech", "business"
    
    html_text = html_text.replace("[IMAGE_PLACEHOLDER_1]", get_image_tag(k1)).replace("[IMAGE_PLACEHOLDER_3]", get_image_tag(k2))
    return html_text.replace("[IMAGE_PLACEHOLDER_2]", "").replace("[IMAGE_PLACEHOLDER_4]", "")

def send_email(subject, final_content):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = subject
    msg.attach(MIMEText(f"<h3>티스토리 HTML 코드:</h3><textarea style='width:100%;height:200px;'>{html.escape(final_content)}</textarea><hr>{final_content}", 'html'))
    
    try:
        s = smtplib.SMTP('smtp.gmail.com', 587)
        s.starttls()
        s.login(EMAIL_SENDER, EMAIL_PASSWORD)
        s.send_message(msg)
        s.quit()
        print(f"✅ Email Sent: {subject}")
    except Exception as e: print(f"❌ Email Fail: {e}")

# --- 5. 통합 처리 ---
def process_and_send(mode, category_korean, history):
    print(f"\n>>> Processing: {category_korean}")
    candidates = get_candidates(mode)
    selected = select_top_2(candidates, history, category_korean)
    
    if len(selected) < 2: return []
        
    raw_html = write_blog_post(selected[0], selected[1], category_korean)
    html_with_images = inject_images(raw_html, selected[0], selected[1])
    
    final_content = f"<div style='line-height:1.8; font-family:sans-serif;'>{html_with_images}</div>"
    send_email(f"[{category_korean} 분석] {selected[0]['title']}", final_content)
    
    return selected

def main():
    history_file = 'history.json'
    history = load_history(history_file)
    kst_now = datetime.datetime.now() + datetime.timedelta(hours=9)
    
    new_items = []
    if kst_now.weekday() == 0:
        new_items.extend(process_and_send("TECH", "테크", history))
    else:
        new_items.extend(process_and_send("BIO", "바이오", history))
        new_items.extend(process_and_send("PATENT", "특허", history))
    
    if new_items: save_history(history_file, history, new_items)

if __name__ == "__main__":
    main()
