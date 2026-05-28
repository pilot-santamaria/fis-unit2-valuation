# 배포 절차

이 앱은 Streamlit 기반 Python 서버 앱입니다. 링크만 알면 접속 가능한 공개 사이트로 만들려면 GitHub 저장소에 올린 뒤 Render, Railway, Streamlit Community Cloud 같은 호스팅 서비스에 연결합니다.

## 비용 없는 권장 배포: Streamlit Community Cloud

가장 간단한 무료 배포 방식입니다. GitHub 저장소와 연결하면 `https://...streamlit.app` 형태의 공개 링크가 생성됩니다.

1. 이 폴더를 GitHub public 저장소로 업로드합니다.
2. Streamlit Community Cloud에 로그인합니다.
3. New app을 선택합니다.
4. Repository, Branch, Main file path를 지정합니다.
   - Main file path: `app.py`
5. Advanced settings에서 필요하면 아래 환경변수를 추가합니다.
   - `CHROME_BIN=/usr/bin/chromium`
   - `CHROMEDRIVER_PATH=/usr/bin/chromedriver`
6. Deploy를 누릅니다.

`requirements.txt`는 Python 패키지를 설치하고, `packages.txt`는 Chromium 관련 시스템 패키지를 설치하는 데 사용됩니다.

무료 서비스 특성상 리소스 제한이 있고, 사용자가 몰리면 느려질 수 있습니다. 동적 재무표 수집이 플랫폼 제한에 걸릴 경우 Docker 기반 배포로 전환하는 것이 좋습니다.

## 대안: Render Docker 배포

동적 재무표 수집에 Chromium/ChromeDriver가 필요하므로 Docker 배포가 가장 안정적입니다.

1. 이 폴더를 GitHub 저장소로 업로드합니다.
2. Render에서 New Web Service를 선택합니다.
3. GitHub 저장소를 연결합니다.
4. Runtime은 Docker를 선택합니다.
5. 별도 Build Command/Start Command는 비워둡니다. `Dockerfile`의 설정을 사용합니다.
6. 배포가 끝나면 `https://...onrender.com` 형태의 공개 링크가 생성됩니다.

무료 플랜은 정책 변경 가능성이 있고, 일정 시간 미사용 시 잠들 수 있어 첫 접속이 느릴 수 있습니다.

## 데이터 동작

- 기본값은 분석 버튼을 누를 때마다 새로 수집입니다.
- `.fis_cache`는 Docker 배포에는 포함하지 않습니다.
- 서버에서 새 수집이 실패하면 실행 중 생성된 캐시를 백업으로 사용할 수 있습니다.
- 공개 배포 전에는 데이터 원천 사이트의 이용 조건과 재배포 가능 범위를 확인해야 합니다.

## 로컬 Docker 테스트

Docker Desktop이 설치되어 있다면 다음 명령으로 로컬에서 배포 환경과 비슷하게 테스트할 수 있습니다.

```powershell
docker build -t fis-unit2 .
docker run --rm -p 8513:8501 fis-unit2
```

브라우저에서 엽니다.

```text
http://localhost:8513
```
