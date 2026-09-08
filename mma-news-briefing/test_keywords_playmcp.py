import os
import json
import subprocess
import hashlib
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
from datetime import datetime, timezone, timedelta
import email.utils
from google import genai
import re
import html
import requests
from bs4 import BeautifulSoup
import time

def clean_html_tags(text):
    if not text:
        return ""
    clean_text = re.sub(r'<[^>]+>', '', text)
    clean_text = html.unescape(clean_text)
    return clean_text.strip()

def scrape_article_content(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        if "news.naver.com" in url or "n.news.naver.com" in url:
            selectors = ['#dic_area', '#articleBodyContents', '#newsct_article', '.go_trans']
            for s in selectors:
                element = soup.select_one(s)
                if element:
                    for decomp_tag in element(['script', 'style', 'iframe']):
                        decomp_tag.decompose()
                    return element.get_text(separator=' ').strip()
        
        for decomp_tag in soup(['script', 'style', 'header', 'footer', 'nav', 'aside', 'iframe']):
            decomp_tag.decompose()
            
        paragraphs = soup.find_all('p')
        if paragraphs:
            text = " ".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            if len(text.strip()) > 100:
                return text.strip()
                
        body = soup.find('body')
        if body:
            return body.get_text(separator=' ').strip()
            
        return None
    except Exception as e:
        print(f"[Warning] Scrape failed for {url}: {e}")
        return None

def is_published_within_days(pub_date_str, days=7):
    try:
        dt = email.utils.parsedate_to_datetime(pub_date_str)
        kst_tz = timezone(timedelta(hours=9))
        dt_kst = dt.astimezone(kst_tz)
        now_kst = datetime.now(timezone.utc).astimezone(kst_tz)
        cutoff_date = (now_kst - timedelta(days=days)).date()
        return dt_kst.date() >= cutoff_date
    except Exception as e:
        print(f"[Warning] Failed to parse pubDate {pub_date_str}: {e}")
        return True

def main():
    # 1. Load credentials
    playmcp_access = os.getenv("PLAYMCP_ACCESS_TOKEN")
    playmcp_refresh = os.getenv("PLAYMCP_REFRESH_TOKEN")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    if not playmcp_access or not playmcp_refresh:
        print("[Critical] Missing PLAYMCP_ACCESS_TOKEN or PLAYMCP_REFRESH_TOKEN environment variables.")
        exit(1)
    if not gemini_key:
        print("[Critical] Missing GEMINI_API_KEY.")
        exit(1)
        
    print("[Info] Setting up ~/.mcporter/credentials.json...")
    mcporter_dir = os.path.expanduser("~/.mcporter")
    os.makedirs(mcporter_dir, exist_ok=True)
    credentials_path = os.path.join(mcporter_dir, "credentials.json")
    
    # Calculate hash key
    raw_str = '{"name":"mcp-gateway","url":"https://playmcp.kakao.com/mcp","command":null}'
    hash_val = hashlib.sha256(raw_str.encode('utf-8')).hexdigest()[:16]
    entry_key = f"mcp-gateway|{hash_val}"
    
    cred_data = {
        "version": 1,
        "entries": {
            entry_key: {
                "serverName": "mcp-gateway",
                "serverUrl": "https://playmcp.kakao.com/mcp",
                "tokens": {
                    "access_token": playmcp_access,
                    "token_type": "Bearer",
                    "refresh_token": playmcp_refresh
                },
                "clientInfo": {
                    "client_id": "HElMUWdVoroTsrXxezeTSemg8gXzzCKWARb5MJux8gY"
                },
                "updatedAt": datetime.utcnow().isoformat() + "Z"
            }
        }
    }
    
    with open(credentials_path, 'w', encoding='utf-8') as f:
        json.dump(cred_data, f, indent=2)
        
    # 2. Add mcp-gateway to mcporter config
    print("[Info] Registering mcp-gateway config...")
    subprocess.run([
        "mcporter", "config", "add", "mcp-gateway", 
        "https://playmcp.kakao.com/mcp", "--auth", "oauth", "--scope", "home"
    ], check=True, shell=False)
    
    env = os.environ.copy()
    env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
    
    # 3. Fetch news for specified keywords: 전역증, 병적기록표, 대체역, 대체복무요원, 대체역심사위원회
    keywords = ["전역증", "병적기록표", "대체역", "대체복무요원", "대체역심사위원회"]
    all_news_items = []
    seen_links = set()
    
    print(f"[Info] Fetching news for keywords: {keywords}...")
    for kw in keywords:
        try:
            args_json = json.dumps({
                "query": kw,
                "display": 30,
                "start": 1,
                "sort": "date"
            })
            result = subprocess.run([
                "mcporter", "call", "mcp-gateway.NaverSearch-search_news", 
                "--args", args_json
            ], capture_output=True, text=True, check=True, env=env, shell=False)
            
            data = json.loads(result.stdout)
            items = data.get("items", [])
            print(f"[Info] Keyword '{kw}' returned {len(items)} items.")
            for item in items:
                link = item.get("link", "")
                if link and link not in seen_links:
                    seen_links.add(link)
                    all_news_items.append(item)
        except Exception as e:
            print(f"[Warning] Failed to fetch news for keyword {kw}: {e}")

    print(f"[Info] Found {len(all_news_items)} total unique raw news items across keywords.")
    
    # Filter items published within last 7 days
    filtered_items = [item for item in all_news_items if is_published_within_days(item.get("pubDate", ""), days=7)]
    print(f"[Info] Filtered {len(filtered_items)} items published within the last 7 days.")
    
    if not filtered_items:
        print("[Warning] No articles found within 7 days. Falling back to all gathered news items.")
        filtered_items = all_news_items
        
    # Take up to 10 articles
    selected_items = filtered_items[:10]
    print(f"[Info] Selected {len(selected_items)} articles for summarization.")
    
    # 4. Scrape full content
    processed_articles = []
    for item in selected_items:
        title = clean_html_tags(item.get("title", ""))
        link = item.get("link", "")
        description = clean_html_tags(item.get("description", ""))
        
        print(f"[Info] Scraped content for: {title}")
        content = scrape_article_content(link)
        if not content:
            content = description
            
        processed_articles.append({
            "title": title,
            "link": link,
            "content": content
        })
        
    # 5. Summarize using Gemini API
    print("[Info] Generating test briefing text using Gemini...")
    
    unverified_ssl_context = ssl.create_default_context()
    unverified_ssl_context.check_hostname = False
    unverified_ssl_context.verify_mode = ssl.CERT_NONE
    
    from google.genai import types
    client = genai.Client(
        api_key=gemini_key,
        http_options=types.HttpOptions(
            api_version='v1beta',
            client_args={'verify': unverified_ssl_context},
            async_client_args={'verify': unverified_ssl_context}
        )
    )
    
    prompt = """
당신은 친절하고 전문적인 AI 뉴스 아나운서입니다. 아래 수집된 병무/대체역 관련 뉴스 데이터(전역증, 병적기록표, 대체역, 대체복무요원, 대체역심사위원회 등)를 바탕으로, 모바일 카카오톡 메시지용 브리핑을 자연스러운 대화체로 요약해서 작성해 주세요.

[작성 지침]
1. 인사말: "📢 [테스트] 안녕하세요! 요청하신 병무/대체역 주요 키워드 뉴스 요약 브리핑입니다."로 시작해 주세요.
2. 본문 작성:
   - 수집된 기사 중 중요한 소식을 우선으로 하여 최대 10개의 핵심 뉴스를 선별해 작성해 주세요.
   - 각 뉴스마다 자연스러운 구어체 대화 형식(예: "~소식입니다", "~할 예정이라고 합니다")으로 2~3문장의 명확한 요약 단락을 작성해 주세요.
   - 요약 단락 바로 다음 줄에 해당 기사의 링크(URL)만 그대로 정확히 출력해 주세요. '기사 보기:', '기사 링크:', 대괄호 '[]', '()' 등 어떠한 수식어구도 절대 붙이지 말고 순수한 URL만 단독으로 적어야 합니다.
   - 뉴스 요약과 링크 사이에는 줄바꿈을 하고, 각 기사 사이에는 빈 줄 하나를 두어 구분해 주세요.
   - 글머리 기호(•, -), 번호(1., 2.), 대괄호, 마크다운 볼드체(예: **텍스트**) 등은 절대 사용하지 마세요.

[뉴스 데이터]
"""
    for idx, art in enumerate(processed_articles, 1):
        prompt += f"\n---\n기사 {idx}:\n"
        prompt += f"제목: {art['title']}\n"
        prompt += f"링크: {art['link']}\n"
        prompt += f"본문: {art['content'][:2500]}\n"
        
    briefing_text = None
    models_to_try = ['gemini-3.1-flash-lite', 'gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.0-flash']
    
    for model_name in models_to_try:
        print(f"[Info] Attempting summarization with model: {model_name}...")
        for attempt in range(1, 4):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                briefing_text = response.text
                if briefing_text:
                    print(f"[Success] Summarization succeeded with model {model_name} on attempt {attempt}.")
                    break
            except Exception as e:
                err_str = str(e)
                if "503" in err_str or "UNAVAILABLE" in err_str:
                    print(f"[Warning] Model {model_name} is temporarily unavailable (503). Retrying in {attempt * 3}s... (Attempt {attempt}/3)")
                    time.sleep(attempt * 3)
                else:
                    print(f"[Warning] Failed with model {model_name}: {e}")
                    break
        
        if briefing_text:
            break
            
    if not briefing_text:
        print("[Critical] Gemini summarization failed for all models.")
        exit(1)
        
    print(f"[Info] Test briefing generated (Length: {len(briefing_text)} chars):\n{briefing_text}")
    
    # 6. Split briefing text and send multiple messages to KakaoTalk (No TTS as requested)
    print("[Info] Splitting briefing text and sending messages to KakaoTalk...")
    
    raw_paragraphs = briefing_text.strip().split("\n\n")
    message_chunks = []
    current_chunk = ""
    
    greeting = ""
    if raw_paragraphs and "안녕하세요" in raw_paragraphs[0]:
        greeting = raw_paragraphs[0]
        raw_paragraphs = raw_paragraphs[1:]
        
    for para in raw_paragraphs:
        test_chunk = current_chunk
        if not test_chunk and greeting:
            test_chunk = greeting + "\n\n"
            
        test_chunk += para + "\n\n"
        
        if len(test_chunk) < 900:
            if not current_chunk and greeting:
                current_chunk = greeting + "\n\n"
            current_chunk += para + "\n\n"
        else:
            if current_chunk:
                message_chunks.append(current_chunk.strip())
            current_chunk = para + "\n\n"
            
    if current_chunk:
        message_chunks.append(current_chunk.strip())
        
    if not message_chunks:
        message_chunks = [briefing_text]
        
    for idx, chunk in enumerate(message_chunks, 1):
        print(f"[Info] Sending chunk {idx}/{len(message_chunks)} (Length: {len(chunk)} chars)...")
        try:
            args_json = json.dumps({
                "message": chunk
            })
            result = subprocess.run([
                "mcporter", "call", "mcp-gateway.KakaotalkChat-MemoChat", 
                "--args", args_json
            ], capture_output=True, text=True, check=True, env=env, shell=False)
            print(f"[Success] Chunk {idx} delivered via PlayMCP.")
        except subprocess.CalledProcessError as e:
            print(f"[Critical] Failed to send chunk {idx}: {e.returncode}\n{e.stdout}\n{e.stderr}")
            exit(1)
        except Exception as e:
            print(f"[Critical] Failed to send chunk {idx}: {e}")
            exit(1)
            
    # 7. Check and update tokens if refreshed
    try:
        with open(credentials_path, 'r', encoding='utf-8') as f:
            updated_cred = json.load(f)
        
        tokens = updated_cred.get("entries", {}).get(entry_key, {}).get("tokens", {})
        new_access = tokens.get("access_token")
        new_refresh = tokens.get("refresh_token")
        
        if new_access and new_access != playmcp_access:
            print("[Info] Access Token refreshed. Syncing with GitHub Secrets...")
            subprocess.run(["gh", "secret", "set", "PLAYMCP_ACCESS_TOKEN", "--body", new_access], shell=False)
        if new_refresh and new_refresh != playmcp_refresh:
            print("[Info] Refresh Token refreshed. Syncing with GitHub Secrets...")
            subprocess.run(["gh", "secret", "set", "PLAYMCP_REFRESH_TOKEN", "--body", new_refresh], shell=False)
    except Exception as e:
        print(f"[Warning] Failed to sync updated tokens: {e}")

if __name__ == "__main__":
    main()
