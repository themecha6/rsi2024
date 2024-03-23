import time
import datetime
import requests
import pandas as pd
import numpy as np
import pyupbit
import os
from dotenv import load_dotenv

# 현재 디렉토리의 .env 파일 로드
load_dotenv()

# 환경 변수 접근
access_key = os.getenv("ACCESS_KEY")
secret_key = os.getenv("SECRET_KEY")
slack_token = os.getenv("SLACK_TOKEN")

# 초기 설정값
bid_price = 5000
fee = 0.0005
period = 14
itv = "day"
remove_tickers = ["KRW-SSX", "KRW-PLA"]

def post_message(token, channel, text):
    """슬랙 메시지 전송"""
    response = requests.post("https://slack.com/api/chat.postMessage",
                             headers={"Authorization": "Bearer " + token},
                             data={"channel": channel, "text": text})
    
# 로그인 및 시작 메시지
upbit = pyupbit.Upbit(access_key, secret_key)
post_message(slack_token,"#aleart", "autotrade start")

def calculate_rsi(data_frame, period=14):
    delta = data_frame['close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# 시작 시간
def get_start_time(ticker):
    df = pyupbit.get_ohlcv(ticker, interval=itv, count = 1)
    start_time = df.index[0]
    return start_time

def get_balance(ticker):
    """특정 티커의 잔고 조회"""
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker:
            return float(b['balance']) if b['balance'] is not None else 0
    return 0

def get_current_price(ticker):
    """현재가 조회"""
    return pyupbit.get_orderbook(ticker=ticker)["orderbook_units"][0]["ask_price"]
    
def execute_buy_order(ticker, price, rsi_current, rsi_previous):
    """매수 주문 실행"""
    upbit.buy_market_order(ticker, price)
    post_message(slack_token, "#aleart", f"{ticker} 매수 완료")
    post_message(slack_token, "#aleart", f"가격 {price:.0f}원")
    post_message(slack_token, "#aleart", f"RSI: {rsi_current:.2f}, 직전 RSI: {rsi_previous:.2f}")


def execute_sell_order(ticker, amount, sell_price, rsi_current, rsi_previous, revenue, revenue_rate):
    """매도 주문 실행"""
    upbit.sell_market_order(ticker, amount)
    post_message(slack_token, "#aleart", f"{ticker} 매도 완료")
    post_message(slack_token, "#aleart", f"매도 가격 {sell_price:.0f}원")
    post_message(slack_token, "#aleart", f"RSI: {rsi_current:.2f}, 직전 RSI: {rsi_previous:.2f}")
    post_message(slack_token, "#aleart", f"손익 {revenue:.0f}원, {revenue_rate:.2f}%")

def trade_logic():
    try:
        now = datetime.datetime.now()
        start_time = get_start_time("KRW-BTC") + datetime.timedelta(seconds=10)  # 시작 시간 설정이 필요한 경우 추가 구현
        end_time = start_time + datetime.timedelta(minutes=1)  # 검색 종료 시간

        if start_time < now < end_time:
            KRW_tickers = [ticker for ticker in pyupbit.get_tickers(fiat="KRW") if ticker not in remove_tickers]

            for ticker in KRW_tickers:
                print(f"{ticker} 거래 조건 검색중...")

                balance = get_balance(ticker[ticker.index("-")+1:])
                df = pyupbit.get_ohlcv(ticker, interval=itv)
                df['RSI'] = calculate_rsi(df, period)

                rsi_current = df['RSI'].iloc[-2]
                rsi_previous = df['RSI'].iloc[-3]

                if rsi_previous <= 30 and rsi_current > rsi_previous:
                    execute_buy_order(ticker, bid_price, rsi_current, rsi_previous)

                elif rsi_previous >= 70 and rsi_current < 70:
                    current_price = get_current_price(ticker)
                    amount_to_sell = balance * current_price
                    if amount_to_sell >= 5000:  # 최소 거래 금액 확인
                        sell_price = current_price  # 이 예제에서는 현재 가격을 사용
                        revenue = (sell_price - bid_price) * balance  # 수익 계산, 실제 로직에 맞게 조정 필요
                        revenue_rate = (revenue / bid_price) * 100
                        execute_sell_order(ticker, balance, sell_price, rsi_current, rsi_previous, revenue, revenue_rate)

                time.sleep(1)  # API 요청 간격 조절

    except Exception as e:
        print(f"에러 발생: {e}")
        post_message(slack_token, "#alert", f"자동매매 중단: {e}")

def main():
    while True:
        try:
            print("자동매매 로직 실행중...")
            post_message(slack_token,"#aleart", "자동매매 로직 실행중")
            trade_logic()  # 앞서 정의된 자동매매 로직 함수 호출
            
            # 자동매매 로직 사이의 대기 시간 설정
            # Upbit API 요청 제한과 네트워크 상태 등을 고려하여 적절한 대기 시간 설정
            time.sleep(60)  # 예시: 60초마다 로직 반복 실행
            
        except KeyboardInterrupt:
            print("자동매매 로직 중단")
            break
        except Exception as e:
            # 예외 상황 발생시 슬랙으로 알림
            error_message = f"자동매매 로직 실행 중 예외 발생: {e}"
            print(error_message)
            post_message(slack_token, "#alert", error_message)
            # 예외 발생 후 재시도 전 대기 시간 설정
            time.sleep(60)  # 예시: 예외 발생시 60초 후 재시도

if __name__ == "__main__":
    main()
