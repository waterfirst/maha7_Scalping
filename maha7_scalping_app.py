import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import traceback

# 페이지 설정
st.set_page_config(
    page_title="마하세븐 스캘핑 전략 분석기",
    page_icon="📈",
    layout="wide"
)

# 앱 제목 및 소개
st.title("마하세븐 스캘핑 전략 분석기")
st.markdown("""
이 애플리케이션은 마하세븐의 스캘핑 전략을 기반으로 주식 분석을 제공합니다.
* **데이터 소스:** Yahoo Finance
* **주요 지표:** 20일, 50일, 100일 지수 이동 평균선(EMA)과 윌리엄스 프랙탈
* **매매 전략:** 정배열 상태에서 20일 EMA 돌파 매수, 50일 EMA 아래 손절, 손절 대비 1.5배 목표 수익
""")

# 사이드바 - 종목 검색 및 설정
st.sidebar.header("종목 설정")

# 종목 입력 방식 선택
input_method = st.sidebar.radio(
    "종목 입력 방식을 선택하세요:",
    ["직접 입력", "종목 검색"]
)

ticker = ""

if input_method == "직접 입력":
    ticker_input = st.sidebar.text_input("종목 티커 심볼을 입력하세요 (예: 005930.KS, AAPL):")
    # 따옴표 제거 및 공백 제거
    ticker = ticker_input.strip().replace('"', '').replace("'", "")
    
else:  # "종목 검색"
    market = st.sidebar.selectbox(
        "시장을 선택하세요:",
        ["한국", "미국"]
    )
    
    search_term = st.sidebar.text_input("종목명을 입력하세요:")
    
    if search_term:
        st.sidebar.info("종목 검색 중...")
        
        # 실제 구현에서는 API를 통해 종목 검색 결과를 가져와야 함
        # 여기서는 예시로 몇 가지 종목만 표시
        if market == "한국":
            search_results = {
                "삼성전자": "005930.KS",
                "SK하이닉스": "000660.KS",
                "NAVER": "035420.KS",
                "카카오": "035720.KS",
                "현대차": "005380.KS"
            }
        else:  # 미국
            search_results = {
                "Apple": "AAPL",
                "Microsoft": "MSFT",
                "Amazon": "AMZN",
                "Google": "GOOGL",
                "Tesla": "TSLA"
            }
        
        # 검색어를 포함하는 종목만 필터링
        filtered_results = {k: v for k, v in search_results.items() if search_term.lower() in k.lower()}
        
        if filtered_results:
            selected_stock = st.sidebar.selectbox(
                "검색 결과에서 종목을 선택하세요:",
                list(filtered_results.keys())
            )
            ticker = filtered_results.get(selected_stock, "")
        else:
            st.sidebar.warning("검색 결과가 없습니다. 다른 검색어를 입력해보세요.")

# 날짜 범위 설정
st.sidebar.header("기간 설정")
today = datetime.now()
start_date = st.sidebar.date_input(
    "시작일",
    today - timedelta(days=365)
)
end_date = st.sidebar.date_input(
    "종료일",
    today
)

# 기술적 지표 설정
st.sidebar.header("기술적 지표 설정")
ema_short = st.sidebar.number_input("단기 EMA 기간", min_value=5, max_value=50, value=20)
ema_medium = st.sidebar.number_input("중기 EMA 기간", min_value=20, max_value=100, value=50)
ema_long = st.sidebar.number_input("장기 EMA 기간", min_value=50, max_value=200, value=100)

# 안전한 불리언 변환 함수
def safe_bool(value):
    """판다스 시리즈의 불리언 값을 안전하게 변환"""
    if isinstance(value, bool):
        return value
    elif isinstance(value, (pd.Series, np.ndarray)):
        # 시리즈가 비어있거나 모든 값이 False인 경우
        if len(value) == 0 or not value.any():
            return False
        # 시리즈에 하나의 값만 있는 경우
        elif len(value) == 1:
            return bool(value.iloc[0])
        # 여러 값이 있는 경우 (이 경우는 오류가 발생해야 함)
        else:
            raise ValueError("Multiple boolean values found, cannot convert to single boolean")
    else:
        # 기타 타입은 파이썬 기본 bool 함수로 변환
        return bool(value)

# 안전한 float 변환 함수
def safe_float(value):
    """판다스 시리즈의 값을 안전하게 float로 변환"""
    if isinstance(value, (int, float)):
        return float(value)
    elif isinstance(value, pd.Series):
        if len(value) == 0:
            return 0.0
        return float(value.iloc[0])
    else:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

# 윌리엄스 프랙탈 함수 정의
def calculate_fractals(df):
    """윌리엄스 프랙탈 지표 계산"""
    try:
        # 데이터 유효성 검사
        if df is None or df.empty or len(df) < 5:
            return df
        
        # 새 컬럼 초기화
        df['Fractal_Buy'] = False
        df['Fractal_Sell'] = False
        
        # 매수 프랙탈 (상향 프랙탈)
        for i in range(2, len(df) - 2):
            high_i = safe_float(df['High'].iloc[i])
            high_i_minus_2 = safe_float(df['High'].iloc[i-2])
            high_i_minus_1 = safe_float(df['High'].iloc[i-1])
            high_i_plus_1 = safe_float(df['High'].iloc[i+1])
            high_i_plus_2 = safe_float(df['High'].iloc[i+2])
            
            if (high_i_minus_2 < high_i and 
                high_i_minus_1 < high_i and 
                high_i > high_i_plus_1 and 
                high_i > high_i_plus_2):
                df.loc[df.index[i], 'Fractal_Buy'] = True
        
        # 매도 프랙탈 (하향 프랙탈)
        for i in range(2, len(df) - 2):
            low_i = safe_float(df['Low'].iloc[i])
            low_i_minus_2 = safe_float(df['Low'].iloc[i-2])
            low_i_minus_1 = safe_float(df['Low'].iloc[i-1])
            low_i_plus_1 = safe_float(df['Low'].iloc[i+1])
            low_i_plus_2 = safe_float(df['Low'].iloc[i+2])
            
            if (low_i_minus_2 > low_i and 
                low_i_minus_1 > low_i and 
                low_i < low_i_plus_1 and 
                low_i < low_i_plus_2):
                df.loc[df.index[i], 'Fractal_Sell'] = True
        
        return df
    except Exception as e:
        st.error(f"프랙탈 계산 오류: {e}")
        st.error(traceback.format_exc())
        # 오류 발생 시 원본 데이터프레임 반환
        if 'Fractal_Buy' not in df.columns:
            df['Fractal_Buy'] = False
        if 'Fractal_Sell' not in df.columns:
            df['Fractal_Sell'] = False
        return df

# 매수/매도 신호 계산 함수
def calculate_signals(df, ema_short, ema_medium, ema_long):
    """마하세븐 전략 기반 매수/매도 신호 계산"""
    try:
        # 데이터 유효성 검사
        if df is None or df.empty or len(df) <= ema_long:
            return df
        
        # 새 컬럼 초기화
        df['Buy_Signal'] = False
        df['Sell_Signal'] = False
        df['Stop_Loss'] = np.nan
        df['Take_Profit'] = np.nan
        
        # 매수 신호 계산
        for i in range(1, len(df)):
            try:
                # 정배열 확인 (단기 > 중기 > 장기)
                ema_short_val = safe_float(df[f'EMA_{ema_short}'].iloc[i-1])
                ema_medium_val = safe_float(df[f'EMA_{ema_medium}'].iloc[i-1])
                ema_long_val = safe_float(df[f'EMA_{ema_long}'].iloc[i-1])
                
                is_aligned = (ema_short_val > ema_medium_val) and (ema_medium_val > ema_long_val)
                
                # 가격이 단기 EMA 아래로 하락했다가 다시 상향 돌파
                price_prev = safe_float(df['Close'].iloc[i-1])
                price_curr = safe_float(df['Close'].iloc[i])
                ema_short_prev = safe_float(df[f'EMA_{ema_short}'].iloc[i-1])
                ema_short_curr = safe_float(df[f'EMA_{ema_short}'].iloc[i])
                
                price_below_ema = price_prev < ema_short_prev
                price_above_ema = price_curr > ema_short_curr
                
                # 매수 프랙탈 발생 - 안전하게 불리언 값으로 변환
                fractal_buy = False
                if i < len(df) and 'Fractal_Buy' in df.columns:
                    fractal_buy = bool(df['Fractal_Buy'].iloc[i])
                
                # 모든 조건 충족 시 매수 신호
                if is_aligned and price_below_ema and price_above_ema and fractal_buy:
                    df.loc[df.index[i], 'Buy_Signal'] = True
                    
                    # 손절가 설정 (중기 EMA 바로 아래)
                    stop_loss = safe_float(df[f'EMA_{ema_medium}'].iloc[i]) * 0.99  # 약간의 여유 추가
                    
                    # 목표가 설정 (손절 대비 1.5배)
                    entry_price = safe_float(df['Close'].iloc[i])
                    risk = entry_price - stop_loss
                    take_profit = entry_price + (risk * 1.5)
                    
                    df.loc[df.index[i], 'Stop_Loss'] = stop_loss
                    df.loc[df.index[i], 'Take_Profit'] = take_profit
            except Exception as e:
                st.error(f"신호 계산 중 오류 (인덱스 {i}): {e}")
                continue
        
        return df
    except Exception as e:
        st.error(f"신호 계산 오류: {e}")
        st.error(traceback.format_exc())
        # 오류 발생 시 기본 컬럼 추가하고 원본 데이터프레임 반환
        if 'Buy_Signal' not in df.columns:
            df['Buy_Signal'] = False
        if 'Sell_Signal' not in df.columns:
            df['Sell_Signal'] = False
        if 'Stop_Loss' not in df.columns:
            df['Stop_Loss'] = np.nan
        if 'Take_Profit' not in df.columns:
            df['Take_Profit'] = np.nan
        return df

# 메인 함수 - 데이터 가져오기 및 분석
def analyze_stock(ticker, start_date, end_date, ema_short, ema_medium, ema_long):
    """주식 데이터 가져오기 및 분석"""
    if not ticker:
        return None
    
    try:
        # 데이터 가져오기
        data = yf.download(ticker, start=start_date, end=end_date)
        
        if data is None or data.empty:
            st.warning(f"{ticker}에 대한 데이터를 가져올 수 없습니다. 올바른 티커 심볼인지 확인하세요.")
            return None
        
        # 데이터 유효성 검사
        required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in required_columns:
            if col not in data.columns:
                st.warning(f"필수 컬럼 '{col}'이 데이터에 없습니다.")
                return None
        
        # EMA 계산
        try:
            data[f'EMA_{ema_short}'] = data['Close'].ewm(span=ema_short, adjust=False).mean()
            data[f'EMA_{ema_medium}'] = data['Close'].ewm(span=ema_medium, adjust=False).mean()
            data[f'EMA_{ema_long}'] = data['Close'].ewm(span=ema_long, adjust=False).mean()
        except Exception as e:
            st.error(f"EMA 계산 오류: {e}")
            return None
        
        # 윌리엄스 프랙탈 계산
        data = calculate_fractals(data)
        
        # 매수/매도 신호 계산
        data = calculate_signals(data, ema_short, ema_medium, ema_long)
        
        return data
    
    except Exception as e:
        st.error(f"데이터 가져오기 오류: {e}")
        st.error(traceback.format_exc())
        return None

# 차트 생성 함수
def create_chart(data, ticker, ema_short, ema_medium, ema_long):
    """Plotly를 사용한 차트 생성"""
    try:
        # 데이터 유효성 검사
        if data is None or data.empty:
            return None
        
        fig = go.Figure()
        
        # 캔들스틱 차트
        fig.add_trace(go.Candlestick(
            x=data.index,
            open=data['Open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close'],
            name='가격'
        ))
        
        # EMA 선 추가
        if f'EMA_{ema_short}' in data.columns:
            fig.add_trace(go.Scatter(
                x=data.index,
                y=data[f'EMA_{ema_short}'],
                mode='lines',
                name=f'{ema_short}일 EMA',
                line=dict(color='blue', width=1)
            ))
        
        if f'EMA_{ema_medium}' in data.columns:
            fig.add_trace(go.Scatter(
                x=data.index,
                y=data[f'EMA_{ema_medium}'],
                mode='lines',
                name=f'{ema_medium}일 EMA',
                line=dict(color='orange', width=1)
            ))
        
        if f'EMA_{ema_long}' in data.columns:
            fig.add_trace(go.Scatter(
                x=data.index,
                y=data[f'EMA_{ema_long}'],
                mode='lines',
                name=f'{ema_long}일 EMA',
                line=dict(color='purple', width=1)
            ))
        
        # 매수 신호 표시
        if 'Buy_Signal' in data.columns:
            buy_signals = data.loc[data['Buy_Signal'] == True]
            if not buy_signals.empty:
                fig.add_trace(go.Scatter(
                    x=buy_signals.index,
                    y=buy_signals['Low'] * 0.99,  # 약간 아래에 표시
                    mode='markers',
                    name='매수 신호',
                    marker=dict(
                        symbol='triangle-up',
                        size=10,
                        color='green',
                    )
                ))
        
        # 매수 프랙탈 표시
        if 'Fractal_Buy' in data.columns:
            buy_fractals = data.loc[data['Fractal_Buy'] == True]
            if not buy_fractals.empty:
                fig.add_trace(go.Scatter(
                    x=buy_fractals.index,
                    y=buy_fractals['High'] * 1.01,  # 약간 위에 표시
                    mode='markers',
                    name='매수 프랙탈',
                    marker=dict(
                        symbol='star',
                        size=8,
                        color='green',
                    )
                ))
        
        # 매도 프랙탈 표시
        if 'Fractal_Sell' in data.columns:
            sell_fractals = data.loc[data['Fractal_Sell'] == True]
            if not sell_fractals.empty:
                fig.add_trace(go.Scatter(
                    x=sell_fractals.index,
                    y=sell_fractals['Low'] * 0.99,  # 약간 아래에 표시
                    mode='markers',
                    name='매도 프랙탈',
                    marker=dict(
                        symbol='star',
                        size=8,
                        color='red',
                    )
                ))
        
        # 차트 레이아웃 설정
        fig.update_layout(
            title=f'{ticker} 마하세븐 스캘핑 전략 분석',
            xaxis_title='날짜',
            yaxis_title='가격',
            height=600,
            xaxis_rangeslider_visible=False
        )
        
        return fig
    except Exception as e:
        st.error(f"차트 생성 오류: {e}")
        st.error(traceback.format_exc())
        return None

# 백테스팅 결과 계산 함수
def calculate_backtest_results(data):
    """백테스팅 결과 계산"""
    try:
        # 데이터 유효성 검사
        if data is None or data.empty:
            return None
        
        if 'Buy_Signal' not in data.columns:
            return None
        
        results = {
            'total_signals': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
            'avg_profit': 0,
            'avg_loss': 0,
            'profit_factor': 0,
            'total_return': 0
        }
        
        # 불리언 인덱싱 대신 명시적 비교 사용
        buy_signals = data.loc[data['Buy_Signal'] == True].copy()
        
        if buy_signals.empty:
            return results
        
        results['total_signals'] = len(buy_signals)
        
        # 각 매수 신호에 대해 결과 계산
        for i, signal in buy_signals.iterrows():
            try:
                entry_price = safe_float(signal['Close'])
                
                # NaN 값 확인
                if pd.isna(signal['Stop_Loss']) or pd.isna(signal['Take_Profit']):
                    continue
                
                stop_loss = safe_float(signal['Stop_Loss'])
                take_profit = safe_float(signal['Take_Profit'])
                
                # 해당 신호 이후의 데이터
                future_data = data.loc[i:].iloc[1:]
                
                if future_data.empty:
                    continue
                
                # 손절 또는 목표가 도달 여부 확인
                reached_stop_loss = False
                reached_take_profit = False
                exit_price = entry_price
                
                for j, future_bar in future_data.iterrows():
                    # 손절가에 도달
                    if future_bar['Low'] <= stop_loss:
                        reached_stop_loss = True
                        exit_price = stop_loss
                        break
                    
                    # 목표가에 도달
                    if future_bar['High'] >= take_profit:
                        reached_take_profit = True
                        exit_price = take_profit
                        break
                
                # 승리/패배 기록
                if reached_take_profit:
                    results['wins'] += 1
                    profit_pct = (exit_price - entry_price) / entry_price * 100
                    results['avg_profit'] += profit_pct
                elif reached_stop_loss:
                    results['losses'] += 1
                    loss_pct = (exit_price - entry_price) / entry_price * 100
                    results['avg_l
(Content truncated due to size limit. Use line ranges to read in chunks)