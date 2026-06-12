import os
import base64
import urllib.parse
import requests
import urllib3

# Suppress insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def main():
    token = os.getenv("GH_TOKEN", "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")
    repo = "ssul5-dev/mma-news-briefing"
    
    # Files mapping: remote path -> local path
    files_to_upload = {
        "mma-news-briefing/requirements.txt": "mma-news-briefing/requirements.txt",
        "mma-news-briefing/main_playmcp.py": "mma-news-briefing/main_playmcp.py",
        "mma-news-briefing/upload_to_github.py": "mma-news-briefing/upload_to_github.py",
        "mma-news-briefing/README.md": "mma-news-briefing/README.md",
        "mma-news-briefing/test_scraper.py": "mma-news-briefing/test_scraper.py",
        "mma-news-briefing/configure_credentials.py": "mma-news-briefing/configure_credentials.py",
        "mma-news-briefing/작업지시서_병무청_뉴스_브리핑_자동화.md": "mma-news-briefing/작업지시서_병무청_뉴스_브리핑_자동화.md",
        "podcast/index.html": "mma-news-briefing/podcast/index.html",
        "podcast/audio/latest.mp3": "mma-news-briefing/podcast/audio/latest.mp3",
        ".github/workflows/daily_briefing.yml": ".github/workflows/daily_briefing.yml"
    }
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    print("Starting file upload to GitHub...")
    for repo_path, local_path in files_to_upload.items():
        actual_local_path = local_path
        if not os.path.exists(actual_local_path):
            # Try fallback by stripping leading directory if in GitHub Actions runner
            fallback_path = local_path
            if fallback_path.startswith("mma-news-briefing/"):
                fallback_path = fallback_path[len("mma-news-briefing/"):]
            
            if os.path.exists(fallback_path):
                actual_local_path = fallback_path
            else:
                print(f"[Warning] File not found locally: {local_path} (Fallback: {fallback_path})")
                continue
            
        with open(actual_local_path, "rb") as f:
            content_bytes = f.read()
        content_b64 = base64.b64encode(content_bytes).decode("utf-8")
        
        # Quote repo_path to support Korean characters in URLs
        quoted_path = urllib.parse.quote(repo_path)
        url = f"https://api.github.com/repos/{repo}/contents/{quoted_path}"
        
        # Check if file already exists to get SHA (for updates)
        r = requests.get(url, headers=headers, verify=False, timeout=10)
        sha = None
        if r.status_code == 200:
            sha = r.json().get("sha")
            
        payload = {
            "message": f"Upload {repo_path} via API",
            "content": content_b64,
        }
        if sha:
            payload["sha"] = sha
            
        r_put = requests.put(url, headers=headers, json=payload, verify=False, timeout=10)
        if r_put.status_code in [200, 201]:
            print(f"[Success] Uploaded: {repo_path}")
        else:
            print(f"[Error] Failed to upload {repo_path}: HTTP {r_put.status_code} - {r_put.text}")

if __name__ == "__main__":
    main()
