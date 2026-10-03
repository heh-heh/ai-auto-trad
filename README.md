# AI Auto Trader — Toss Securities

개인용 토스증권 Open API 기반 **실계좌 자동매매 플랫폼**입니다.

## 구조

- `frontend/` — GitHub Pages 실거래 관제 대시보드
- `termux_server/` — Android Termux의 실제 주문 실행 서버
- Cloudflare Tunnel — GitHub Pages ↔ 휴대폰 서버 HTTPS 연결
- Toss Securities Open API — 시세·계좌·주문·주문상태

> GitHub Pages에는 API Secret을 두지 않습니다. 실제 주문은 Termux에서만 실행됩니다.

## 실거래 안전장치

- `TRADING_MODE=live` 필요
- `LIVE_TRADING_ENABLED=true` 필요
- 별도 `LIVE_ARM_PHRASE` 입력으로 ARM
- ARM과 자동매매 ON을 분리
- 주문 직전 계좌 평가금액/일일 손실 재확인
- 주문 직전 매수 가능금액 또는 매도 가능수량 재확인
- `MAX_ORDER_KRW` 주문금액 상한
- `MAX_DAILY_LOSS_KRW` 일일 손실 한도
- 시장가/지정가 주문 지원
- 미체결 주문 조회·정정·취소 지원
- 실제 주문 제출 전 프런트 확인 + 서버 확인 이중 게이트

Toss Open API는 계좌 조회, 주문 생성·정정·취소, 매수 가능금액·매도 가능수량 조회를 제공합니다. 계좌/주문 계열에는 `X-Tossinvest-Account` 헤더가 필요합니다. citeturn0search0

## 환경변수

```env
TOSS_CLIENT_ID=
TOSS_CLIENT_SECRET=
TOSS_ACCOUNT_SEQ=
TRADING_MODE=live
LIVE_TRADING_ENABLED=false
LIVE_ARM_PHRASE=
CONTROL_TOKEN=
ALLOWED_ORIGINS=https://heh-heh.github.io,http://localhost:8000,http://127.0.0.1:8000
MAX_ORDER_KRW=100000
MAX_DAILY_LOSS_KRW=50000
```

`TOSS_CLIENT_ID`, `TOSS_CLIENT_SECRET`, `CONTROL_TOKEN`, `LIVE_ARM_PHRASE`는 저장소에 커밋하지 않습니다.

## Termux

최초 1회:

```bash
git clone https://github.com/heh-heh/ai-auto-trad.git
cd ai-auto-trad
bash termux_setup.sh
```

기존 설치라면:

```bash
cd ~/ai-auto-trad
git pull origin main
```

서버 실행:

```bash
bash termux_background.sh
```

로그:

```bash
tail -f logs/server.log
```

중지:

```bash
bash termux_stop.sh
```

상태 확인:

```bash
curl http://127.0.0.1:8000/health
```

## GitHub Pages 연결

휴대폰 서버는 Cloudflare Tunnel을 통해 HTTPS로 노출합니다.

```bash
bash termux_tunnel_background.sh
```

로그:

```bash
tail -f logs/tunnel.log
```

Quick Tunnel은 재시작할 때 주소가 바뀔 수 있습니다. 주소가 바뀌면 GitHub Pages의 **서버 연결 → API 서버 주소**를 새 주소로 변경합니다.

관제 토큰:

```bash
cat termux_server/.control_token
```

## 대시보드

- Toss 실시간 현재가/캔들/호가
- 계좌 평가금액
- 매수 가능금액
- 보유종목
- 미체결 주문
- 실거래 시장가/지정가 매수·매도
- 주문 정정/취소
- SMA5/SMA20/RSI14 전략 신호
- 실거래 자동매매 ON/OFF
- 일일 손실 제한 및 주문금액 제한

실시간 주문 이벤트는 Toss WebSocket의 `personal:order`로 받을 수 있으며, 연결이 끊긴 경우 REST 주문 목록으로 재동기화해야 합니다. 현재 구현은 REST 기반 주문 동기화를 사용합니다. citeturn0search2

## 주의

실거래 주문은 실제 계좌에 영향을 줍니다. 소프트웨어가 주문을 전송할 수 있어도 수익이나 손실을 보장하지 않습니다.
