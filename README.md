# FIS 1팀 Unit2

기업 재무제표, 컨센서스, 투자지표, 관련 뉴스를 수집하고 PER, PBR, EV/EBITDA, DCF 방식으로 목표주가를 계산하는 Streamlit 리서치 터미널입니다.

## 로컬 실행

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8513 --server.headless true --browser.gatherUsageStats false
```

브라우저에서 엽니다.

```text
http://localhost:8513
```

## 주요 기능

- 기업 요약, 현재가, 목표주가, 고평가/저평가 판단
- 과거 실적, 컨센서스, 투자지표 표 수집
- PER, PBR, EV/EBITDA, DCF 비중 직접 입력
- DCF, WACC/CAPM, 민감도 분석
- 경쟁사 비교분석
- 관련 뉴스 탭
- 기업명/종목코드 검색

## 배포

공개 링크로 배포하는 절차는 [DEPLOY.md](DEPLOY.md)를 참고하세요. Docker 기반 Render 배포를 권장합니다.
