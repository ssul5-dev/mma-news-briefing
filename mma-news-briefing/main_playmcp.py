import os
import json
import subprocess
import hashlib
from datetime import datetime
from google import genai
import re
import html
import requests
from bs4 import BeautifulSoup

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
    
    # Bypass TLS verification for self-signed cert in corporate network
    env = os.environ.copy()
    env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
    
    # 3. Fetch news using PlayMCP Naver Search tool
    print("[Info] Fetching latest '병무청' news via PlayMCP Naver Search...")
    try:
        result = subprocess.run([
            "mcporter", "call", "mcp-gateway.NaverSearch-search_news", 
            "병무청", "5", "1", "date"
        ], capture_output=True, text=True, check=True, env=env, shell=False)
        
        news_data = json.loads(result.stdout)
        news_items = news_data.get("items", [])
    except subprocess.CalledProcessError as e:
        print(f"[Critical] Failed to call NaverSearch-search_news. Exit code: {e.returncode}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        exit(1)
    except Exception as e:
        print(f"[Critical] Failed to call NaverSearch-search_news: {e}")
        exit(1)
        
    print(f"[Info] Found {len(news_items)} news items from search results.")
    
    # 4. Scrape full content of articles
    processed_articles = []
    for item in news_items:
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
    print("[Info] Generating briefing text using Gemini...")
    client = genai.Client(api_key=gemini_key)
    prompt = """
당신은 뉴스 요약 전문가입니다. 아래 수집된 병무청 관련 뉴스 리스트를 요약하여 모바일 카카오톡 화면에 최적화된 브리핑 메시지를 작성해 주세요.

[작성 지침]
1. 제목: "📢 오늘의 병무청 뉴스 브리핑"으로 시작하세요.
2. 각 기사별로 아래 형식을 정확히 따르십시오:
   - 기사의 제목을 간결하게 한 줄로 출력 (볼드체 사용 금지)
   - 기사의 핵심 내용을 3줄 이내의 글머리 기호(•) 형식으로 요약
   - 주요 키워드나 수치는 **볼드체**로 처리하세요.
3. 메시지의 총 길이는 공백 포함 850자 이하가 되도록 아주 간결하게 유지해야 합니다.
4. 불필요한 기사 링크나 꼬리말은 생략하세요.

[뉴스 데이터]
"""
    for idx, art in enumerate(processed_articles, 1):
        prompt += f"\n---\n기사 {idx}:\n"
        prompt += f"제목: {art['title']}\n"
        prompt += f"본문: {art['content'][:2500]}\n"
        
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        briefing_text = response.text
        if len(briefing_text) > 950:
            briefing_text = briefing_text[:900] + "\n\n(이하 생략)"
    except Exception as e:
        print(f"[Critical] Gemini summarization failed: {e}")
        exit(1)
        
    print(f"[Info] Briefing generated (Length: {len(briefing_text)} chars):\n{briefing_text}")
    
    # 6. Send message using PlayMCP 나와의 채팅방 tool
    print("[Info] Sending message to KakaoTalk 나와의 채팅방...")
    try:
        result = subprocess.run([
            "mcporter", "call", "mcp-gateway.KakaotalkChat-MemoChat", 
            "--message", briefing_text
        ], capture_output=True, text=True, check=True, env=env, shell=False)
        print("[Success] Briefing message delivered via PlayMCP.")
    except subprocess.CalledProcessError as e:
        print(f"[Critical] Failed to send message via KakaotalkChat-MemoChat. Exit code: {e.returncode}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        exit(1)
    except Exception as e:
        print(f"[Critical] Failed to send message via KakaotalkChat-MemoChat: {e}")
        exit(1)
        
    # 7. Check and update dynamically refreshed tokens
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
