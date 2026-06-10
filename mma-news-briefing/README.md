# 일일 병무청 뉴스 AI 브리핑 자동화 파이프라인 (PlayMCP 버전)

본 가이드는 매일 아침 병무청 관련 주요 뉴스를 PlayMCP의 네이버 검색 도구로 수집하고, AI로 요약하여 PlayMCP의 카카오톡 '나와의 채팅방' 도구로 자동 전송하는 파이프라인의 연동 매뉴얼입니다.

---

## 1. PlayMCP 도구 연동 및 초기 토큰 발급

PlayMCP를 사용하면 네이버 API 키 발급 및 카카오 개발자 앱의 복잡한 등록 과정이 필요 없습니다. 카카오 계정 로그인과 도구 추가만으로 연동이 완료됩니다.

### 1.1 PlayMCP 도구함 설정
1. [PlayMCP 공식 사이트](https://playmcp.kakao.com)에 로그인합니다.
2. **[도구함(Toolbox)]** 메뉴로 이동합니다.
3. 목록에서 아래 도구들을 내 도구함에 추가합니다:
   - **'나와의 채팅방'** (카카오톡 메시지 전송 기능)
   - **'네이버 검색 API'** (뉴스 및 트렌드 검색 기능)

### 1.2 One Time Token (OTT) 발급 및 액세스 토큰 교환
1. 도구함 페이지에서 **"OpenClaw와 연결"** 또는 **"연결 정보 생성"** 버튼을 클릭하여 일회용 토큰(One Time Token)을 발급받습니다.
2. 터미널(또는 Python 환경)을 열어 아래 Python 1줄 명령어를 실행합니다. `<ONE_TIME_TOKEN>` 부분을 발급받은 토큰 값으로 교환해 주세요.

```bash
C:\Users\ATEC\.local\bin\uv.exe run --with requests python -c "import requests, json; r = requests.post('https://playmcp.kakao.com/api/v1/auths/otts:exchange', json={'tokenValue': '<ONE_TIME_TOKEN>'}); print(json.dumps(r.json(), indent=2))"
```

**출력되는 결과 예시:**
```json
{
  "accessToken": {
    "tokenValue": "PLAYMCP_ACCESS_TOKEN_VALUE",
    "expiresAt": "2026-06-10T15:59:27Z"
  },
  "refreshToken": {
    "tokenValue": "PLAYMCP_REFRESH_TOKEN_VALUE",
    "expiresAt": "2026-09-08T03:59:27Z"
  }
}
```
여기서 반환된 `PLAYMCP_ACCESS_TOKEN_VALUE`와 `PLAYMCP_REFRESH_TOKEN_VALUE`를 기록해 둡니다.

---

## 2. GitHub Secrets 등록 항목

GitHub 레포지토리의 **Settings > Secrets and variables > Actions** 메뉴에서 다음 세 가지 시크릿을 등록합니다.

| 시크릿 이름 | 설명 | 필수 여부 |
| :--- | :--- | :--- |
| `PLAYMCP_ACCESS_TOKEN` | PlayMCP에서 교환한 `accessToken` 값 | **필수** |
| `PLAYMCP_REFRESH_TOKEN` | PlayMCP에서 교환한 `refreshToken` 값 | **필수** |
| `GEMINI_API_KEY` | Google AI Studio에서 발급받은 Gemini API 키 | **필수** |
| `GH_PAT` | 토큰 자동 갱신을 위해 Secrets 권한(`secrets:write`)이 포함된 GitHub Personal Access Token | **필수 (자동 갱신용)** |

---

## 3. GCP Cloud Scheduler 등록 및 트리거 설정 방법

매일 오전 07:00 KST에 GitHub Actions 워크플로우를 실행시키는 GCP Cloud Scheduler 설정 방법입니다.

1. [Google Cloud Console](https://console.cloud.google.com/)에 로그인합니다.
2. **Cloud Scheduler > 작업 만들기 (Create Job)**를 클릭합니다.
3. **작업 정의**:
   - **이름**: `daily-mma-news-trigger`
   - **빈도**: `0 7 * * *` (매일 오전 7시)
   - **시간대**: `한국 표준시 (KST)` 또는 `Asia/Seoul`
4. **실행 구성**:
   - **대상 유형**: `HTTP`
   - **URL**: `https://api.github.com/repos/{GitHub사용자명}/{저장소명}/dispatches`
     - 예: `https://api.github.com/repos/myusername/my-briefing-repo/dispatches`
   - **HTTP 메서드**: `POST`
   - **HTTP 헤더**:
     - `Accept`: `application/vnd.github.v3+json`
     - `User-Agent`: `Google-Cloud-Scheduler`
     - `Authorization`: `Bearer {GH_PAT_VALUE}` (발급받은 GitHub PAT 키)
   - **본문 (Body)**:
     ```json
     {
       "event_type": "daily-briefing"
     }
     ```
5. 생성을 완료하고 작업 목록에서 **강제 실행 (Force Run)**을 클릭해 동작을 최종 확인합니다.
