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

# --- 1. 데이터 수집 (웹 스크래핑 추가) ---
def scrape_article_text(url):
    """URL에 접속해 실제 본문의 <p> 태그 텍스트를 긁어옵니다."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.get(url, headers=headers, timeout=5)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        paragraphs = soup.find_all('p')
        text = " ".join([p.get_text() for p in paragraphs])
        # 너무 길면 Gemini 토큰 제한이 걸릴 수 있으므로 3000자로 제한
        return text[:3000] if len(text) > 100 else None 
    except Exception as e:
        print(f"Scraping failed for {url}: {e}")
        return None

def fetch_rss(url, category):
    items = []
    try:
        feed = feedparser.parse(url)
        # 회원님이 변경하신 7일 기준으로 넉넉하게 세팅!
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
        # 검색 조건 완화 (OR 사용): 바이오, FDA 승인, 임상시험 중 하나라도 포함되면 수집
        urls = ["https://news.google.com/rss/search?q=Biotech+OR+%22FDA+approval%22+OR+%22Clinical+Trial%22&hl=en-US&gl=US&ceid=US:en"]
    elif mode == "PATENT":
        # 검색 조건 완화 (OR 사용): 특허, 기술 혁신 중 하나라도 포함되면 수집
        urls = ["https://news.google.com/rss/search?q=Patent+OR+%22Technology+Innovation%22+OR+%22Future+Tech%22&hl=en-US&gl=US&ceid=US:en"]
    
    for u in urls: items.extend(fetch_rss(u, mode))
    return items

# --- 2. 주제 선정 ---
def select_top_2(candidates, history, category_name):
    history_ids = [h['id'] for h in history]
    filtered = [c for c in candidates if c['id'] not in history_ids]
    
    if len(filtered) < 2: return filtered[:2]
    
    # 💡 Gemini 3 Flash Preview로 변경
    model = genai.GenerativeModel('gemini-3.0-flash-preview')
    cand_txt = "\n".join([f"{i}. {c['title']}" for i, c in enumerate(filtered[:15])])
    
    prompt = f"""
    역할: 전문 투자/기술 블로그 편집장 '스포(spo)'.
    목표: {category_name} 분야에서 심층 분석(Deep-Dive)이 가능하고 투자자들의 관심이 집중될 뉴스 2개 선정.
    
    [후보군]
    {cand_txt}
    
    조건:
    1. 기술적 원리나 시장 파급력을 분석할 거리가 있는 주제 우선.
    2. 오직 숫자 2개만 반환 (예: 1, 4).
    """
    try:
        res = model.generate_content(prompt)
        nums = [int(s) for s in re.findall(r'\b\d+\b', res.text)]
        if len(nums) >= 2:
            return [filtered[nums[0]], filtered[nums[1]]]
    except: pass
    return filtered[:2]

# --- 3. 글 작성 ---
def write_blog_post(topic1, topic2, category_name):
    print(f"Writing {category_name} Post with Gemini 3 Flash Preview...")
    
    # 💡 Gemini 3 Flash Preview 유지
    model = genai.GenerativeModel('gemini-3.0-flash-preview')
    
    structure_instruction = """
    각 주제별로 반드시 아래 5가지 H2 태그 섹션을 포함해야 함:
    1. <h2>1. 배경 및 개요 (The Context)</h2> : 현 상황을 3줄 요약 리스트(<ul>)로 제시.
    2. <h2>2. 기술적 메커니즘 (Technical Deep-Dive)</h2> : 핵심 원리를 설명하되, 기존 기술과의 비교나 장단점을 보여주는 깔끔한 HTML <table>을 1개 이상 반드시 포함.
    3. <h2>3. 시장 판도 및 경쟁사 분석 (Market Dynamics)</h2> : 관련 기업의 티커(Ticker), 시장 점유율, 최근 매출 등 구체적인 [수치/데이터]를 반드시 포함하여 객관적으로 작성.
    4. <h2>4. 리스크 및 한계점 (Risk Factors)</h2> : 규제, 경쟁, 기술적 장벽 분석.
    5. <h2>5. 스포(spo)의 인사이트 (Actionable Insights)</h2> : 투자자/업계 종사자 관점의 시사점.
    """

    glossary_rule = """
    [매우 중요 - 용어 강조 규칙]
    어려운 '전문 용어', '약어', '핵심 기술 용어'는 반드시 <u> 태그로 감싸주세요. (예: <u>임상 3상</u>)
    """

    bold_rule = """
    [매우 중요 - 가독성 향상 규칙 (Bold)]
    각 문단에서 가장 중요한 '핵심 문장'이나 '결정적인 수치'는 반드시 <b> 태그를 사용하여 굵은 글씨로 강조해주세요.
    """

    outline = model.generate_content(f"주제1: {topic1['title']}\n주제2: {topic2['title']}\n위 두 주제로 '{category_name} 심층 분석' 블로그 글 개요 작성.").text
    
    p1_prompt = f"""
    역할: 전문 테크/바이오 분석가 '스포(spo)'.
    어조: '해요'체 사용. 전문적이나 친절하게.
    
    개요: {outline}
    주제 1: {topic1['title']} / 원문 내용: {topic1['raw']}
    
    {glossary_rule}
    {bold_rule}
    
    [작성 지침]
    - 블로그 포맷 HTML 태그만 출력 (```html 등의 마크다운 절대 제외).
    - <h1>[{category_name} 심층분석] {topic1['title']}</h1>
    - [IMAGE_PLACEHOLDER_1]
    {structure_instruction}
    - [IMAGE_PLACEHOLDER_2]
    - 주제 1의 모든 내용을 작성하고 멈출 것.
    """
    part1 = re.sub(r"```[a-zA-Z]*\n?|```", "", model.generate_content(p1_prompt).text).strip()
    
    p2_prompt = f"""
    앞부분: {part1}
    주제 2: {topic2['title']} / 원문 내용: {topic2['raw']}
    
    {glossary_rule}
    {bold_rule}
    
    [작성 지침]
    - 앞부분에 이어 자연스럽게 작성. HTML 태그만 출력 (```html 등의 마크다운 절대 제외).
    - <br><hr style="border: 0; height: 1px; background: #ddd; margin: 40px 0;"><br>
    - <h1>[{category_name} 심층분석] {topic2['title']}</h1>
    - [IMAGE_PLACEHOLDER_3]
    {structure_instruction}
    - [IMAGE_PLACEHOLDER_4]
    
    - <br><hr style="border: 0; height: 2px; background: #2c3e50; margin: 50px 0;"><br>
    
    [통합 및 마무리 섹션 추가]
    
    - <h2>🎯 통합 인사이트: 두 뉴스가 그리는 미래 (The Bridge)</h2>
    - 주제 1과 주제 2를 관통하는 핵심 트렌드와 연결 고리를 1~2문단으로 분석해주세요.
    
    - <h2>📖 오늘의 용어 정리 (Glossary)</h2>
    - 위 글에서 <u>태그로 감싸서 표시했던 어려운 용어들</u>을 모두 모아 초보자도 이해할 수 있게 해설 (최소 5개 이상).
    - <ul><li><b>용어명</b>: 설명...</li></ul> 형식.
      
    - <h2>🔍 SEO 및 태그 정보 (업로드용)</h2>
    - <div style="background-color:#f0f4f8; padding:20px; border-radius:8px; border:1px solid #d1e1f0;">
        <p><b>Meta 초안 (한 줄 요약):</b> [여기에 전체 글을 아우르는 150자 이내의 매력적인 요약 작성]</p>
        <p><b>추천 태그:</b> [여기에 쉼표(,)로 구분된 검색 키워드 7개 작성. 예: #인공지능, #테크놀로지]</p>
      </div>

    - <hr style="border: 0; height: 1px; background: #eee; margin: 40px 0;">
    - <p style="color:grey; font-size: 0.9em; text-align: center;">* 본 콘텐츠는 정보 제공을 목적으로 하며, 투자의 책임은 본인에게 있습니다. <br> Editor: 스포(spo)</p>
    """
    part2 = re.sub(r"```[a-zA-Z]*\n?|```", "", model.generate_content(p2_prompt).text).strip()
    
    return part1 + "\n" + part2

# --- 4. 이미지 및 이메일 전송 ---
def get_image_tag(keyword, alt_text=""):
    search_query = f"{keyword} high quality"
    url = f"https://api.unsplash.com/search/photos?query={search_query}&per_page=1&orientation=landscape&client_id={UNSPLASH_ACCESS_KEY}"
    try:
        data = requests.get(url, timeout=5).json()
        img_url = data['results'][0]['urls']['regular']
        return f"""
        <figure style="margin: 30px 0;">
            <img src='{img_url}' alt='{alt_text}' style='width:100%; border-radius:12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);'>
            <figcaption style='color:#666; font-size:13px; text-align:center; margin-top:10px;'>Source: Unsplash ({keyword})</figcaption>
        </figure>
        """
    except: return ""

def inject_images(html_text, t1, t2):
    # 💡 Gemini 3 Flash Preview 유지
    model = genai.GenerativeModel('gemini-3.0-flash-preview')
    try:
        k1_main = model.generate_content(f"Extract one main object noun from: {t1['title']}").text.strip()
        k1_sub = model.generate_content(f"Extract abstract concept (e.g. data, biology) from: {t1['title']}").text.strip()
        k2_main = model.generate_content(f"Extract one main object noun from: {t2['title']}").text.strip()
        k2_sub = model.generate_content(f"Extract abstract concept from: {t2['title']}").text.strip()
    except: 
        k1_main, k1_sub = "technology", "analysis"
        k2_main, k2_sub = "news", "future"
    
    html_text = html_text.replace("[IMAGE_PLACEHOLDER_1]", get_image_tag(k1_main, t1['title']))
    html_text = html_text.replace("[IMAGE_PLACEHOLDER_2]", get_image_tag(k1_sub + " visualization", "Analysis")) 
    html_text = html_text.replace("[IMAGE_PLACEHOLDER_3]", get_image_tag(k2_main, t2['title']))
    html_text = html_text.replace("[IMAGE_PLACEHOLDER_4]", get_image_tag(k2_sub + " visualization", "Market Insight"))
    return html_text

def send_email(subject, final_content):
    escaped_html = html.escape(final_content)
    
    email_body = f"""
    <div style="font-family: sans-serif; max-width: 800px; margin: 0 auto;">
        <h2 style="color: #2c3e50;">스포(spo) 편집장님, 새 포스팅이 준비되었습니다! 🎉 (Gemini 3 Flash Preview)</h2>
        <p style="color: #e74c3c; font-weight: bold;">[티스토리 업로드용 HTML 코드]</p>
        <p style="font-size: 14px; color: #555;">아래 박스 안쪽을 클릭하고 <code>Ctrl+A</code>(전체선택) 후 복사하여 티스토리 'HTML 모드'에 붙여넣으세요. 맨 하단의 SEO 정보는 태그 입력 시 활용하세요.</p>
        
        <textarea style="width: 100%; height: 200px; font-family: monospace; font-size: 13px; background-color: #f8f9fa; padding: 15px; border: 1px solid #ced4da; border-radius: 5px; cursor: text;" readonly>{escaped_html}</textarea>
        
        <hr style="border: 0; height: 1px; background: #ddd; margin: 40px 0;">
        
        <h3 style="color: #2c3e50;">👀 포스팅 미리보기</h3>
        <div style="border: 1px solid #eee; padding: 30px; border-radius: 10px; background-color: #fff;">
            {final_content}
        </div>
    </div>
    """

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = subject
    msg.attach(MIMEText(email_body, 'html'))
    
    try:
        s = smtplib.SMTP('smtp.gmail.com', 587)
        s.starttls()
        s.login(EMAIL_SENDER, EMAIL_PASSWORD)
        s.send_message(msg)
        s.quit()
        print(f"✅ Email Sent: {subject}")
    except Exception as e:
        print(f"❌ Email Fail: {e}")

# --- 5. 통합 처리 함수 ---
def process_and_send(mode, category_korean, history):
    print(f"\n>>> Processing: {category_korean} ({mode})")
    candidates = get_candidates(mode)
    selected = select_top_2(candidates, history, category_korean)
    
    if len(selected) < 2:
        print(f"Not enough news for {mode}")
        return []
        
    raw_html = write_blog_post(selected[0], selected[1], category_korean)
    html_with_images = inject_images(raw_html, selected[0], selected[1])
    
    final_tistory_content = f"""
    <div class="spo-analysis-report" style="line-height: 1.8; color: #333; font-family: 'Noto Sans KR', sans-serif; word-break: keep-all; padding: 10px;">
        {html_with_images}
    </div>
    """
    
    subject = f"[{category_korean} 분석] {selected[0]['title']} & {selected[1]['title']}"
    send_email(subject, final_tistory_content)
    
    return selected

# --- 메인 실행 ---
def main():
    history_file = 'history.json'
    history = load_history(history_file)
    
    kst_now = datetime.datetime.now() + datetime.timedelta(hours=9)
    weekday = kst_now.weekday()
    
    new_items_total = []

    if weekday == 0: # 월요일
        items = process_and_send("TECH", "테크", history)
        new_items_total.extend(items)
        
    else: # 화~일요일
        items_bio = process_and_send("BIO", "바이오", history)
        new_items_total.extend(items_bio)
        
        items_patent = process_and_send("PATENT", "특허", history)
        new_items_total.extend(items_patent)
    
    if new_items_total:
        save_history(history_file, history, new_items_total)

if __name__ == "__main__":
    main()
