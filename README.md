# Multi-agent Crypto Management

한국어 사용자를 위해 설계된 멀티 에이전트 기반의 가상자산 자동 운용 샘플 프로젝트입니다. 본 예시는 빗썸(Bithumb) 거래소의 공개 시세와 외부 뉴스 데이터를 결합하고, LLM 기반 감성 분석을 통해 투자 결정을 생성하는 **시뮬레이션** 파이프라인을 제공합니다. 실제 매매 API를 호출하지 않으며, 투자 판단 참고용 구조를 빠르게 실험해 볼 수 있도록 구성했습니다.

> ⚠️ **중요 고지**: 본 저장소의 코드는 연구/실험용이며, 실거래에 바로 사용해서는 안 됩니다. 암호화폐 투자는 높은 손실 위험을 동반합니다. 항상 자신의 책임 하에 판단하시고, 필요한 경우 전문가와 상담하십시오.

## 주요 구성 요소

프로젝트는 다음과 같은 에이전트로 구성됩니다.

| 에이전트 | 역할 |
|----------|------|
| `MarketDataAgent` | 빗썸 공개 REST API에서 코인별 시세 정보를 수집합니다. |
| `NewsAgent` | 코인데스크, 코인텔레그래프, 구글 뉴스 RSS를 조회하여 관련 뉴스를 수집하고, 추적 중인 심볼을 자동 감지합니다. |
| `SentimentAgent` | LLM(기본은 규칙 기반 모델)으로 뉴스 별 감성 점수를 산출합니다. |
| `StrategyAgent` | 감성·시세 데이터를 결합하고 전문가용 전략(돌파, 변동성, 거래량 필터)을 적용해 매수/매도 후보를 선정합니다. |
| `PortfolioAgent` | 전략 에이전트가 생성한 의사결정을 바탕으로 가상의 KRW 포트폴리오를 업데이트합니다. |

모든 에이전트는 `AgentOrchestrator`를 통해 순차적으로 실행되며, 공유 상태(`AgentState`)를 주고받습니다.

## 빠른 시작

1. **의존성 설치**

   ```bash
   pip install -e .[dev]
   ```

2. **시뮬레이션 실행**

   기본 설정(추적 심볼: BTC, ETH, XRP, ADA, SOL)으로 한 번 실행하려면 다음 명령을 사용합니다.

   ```bash
   python -m multi_agent_crypto.main --cycles 1 --log-level INFO
   ```

   주요 옵션

   - `--cycles`: 에이전트 파이프라인 반복 실행 횟수
   - `--delay`: 반복 사이 대기 시간(초)
   - `--symbols`: 감시할 심볼 재정의 (예: `--symbols BTC ETH XRP`)

3. **테스트 실행**

   ```bash
   pytest
   ```

## OpenAI GPT-5 감성 분석 연동

규칙 기반 LLM 대신 OpenAI GPT-5 모델을 사용해 뉴스 감성 분석을 수행할 수 있습니다. `OPENAI_API_KEY` 환경 변수가 필요하며, 다음 절차를 따르면 됩니다.

1. **의존성 설치**

   ```bash
   pip install -e .[llm]
   ```

2. **API 키 설정**

   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

3. **GPT-5 기반 시뮬레이션 실행**

   ```bash
   python -m multi_agent_crypto.main --llm-provider openai --cycles 1 --openai-model gpt-5.0-mini
   ```

   `--openai-temperature` 옵션으로 샘플링 온도를 조절하거나, `--openai-api-key` 인자를 통해 환경 변수 대신 직접 키를 전달할 수 있습니다.

## 모니터링 대시보드 실행

FastAPI 기반의 경량 서버와 정적 프론트엔드가 결합된 모니터링 대시보드에서 시장 데이터와 에이전트 결괏값을 실시간으로 살펴볼 수 있습니다. 기본 설정은 1분 주기로 상태를 새로고침하며, 추적 심볼이나 주기를 옵션으로 변경할 수 있습니다.

1. 의존성 설치

   ```bash
   pip install -e .[monitoring]
   ```

2. 대시보드 서버 실행

   ```bash
   python -m multi_agent_crypto.monitoring --host 0.0.0.0 --port 8000 --refresh-interval 120
   ```

   `--symbols BTC ETH XRP`와 같이 인자를 추가하면 감시할 자산을 재정의할 수 있습니다.

3. 브라우저에서 `http://localhost:8000`으로 접속하면 다음 정보를 확인할 수 있습니다.

   - 추적 중인 코인별 시세, 변동률, 거래량
   - 포트폴리오 총자산, 잔고, 포지션, 체결 내역
   - 전략 에이전트가 생성한 매수/매도 의사결정과 신뢰도
   - 뉴스·감성 분석 결과와 관련 심볼


## 전문가용 전략 모드

`StrategyAgent`는 기본값으로 전문가용 트레이딩 전략 모드를 사용합니다. 이 모드는 다음과 같은 시그널을 조합하여 매수/매도 결정을 내립니다.

- **돌파·붕괴 감지**: 24시간 고가/저가 대비 현재 가격을 비교해 돌파(breakout) 또는 붕괴(breakdown) 여부를 판단합니다.
- **모멘텀 및 감성 융합**: LLM 감성 점수와 24시간 수익률을 가중 평균해 추세 강도를 평가합니다.
- **거래량 필터**: 24시간 거래량이 임계값을 밑돌면 신호 신뢰도를 낮춥니다.
- **변동성 제어**: 고가·저가 범위를 활용한 간이 ATR 지표로 과도한 변동성을 감지하고 보수적으로 대응합니다.
- **평균회귀 판단**: 가격이 24시간 중앙값 대비 과도하게 벗어났는지 살펴 과매수/과매도 신호를 보정합니다.

필요하다면 `StrategyAgent(strategy_mode="basic")`로 기존 단순 임계값 기반 로직을 사용할 수 있으며, `volume_threshold`, `volatility_threshold` 등 생성자 인자로 전문가 모드의 민감도를 조정할 수 있습니다.

## 시스템 확장 방법

- **실제 LLM 연동**: `multi_agent_crypto/llm/base.py`의 `LLMClient` 인터페이스를 구현하여 OpenAI, Azure OpenAI, Anthropic 등 원하는 모델과 통합할 수 있습니다.
- **뉴스 소스 추가**: `config.default_news_sources()`에 `NewsSource`를 추가하거나, 실행 시 구성 객체를 수정하면 됩니다.
- **실거래 연동**: `PortfolioAgent` 대신 실시간 주문 실행 로직을 작성할 수 있도록 구조를 모듈화했습니다. 단, API 키 관리와 리스크 제어를 반드시 선행하세요.

## 프로젝트 구조

```
multi_agent_crypto/
├─ agents/                # 각 기능별 에이전트 구현
├─ exchanges/             # 거래소 API 클라이언트 (Bithumb)
├─ llm/                   # LLM 클라이언트 추상화 및 규칙 기반 구현
├─ orchestrator.py        # 에이전트 실행 관리자
├─ config.py              # 기본 시스템 설정 및 에이전트 생성 헬퍼
└─ main.py                # CLI 진입점
```

## 라이선스

이 프로젝트는 [MIT License](LICENSE.md)를 따릅니다.
