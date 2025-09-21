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
| `StrategyAgent` | 시세 변화율과 뉴스 감성 점수를 융합해 매수/매도 후보를 선정합니다. |
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
