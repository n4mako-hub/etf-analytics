import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import os
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh

# 1. Configurazione Pagina e Styling CSS (Minimal & Monochromatic + Animazione Puntini)
st.set_page_config(page_title="ETF Analytics & Portfolio Tracker", layout="wide")

count = st_autorefresh(interval=15 * 60 * 1000, key="datarefresh")

st.markdown("""
    <style>
    html, body, [class*="css"]  { font-size: 13px !important; }
    h1 { font-size: 1.25rem !important; font-weight: 600 !important; color: #1E293B; margin-bottom: 0.2rem; }
    h2, h3 { font-size: 0.95rem !important; font-weight: 600 !important; color: #475569; margin-top: 0.8rem; margin-bottom: 0.3rem; }
    .block-container { padding-top: 1.2rem !important; padding-bottom: 1.2rem !important; padding-left: 1rem !important; padding-right: 1rem !important; }
    div[data-testid="stSidebarUserContent"] { padding-top: 1rem !important; }
    .stDataFrame { border: 1px solid #E2E8F0; border-radius: 4px; }
    section[data-testid="stSidebar"] { background-color: #F8FAFC; border-right: 1px solid #E2E8F0; }
    
    div[data-testid="stPopover"] > button {
        border: none !important;
        background: transparent !important;
        padding: 0px 8px !important;
        color: #64748B !important;
    }
    div[data-testid="stPopover"] > button:hover {
        color: #2563EB !important;
    }

    /* Animazione puntini saltellanti al centro */
    .loader-container {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 60vh;
        width: 100%;
    }
    .dot-flashing {
        position: relative;
        width: 10px;
        height: 10px;
        border-radius: 5px;
        background-color: #2563EB;
        color: #2563EB;
        animation: dot-flashing 1s infinite linear alternate;
        animation-delay: 0.5s;
    }
    .dot-flashing::before, .dot-flashing::after {
        content: "";
        display: inline-block;
        position: absolute;
        top: 0;
    }
    .dot-flashing::before {
        left: -15px;
        width: 10px;
        height: 10px;
        border-radius: 5px;
        background-color: #2563EB;
        color: #2563EB;
        animation: dot-flashing 1s infinite linear alternate;
        animation-delay: 0s;
    }
    .dot-flashing::after {
        left: 15px;
        width: 10px;
        height: 10px;
        border-radius: 5px;
        background-color: #2563EB;
        color: #2563EB;
        animation: dot-flashing 1s infinite linear alternate;
        animation-delay: 1s;
    }
    @keyframes dot-flashing {
        0% { background-color: #2563EB; }
        50%, 100% { background-color: rgba(37, 99, 235, 0.2); }
    }

    @media (max-width: 768px) {
        .block-container {
            padding-top: 0.8rem !important;
            padding-bottom: 0.8rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        h1 { font-size: 1.1rem !important; }
        h2, h3 { font-size: 0.85rem !important; }
        .stButton button { width: 100% !important; }
    }
    </style>
""", unsafe_allow_html=True)

st.title("ETF Performance Analytics")

WATCHLIST_FILE = "watchlist.json"
SETTINGS_FILE = "settings.json"

DEFAULT_WATCHLIST = {
    "VWCE.DE": {"name": "Vanguard FTSE All-World UCITS ETF", "isin": "IE00BK5BQT36", "active": True, "ter": 0.22, "invested_amount": 0.0, "buy_price": 0.0, "buy_date": ""},
    "SWDA.MI": {"name": "iShares Core MSCI World UCITS ETF", "isin": "IE00B4L5Y983", "active": False, "ter": 0.20, "invested_amount": 0.0, "buy_price": 0.0, "buy_date": ""},
    "XEON.DE": {"name": "Xtrackers EUR Overnight Rate Swap UCITS ETF", "isin": "LU0290358497", "active": False, "ter": 0.10, "invested_amount": 0.0, "buy_price": 0.0, "buy_date": ""}
}

all_tab1_cols = [
    "Strumento", "Categoria", "ISIN", "Data Emissione", "JustETF", "Attivo", "TER (%)", 
    "Investito (€)", "Prezzo Carico (€)", "Data Acquisto", "Valore Attuale (€)", 
    "Profitto/Perdita (€)", "Profitto/Perdita (%)", "Ultimo (€)", "YTD (%)", 
    "1 Anno (%)", "Volatilità 1A", "Sharpe 1A", "Sortino 1A", "SMA200", "RSI (14)"
]
default_tab1_cols = [
    "Strumento", "Attivo", "Data Emissione", "TER (%)", "Investito (€)", "Prezzo Carico (€)", "Data Acquisto", 
    "Valore Attuale (€)", "Profitto/Perdita (€)", "Profitto/Perdita (%)", 
    "Ultimo (€)", "1 Anno (%)", "SMA200"
]

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k in data:
                    if "ter" not in data[k]: data[k]["ter"] = 0.0
                    if "active" not in data[k]: data[k]["active"] = True
                    if "invested_amount" not in data[k]: data[k]["invested_amount"] = 0.0
                    if "buy_price" not in data[k]: data[k]["buy_price"] = 0.0
                    if "buy_date" not in data[k]: data[k]["buy_date"] = ""
                return data
        except Exception:
            return DEFAULT_WATCHLIST.copy()
    return DEFAULT_WATCHLIST.copy()

def save_watchlist(watchlist):
    try:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"Errore nel salvataggio watchlist: {e}")

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "selected_tab1_cols" in data:
                    return data
        except Exception:
            pass
    return {"selected_tab1_cols": default_tab1_cols.copy()}

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"Errore nel salvataggio impostazioni: {e}")

if "watchlist" not in st.session_state:
    st.session_state.watchlist = load_watchlist()

if "focus_ticker" not in st.session_state:
    st.session_state.focus_ticker = None

if "selected_tab1_cols" not in st.session_state:
    saved_settings = load_settings()
    st.session_state.selected_tab1_cols = saved_settings.get("selected_tab1_cols", default_tab1_cols.copy())

if "chart_type_radio" not in st.session_state:
    st.session_state.chart_type_radio = "Linee (Normalizzato)"

def detect_category(name, info):
    name_upper = name.upper()
    cat_raw = str(info.get('category', '')).upper()
    
    if any(k in name_upper for k in ['GOLD', 'SILVER', 'PHYSICAL', 'COMMODITY', 'COMMODITIES', 'OIL', 'COPPER', 'METALS', 'ETC']):
        return "Materie Prime / Metalli"
    if any(k in name_upper for k in ['OVERNIGHT', 'RATE', 'CASH', 'MONEY', 'TREASURY', 'BOND', 'BONDS', 'AGGREGATE', 'GOVT', 'CORPORATE', 'INFLATION']):
        if any(k in name_upper for k in ['OVERNIGHT', 'CASH', 'XEON', 'MONEY', 'RATE']):
            return "Monetario / Liquidità"
        return "Obbligazionario"
    if any(k in name_upper for k in ['WORLD', 'ALL-WORLD', 'MSCI WORLD', 'ACWI', 'GLOBAL']):
        return "Azionario Globale"
    if any(k in name_upper for k in ['S&P 500', 'NASDAQ', 'USA', 'AMERICA', 'US ']):
        return "Azionario USA"
    if any(k in name_upper for k in ['EUROPE', 'EURO', 'STOXX', 'DAX', 'FTSE MIB']):
        return "Azionario Europa"
    if any(k in name_upper for k in ['EMERGING', 'EM ', 'ASIA', 'CHINA', 'INDIA']):
        return "Azionario Mercati Emergenti"
    if any(k in name_upper for k in ['EQUITY', 'STOCK', 'MSCI', 'FTSE', 'SECTOR', 'SEMICONDUCTOR', 'TECH', 'CLEAN ENERGY', 'ARTIFICIAL', 'ROBOTICS', 'AI']):
        return "Azionario Settoriale"
        
    if "EQUITY" in cat_raw:
        return "Azionario"
    elif "BOND" in cat_raw or "FIXED" in cat_raw:
        return "Obbligazionario"
        
    return "Generico / Altro"

def get_info_from_isin(isin):
    forced_tickers = {
        "IE00BGV5VN51": "XAIX.MI",
        "IE00BK5BQT36": "VWCE.DE",
        "IE00B4L5Y983": "SWDA.MI",
        "LU0290358497": "XEON.DE"
    }
    
    if isin in forced_tickers:
        ticker = forced_tickers[isin]
        try:
            tk_obj = yf.Ticker(ticker)
            info = tk_obj.info
            name = info.get("longName") or info.get("shortName") or ticker
            return ticker, name
        except Exception:
            return ticker, ticker

    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={isin}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if "quotes" in data and len(data["quotes"]) > 0:
            best_match = data["quotes"][0]
            ticker = best_match.get("symbol")
            name = best_match.get("longname") or best_match.get("shortname") or ticker
            return ticker, name
    except Exception:
        pass
    return f"{isin}.MI", isin

# --- BARRA LATERALE ---
st.sidebar.markdown("### Gestione Watchlist")

with st.sidebar.expander("+ Aggiungi Strumento", expanded=False):
    with st.form(key="add_isin_form", clear_on_submit=True):
        isin_input = st.text_input("Codice ISIN o Ticker", placeholder="es. IE00B4L5Y983")
        submit_button = st.form_submit_button(label="Aggiungi")

    if submit_button:
        clean_input = isin_input.strip().upper()
        if clean_input:
            with st.spinner("Ricerca..."):
                ticker, long_name = get_info_from_isin(clean_input)
                if ticker:
                    st.session_state.watchlist[ticker] = {
                        "name": long_name, 
                        "isin": clean_input, 
                        "active": True,
                        "ter": 0.0,
                        "invested_amount": 0.0,
                        "buy_price": 0.0,
                        "buy_date": ""
                    }
                    save_watchlist(st.session_state.watchlist)
                    st.sidebar.success("Aggiunto e salvato")
                    st.rerun()
                else:
                    st.sidebar.error("Strumento non trovato.")

st.sidebar.markdown("---")

st.sidebar.markdown("### Portafoglio Personale")
portfolio_items = [(tk, inf) for tk, inf in st.session_state.watchlist.items() if inf.get("invested_amount", 0.0) > 0 and inf.get("buy_price", 0.0) > 0]

if portfolio_items:
    total_inv_sidebar = sum(inf["invested_amount"] for tk, inf in portfolio_items)
    st.sidebar.markdown(f"**Totale Investito:** `{total_inv_sidebar:,.2f} €`")
    
    if st.session_state.focus_ticker:
        focus_name = st.session_state.watchlist.get(st.session_state.focus_ticker, {}).get("name", st.session_state.focus_ticker)
        if st.sidebar.button(f"🔍 Focalizzato: {focus_name[:12]}... [Reset]", use_container_width=True):
            st.session_state.focus_ticker = None
            st.rerun()

    st.sidebar.markdown("")
    
    portfolio_state_changed = False
    for tk, inf in portfolio_items:
        cols = st.sidebar.columns([0.15, 0.85])
        is_active = cols[0].checkbox("", value=inf["active"], key=f"port_chk_{tk}")
        if is_active != inf["active"]:
            st.session_state.watchlist[tk]["active"] = is_active
            portfolio_state_changed = True
            
        if cols[1].button(inf['name'], key=f"focus_btn_{tk}", use_container_width=True):
            if st.session_state.focus_ticker == tk:
                st.session_state.focus_ticker = None
            else:
                st.session_state.focus_ticker = tk
            st.rerun()
            
        date_str = f" ({inf['buy_date']})" if inf.get('buy_date') else ""
        st.sidebar.markdown(f"<small style='color: #475569; margin-left: 25px;'>Inv: **{inf['invested_amount']:,.2f}€** | Carico: **{inf['buy_price']}€**{date_str}</small>", unsafe_allow_html=True)
        st.sidebar.markdown("")

    if portfolio_state_changed:
        save_watchlist(st.session_state.watchlist)
        st.rerun()
else:
    st.sidebar.info("Nessun ETF con dati di acquisto inseriti.")

st.sidebar.markdown("---")
st.sidebar.markdown("### Lista ETF e Selezione")
search_query = st.sidebar.text_input("Filtra rapido:", placeholder="cerca nome o ISIN...")

col_b1, col_b2, col_b3 = st.sidebar.columns(3)

if col_b1.button("Tutti", use_container_width=True):
    for tk in st.session_state.watchlist:
        st.session_state.watchlist[tk]["active"] = True
        if f"chk_{tk}" in st.session_state:
            st.session_state[f"chk_{tk}"] = True
    save_watchlist(st.session_state.watchlist)
    st.rerun()

if col_b2.button("Nessun", use_container_width=True):
    for tk in st.session_state.watchlist:
        st.session_state.watchlist[tk]["active"] = False
        if f"chk_{tk}" in st.session_state:
            st.session_state[f"chk_{tk}"] = False
    save_watchlist(st.session_state.watchlist)
    st.rerun()

if col_b3.button("Top 5", use_container_width=True):
    performance_scores = {}
    for tk in st.session_state.watchlist:
        try:
            tk_obj = yf.Ticker(tk)
            data = tk_obj.history(period="max")['Close'].dropna()
            if len(data) > 0:
                performance_scores[tk] = ((data.iloc[-1] - data.iloc[0]) / data.iloc[0]) * 100
        except Exception:
            pass
    sorted_top = sorted(performance_scores.items(), key=lambda x: x[1], reverse=True)
    top_5_tickers = [item[0] for item in sorted_top[:5]]
    for tk in st.session_state.watchlist:
        is_top5 = (tk in top_5_tickers)
        st.session_state.watchlist[tk]["active"] = is_top5
        if f"chk_{tk}" in st.session_state:
            st.session_state[f"chk_{tk}"] = is_top5
    save_watchlist(st.session_state.watchlist)
    st.rerun()

st.sidebar.markdown("")

grouped_watchlist = {}
for ticker, info in st.session_state.watchlist.items():
    name = info["name"]
    isin = info.get("isin", "")
    if search_query.strip():
        q = search_query.strip().upper()
        if not (q in ticker.upper() or q in name.upper() or q in isin.upper()):
            continue
    cat = detect_category(name, {})
    if cat not in grouped_watchlist:
        grouped_watchlist[cat] = []
    grouped_watchlist[cat].append((ticker, info))

state_changed = False
if not grouped_watchlist:
    st.sidebar.info("Nessun ETF trovato.")
else:
    for cat, items in sorted(grouped_watchlist.items()):
        active_count_in_cat = sum(1 for tk, inf in items if inf["active"])
        cat_label = f"{cat} ({active_count_in_cat}/{len(items)})"
        with st.sidebar.expander(cat_label, expanded=(len(grouped_watchlist) == 1 or search_query.strip() != "")):
            for tk, info in items:
                current_status = info["active"]
                col_item_chk, col_item_del = st.columns([0.82, 0.18])
                new_status = col_item_chk.checkbox(f"{info['name']} ({tk})", value=current_status, key=f"chk_{tk}")
                if new_status != current_status:
                    st.session_state.watchlist[tk]["active"] = new_status
                    state_changed = True
                if col_item_del.button("[-] ", key=f"del_btn_{tk}", help="Elimina"):
                    del st.session_state.watchlist[tk]
                    save_watchlist(st.session_state.watchlist)
                    st.rerun()

if state_changed:
    save_watchlist(st.session_state.watchlist)
    st.rerun()

all_tab2_cols = ["Strumento", "Rendimento", "Crollo Max", "Miglior Anno Solare", "Peggior Anno Solare", "Peggior Crollo Storico"]

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty else 50.0

def calculate_rsi_series(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_sortino(series, target_return=0.0):
    daily_returns = series.pct_change().dropna()
    if len(daily_returns) < 2: return 0.0
    downside_returns = daily_returns[daily_returns < target_return]
    downside_deviation = np.sqrt(np.mean(downside_returns**2)) * np.sqrt(252) if len(downside_returns) > 0 else 0.0
    price_1y = series.iloc[-252] if len(series) >= 252 else series.iloc[0]
    ret_1y = ((series.iloc[-1] - price_1y) / price_1y) * 100
    return (ret_1y / (downside_deviation * 100)) if downside_deviation > 0 else 0.0

def parse_custom_date(date_str):
    if not date_str or str(date_str).strip() == "":
        return pd.NaT
    s = str(date_str).strip()
    parts = s.replace('/', '.').replace('-', '.').split('.')
    if len(parts) == 3 and len(parts[2]) == 2:
        parts[2] = '20' + parts[2]
        s = f"{parts[0]}.{parts[1]}.{parts[2]}"
    return pd.to_datetime(s, errors='coerce', dayfirst=True)

def get_etf_data(tickers_list):
    metrics_list = []
    historical_prices = pd.DataFrame()
    historical_ohlc = {}

    all_tickers_to_fetch = list(st.session_state.watchlist.keys())

    for ticker in all_tickers_to_fetch:
        info_dict = st.session_state.watchlist.get(ticker, {})
        name = info_dict.get("name", ticker)
        isin_val = info_dict.get("isin", ticker.split(".")[0])
        ter_val = info_dict.get("ter", 0.0)
        is_active = info_dict.get("active", True)
        inv_amt = info_dict.get("invested_amount", 0.0)
        buy_pr = info_dict.get("buy_price", 0.0)
        buy_dt = info_dict.get("buy_date", "")
        
        justetf_url = f"https://www.justetf.com/it/etf-profile.html?isin={isin_val}"
        
        try:
            tk_obj = yf.Ticker(ticker)
            df_hist = tk_obj.history(period="max")
            if not df_hist.empty and 'Close' in df_hist.columns:
                data = df_hist['Close']
                if not isinstance(data.index, pd.DatetimeIndex): data.index = pd.to_datetime(data.index)
                data = data.tz_localize(None)

                inception_date_str = data.index[0].strftime("%d/%m/%Y") if not data.empty else "N/D"

                historical_ohlc[name] = df_hist.copy()
                if not isinstance(historical_ohlc[name].index, pd.DatetimeIndex): 
                    historical_ohlc[name].index = pd.to_datetime(historical_ohlc[name].index)
                historical_ohlc[name] = historical_ohlc[name].tz_localize(None)

                info = tk_obj.info
                category = detect_category(name, info)

                historical_prices[name] = data
                latest_price = data.iloc[-1]
                
                price_1y = data.iloc[-252] if len(data) >= 252 else data.iloc[0]
                ret_1y = ((latest_price - price_1y) / price_1y) * 100
                
                current_year = datetime.now().year
                ytd_data = data[data.index.year == current_year]
                ret_ytd = ((latest_price - ytd_data.iloc[0]) / ytd_data.iloc[0]) * 100 if not ytd_data.empty else 0.0

                daily_returns = data.pct_change().dropna()
                volatility_1y = daily_returns.iloc[-252:].std() * np.sqrt(252) * 100 if len(daily_returns) >= 252 else daily_returns.std() * np.sqrt(252) * 100
                
                sharpe_1y = (ret_1y / volatility_1y) if volatility_1y > 0 else 0.0
                sortino_1y = calculate_sortino(data)
                sma_200 = data.iloc[-200:].mean() if len(data) >= 200 else None
                
                sma_val = "🟩" if sma_200 and latest_price >= sma_200 else ("🟥" if sma_200 else "N/D")
                rsi_val = calculate_rsi(data, 14)

                current_val_eur = 0.0
                pnl_eur = 0.0
                pnl_pct = 0.0
                if inv_amt > 0 and buy_pr > 0:
                    shares = inv_amt / buy_pr
                    current_val_eur = shares * latest_price
                    pnl_eur = current_val_eur - inv_amt
                    pnl_pct = (pnl_eur / inv_amt) * 100

                def fmt_pct(val):
                    return f"{val:+.2f}%" if isinstance(val, (int, float)) else "N/D"

                if inv_amt > 0 and buy_pr > 0:
                    pnl_eur_str = f"+{pnl_eur:.2f} €" if pnl_eur > 0 else (f"{pnl_eur:.2f} €" if pnl_eur < 0 else f"{pnl_eur:.2f} €")
                    pnl_pct_str = f"+{pnl_pct:.2f}%" if pnl_pct > 0 else (f"{pnl_pct:.2f}%" if pnl_pct < 0 else f"{pnl_pct:.2f}%")
                else:
                    pnl_eur_str = "N/D"
                    pnl_pct_str = "N/D"

                metrics_list.append({
                    "ticker_internal": ticker,
                    "Strumento": name,
                    "Categoria": category,
                    "ISIN": isin_val,
                    "Data Emissione": inception_date_str,
                    "JustETF": justetf_url,
                    "Attivo": bool(is_active),
                    "TER (%)": float(ter_val),
                    "Investito (€)": float(inv_amt),
                    "Prezzo Carico (€)": float(buy_pr),
                    "Data Acquisto": str(buy_dt),
                    "Valore Attuale (€)": f"{current_val_eur:.2f} €" if inv_amt > 0 else "N/D",
                    "Profitto/Perdita (€)": pnl_eur_str,
                    "Profitto/Perdita (%)": pnl_pct_str,
                    "Ultimo (€)": f"{latest_price:.2f} €",
                    "YTD (%)": fmt_pct(ret_ytd),
                    "1 Anno (%)": fmt_pct(ret_1y),
                    "Volatilità 1A": f"{volatility_1y:.2f}%",
                    "Sharpe 1A": f"{sharpe_1y:.2f}",
                    "Sortino 1A": f"{sortino_1y:.2f}",
                    "SMA200": sma_val,
                    "RSI (14)": f"{rsi_val:.1f}",
                    "raw_close": data,
                    "raw_latest": latest_price,
                    "raw_sma200": sma_200,
                    "raw_rsi": rsi_val
                })
        except Exception:
            pass

    return pd.DataFrame(metrics_list), historical_prices, historical_ohlc

def compute_dynamic_cycles(historical_prices, timeframe_choice):
    cycles_list = []
    tf_map = {"1 Mese": 21, "3 Mesi": 63, "6 Mesi": 126, "1 Anno": 252, "3 Anni": 252*3, "5 Anni": 252*5, "Tutto": None}
    days = tf_map.get(timeframe_choice)

    for name in historical_prices.columns:
        data = historical_prices[name].dropna()
        if len(data) > 2:
            period_data = data.iloc[-days:] if days and len(data) > days else data
            latest_price = period_data.iloc[-1]
            start_price = period_data.iloc[0]
            period_return = ((latest_price - start_price) / start_price) * 100
            
            rolling_max = period_data.cummax()
            drawdown = (period_data - rolling_max) / rolling_max * 100
            max_dd_in_period = drawdown.min()
            max_dd_date = drawdown.idxmin().strftime("%d/%m/%Y")

            try:
                yearly = data.resample('YE').last().pct_change() * 100
            except Exception:
                yearly = data.resample('A').last().pct_change() * 100

            if not yearly.empty:
                first_yr = data.index[0].year
                yearly.iloc[0] = ((data[str(first_yr)].iloc[-1] - data[str(first_yr)].iloc[0]) / data[str(first_yr)].iloc[0]) * 100
                yearly_clean = yearly.dropna()
                if not yearly_clean.empty:
                    best_yr_name = yearly_clean.idxmax().year
                    best_yr_val = yearly_clean.max()
                    worst_yr_name = yearly_clean.idxmin().year
                    worst_yr_val = yearly_clean.min()
                    best_str = f"{best_yr_name} (+{best_yr_val:.2f}%)"
                    worst_str = f"{worst_yr_name} ({worst_yr_val:.2f}%)"
                else:
                    best_str, worst_str = "N/D", "N/D"
            else:
                best_str, worst_str = "N/D", "N/D"

            all_rolling_max = data.cummax()
            all_drawdown = (data - all_rolling_max) / all_rolling_max * 100
            max_dd_val = all_drawdown.min()
            max_dd_date_all = all_drawdown.idxmin().strftime("%m/%Y")

            cycles_list.append({
                "Strumento": name,
                "Rendimento": f"{period_return:+.2f}%",
                "Crollo Max": f"{max_dd_in_period:.2f}% ({max_dd_date})",
                "Miglior Anno Solare": best_str,
                "Peggior Anno Solare": worst_str,
                "Peggior Crollo Storico": f"{max_dd_val:.2f}% ({max_dd_date_all})"
            })

    return pd.DataFrame(cycles_list)

def color_performance(val):
    if isinstance(val, str):
        if val.startswith('+'): return 'color: #16A34A; font-weight: 600;'
        elif val.startswith('-'): return 'color: #DC2626; font-weight: 600;'
    return ''

def color_pullback(val):
    if isinstance(val, str) and val.endswith('%'):
        try:
            num = float(val.replace('%', '').replace('+', '').strip())
            if num >= -15.0:
                return 'color: #16A34A; font-weight: 600;'
            elif -25.0 <= num < -15.0:
                return 'color: #D97706; font-weight: 600;'
            else:
                return 'color: #DC2626; font-weight: 600;'
        except ValueError:
            pass
    return ''

if st.session_state.watchlist:
    placeholder_loading = st.empty()
    with placeholder_loading.container():
        st.markdown('<div class="loader-container"><div class="dot-flashing"></div></div>', unsafe_allow_html=True)

    df_metrics, df_prices, df_ohlc = get_etf_data(list(st.session_state.watchlist.keys()))
    
    placeholder_loading.empty()

    if not df_metrics.empty:
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Performance e Grafici", 
            "Analisi Cicli & Drawdown", 
            "Opportunità di Pullback",
            "Correlazione & Backtest",
            "Guida e Metriche"
        ])

        with tab1:
            st.markdown("### Portafoglio & Gestione ETF")
            
            with st.expander("⚙️ Personalizza Colonne Tabella"):
                st.markdown("<small style='color: #475569;'>Seleziona le colonne da visualizzare:</small>", unsafe_allow_html=True)
                temp_selected_cols = []
                col_c1, col_c2, col_c3, col_c4 = st.columns(4)
                for i, col_name in enumerate(all_tab1_cols):
                    default_checked = col_name in st.session_state.selected_tab1_cols
                    target_col = [col_c1, col_c2, col_c3, col_c4][i % 4]
                    if target_col.checkbox(col_name, value=default_checked, key=f"chk_col_tab1_{i}"):
                        temp_selected_cols.append(col_name)
                
                if temp_selected_cols != st.session_state.selected_tab1_cols:
                    st.session_state.selected_tab1_cols = temp_selected_cols
            
            if not st.session_state.selected_tab1_cols:
                st.session_state.selected_tab1_cols = default_tab1_cols.copy()

            active_df_metrics = df_metrics[df_metrics["Attivo"] == True].copy()

            if not active_df_metrics.empty:
                st.markdown("<small>Modifica direttamente qui sotto le spunte **Attivo**, il **TER (%)**, il **Capitale Investito (€)**, il **Prezzo di Carico (€)** o la **Data di Acquisto**. Clicca su **'Salva Modifiche Tabella'** in fondo per memorizzare.</small>", unsafe_allow_html=True)

                cols_to_display = st.session_state.selected_tab1_cols.copy()
                if "ticker_internal" not in cols_to_display:
                    cols_to_display_full = cols_to_display + ["ticker_internal"]
                else:
                    cols_to_display_full = cols_to_display

                display_cols_clean = [c for c in cols_to_display_full if not c.startswith("raw_")]

                edited_df = st.data_editor(
                    active_df_metrics[cols_to_display_full][[c for c in cols_to_display_full if c in display_cols_clean or c == "ticker_internal"]],
                    use_container_width=True,
                    hide_index=True,
                    disabled=[c for c in display_cols_clean if c not in ["Attivo", "TER (%)", "Investito (€)", "Prezzo Carico (€)", "Data Acquisto"]] + ["ticker_internal"],
                    column_config={
                        "ticker_internal": None,
                        "Strumento": st.column_config.TextColumn("Strumento"),
                        "Categoria": st.column_config.TextColumn("Categoria"),
                        "ISIN": st.column_config.TextColumn("ISIN"),
                        "Data Emissione": st.column_config.TextColumn("Data Emissione"),
                        "JustETF": st.column_config.LinkColumn("Scheda", display_text="[Link]"),
                        "Attivo": st.column_config.CheckboxColumn("Attivo"),
                        "TER (%)": st.column_config.NumberColumn("TER (%)", format="%.2f%%"),
                        "Investito (€)": st.column_config.NumberColumn("Capitale Investito (€)", min_value=0.0, step=100.0, format="%.2f €"),
                        "Prezzo Carico (€)": st.column_config.NumberColumn("Prezzo di Carico (€)", min_value=0.0, step=0.01, format="%.2f €"),
                        "Data Acquisto": st.column_config.TextColumn("Data Acquisto", help="Es. 07.08.26 o 07/08/2026"),
                        "Valore Attuale (€)": st.column_config.TextColumn("Valore Attuale (€)"),
                        "Profitto/Perdita (€)": st.column_config.TextColumn("P&L (€)"),
                        "Profitto/Perdita (%)": st.column_config.TextColumn("P&L (%)"),
                        "Ultimo (€)": st.column_config.TextColumn("Ultimo (€)"),
                        "YTD (%)": st.column_config.TextColumn("YTD (%)"),
                        "1 Anno (%)": st.column_config.TextColumn("1 Anno (%)"),
                        "Volatilità 1A": st.column_config.TextColumn("Volatilità 1A"),
                        "Sharpe 1A": st.column_config.TextColumn("Sharpe 1A"),
                        "Sortino 1A": st.column_config.TextColumn("Sortino 1A"),
                        "SMA200": st.column_config.TextColumn("SMA200"),
                        "RSI (14)": st.column_config.TextColumn("RSI")
                    },
                    key="portfolio_editor"
                )

                if st.button("💾 Salva Modifiche Tabella"):
                    updated = False
                    for idx, row in edited_df.iterrows():
                        tk = row["ticker_internal"]
                        new_ter = row["TER (%)"] if "TER (%)" in edited_df.columns else st.session_state.watchlist.get(tk, {}).get("ter", 0.0)
                        new_active = row["Attivo"] if "Attivo" in edited_df.columns else st.session_state.watchlist.get(tk, {}).get("active", True)
                        new_inv = row["Investito (€)"] if "Investito (€)" in edited_df.columns else st.session_state.watchlist.get(tk, {}).get("invested_amount", 0.0)
                        new_buy = row["Prezzo Carico (€)"] if "Prezzo Carico (€)" in edited_df.columns else st.session_state.watchlist.get(tk, {}).get("buy_price", 0.0)
                        new_date = row["Data Acquisto"] if "Data Acquisto" in edited_df.columns else st.session_state.watchlist.get(tk, {}).get("buy_date", "")
                        
                        old_info = st.session_state.watchlist.get(tk, {})
                        if (float(new_ter) != float(old_info.get("ter", 0.0)) or 
                            bool(new_active) != bool(old_info.get("active", True)) or
                            float(new_inv) != float(old_info.get("invested_amount", 0.0)) or
                            float(new_buy) != float(old_info.get("buy_price", 0.0)) or
                            str(new_date) != str(old_info.get("buy_date", ""))):
                            
                            st.session_state.watchlist[tk]["ter"] = float(new_ter)
                            st.session_state.watchlist[tk]["active"] = bool(new_active)
                            st.session_state.watchlist[tk]["invested_amount"] = float(new_inv)
                            st.session_state.watchlist[tk]["buy_price"] = float(new_buy)
                            st.session_state.watchlist[tk]["buy_date"] = str(new_date)
                            updated = True

                    save_watchlist(st.session_state.watchlist)
                    save_settings({"selected_tab1_cols": st.session_state.selected_tab1_cols})
                    
                    st.success("Modifiche e impostazioni salvate con successo!")
                    st.rerun()
            else:
                st.info("Nessun ETF attivo. Usa i pulsanti nella barra laterale (es. 'Tutti' o seleziona qualche spunta) per visualizzarli nella tabella.")

            st.markdown("---")
            st.markdown("### Storico Prezzi & Confronto")
            
            c_opt1, c_opt2, c_opt3 = st.columns([0.35, 0.35, 0.3])
            with c_opt1:
                chart_options = ["Linee (Normalizzato)", "Candele (Candlestick)"]
                current_chart_selection = st.session_state.get("chart_type_radio", "Linee (Normalizzato)")
                default_idx = chart_options.index(current_chart_selection) if current_chart_selection in chart_options else 0
                
                chart_type = st.radio("Tipo di Grafico:", chart_options, index=default_idx, horizontal=True, key="chart_type_radio")
            with c_opt2:
                timeframe = st.radio("Orizzonte temporale:", ["1 Anno", "3 Anni", "5 Anni", "Tutto"], index=0, horizontal=True, key="tf_chart")
            with c_opt3:
                selected_benchmarks = st.multiselect("Aggiungi Benchmark:", ["MSCI World (SWDA.MI)", "S&P 500 (SPY)", "All-World (VWCE.DE)"])

            active_rows = df_metrics[df_metrics["Attivo"] == True]
            active_names_from_editor = active_rows["Strumento"].tolist()

            if chart_type == "Linee (Normalizzato)":
                df_filtered_prices = df_prices[[col for col in df_prices.columns if col in active_names_from_editor]] if not df_prices.empty else pd.DataFrame()
                
                bench_map = {
                    "MSCI World (SWDA.MI)": "SWDA.MI",
                    "S&P 500 (SPY)": "SPY",
                    "All-World (VWCE.DE)": "VWCE.DE"
                }
                for benchmark_choice in selected_benchmarks:
                    if benchmark_choice in bench_map:
                        bench_ticker = bench_map[benchmark_choice]
                        try:
                            b_obj = yf.Ticker(bench_ticker)
                            b_data = b_obj.history(period="max")['Close']
                            if not isinstance(b_data.index, pd.DatetimeIndex): b_data.index = pd.to_datetime(b_data.index)
                            b_data = b_data.tz_localize(None)
                            df_filtered_prices[f"📊 {benchmark_choice}"] = b_data
                        except Exception:
                            pass

                if st.session_state.focus_ticker:
                    focused_info = st.session_state.watchlist.get(st.session_state.focus_ticker, {})
                    focused_name = focused_info.get("name")
                    if focused_name and focused_name in df_filtered_prices.columns:
                        df_filtered_prices = df_filtered_prices[[focused_name]]
                        st.info(f"Visualizzazione isolata per: **{focused_name}**. Clicca su 'Reset' nella barra laterale per tornare a vederli tutti.")

                if not df_filtered_prices.empty:
                    if timeframe == "1 Anno" and len(df_filtered_prices) >= 252: df_filtered_prices = df_filtered_prices.iloc[-252:]
                    elif timeframe == "3 Anni" and len(df_filtered_prices) >= 252*3: df_filtered_prices = df_filtered_prices.iloc[-252*3:]
                    elif timeframe == "5 Anni" and len(df_filtered_prices) >= 252*5: df_filtered_prices = df_filtered_prices.iloc[-252*5:]

                    normalized_prices = df_filtered_prices.apply(lambda col: (col / col.dropna().iloc[0]) * 100 if not col.dropna().empty else col)
                    
                    fig = px.line(normalized_prices, labels={"value": "Indice (Base 100)", "index": "Data"})
                    fig.update_traces(line_width=1.8)

                    for trace in fig.data:
                        if trace.name and "📊" in trace.name:
                            trace.line.width = 2.0
                            trace.line.dash = None

                    for idx, row in active_rows.iterrows():
                        name = row["Strumento"]
                        buy_p = row["Prezzo Carico (€)"]
                        if buy_p > 0 and name in df_filtered_prices.columns:
                            first_price = df_filtered_prices[name].dropna().iloc[0] if not df_filtered_prices[name].dropna().empty else 1.0
                            buy_p_normalized = (buy_p / first_price) * 100
                            fig.add_hline(
                                y=buy_p_normalized, 
                                line_dash="dot", 
                                line_color="#E11D48", 
                                line_width=1.0,
                                annotation_text=f"Carico {name[:10]}: {buy_p}€", 
                                annotation_position="bottom right",
                                annotation_font_color="#E11D48"
                            )

                    fig.update_layout(
                        plot_bgcolor="white", paper_bgcolor="white",
                        font=dict(color="#475569", size=10),
                        margin=dict(l=10, r=10, t=10, b=10),
                        xaxis=dict(showgrid=True, gridcolor="#F1F5F9"),
                        yaxis=dict(showgrid=True, gridcolor="#F1F5F9"),
                        legend=dict(title_text='', orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig, use_container_width=True)

            else:
                active_candle_rows = df_metrics[df_metrics["Attivo"] == True]
                candlestick_names = active_candle_rows["Strumento"].tolist()

                if st.session_state.focus_ticker:
                    focused_info = st.session_state.watchlist.get(st.session_state.focus_ticker, {})
                    focused_name = focused_info.get("name")
                    if focused_name:
                        candlestick_names = [focused_name]

                if candlestick_names:
                    selected_candle_etf = st.selectbox("Seleziona ETF per il grafico a candele:", candlestick_names, key="select_candle_etf")
                    
                    st.markdown("##### 🛠️ Configurazione Indicatori Tecnici")
                    col_ind1, col_ind2, col_ind3, col_ind4, col_ind5 = st.columns([0.22, 0.18, 0.18, 0.18, 0.24])
                    with col_ind1:
                        show_ma = st.checkbox("Media Mobile", value=True)
                    with col_ind2:
                        ma_type = st.selectbox("Tipo MA", ["SMA", "EMA"], index=0, label_visibility="collapsed")
                    with col_ind3:
                        ma_period = st.number_input("Periodo MA", min_value=5, max_value=300, value=200, step=5, label_visibility="collapsed")
                    with col_ind4:
                        show_bollinger = st.checkbox("Bollinger", value=False)
                    with col_ind5:
                        show_fib = st.checkbox("Ritracciamenti Fibonacci", value=False)

                    col_ind6, col_ind7, col_ind8 = st.columns([0.38, 0.42, 0.20])
                    
                    with col_ind6:
                        bottom_indicator = st.selectbox("Indicatore Inferiore nel sottografico:", ["RSI (14)", "MACD", "Nessuno"], index=0)
                    
                    with col_ind7:
                        st.markdown("<small style='color: #475569;'>Zoom Temporale:</small>", unsafe_allow_html=True)
                        if "candle_time_tf" not in st.session_state:
                            st.session_state.candle_time_tf = "Tutto"
                        
                        current_tf = st.session_state.candle_time_tf
                        
                        zt_col1, zt_col2, zt_col3, zt_col4, zt_col5 = st.columns(5)
                        
                        def get_btn_type(tf_name):
                            return "primary" if current_tf == tf_name else "secondary"

                        if zt_col1.button("1m", key="zt_1m", type=get_btn_type("1m"), use_container_width=True): 
                            st.session_state.candle_time_tf = "1m"
                            st.rerun()
                        if zt_col2.button("3m", key="zt_3m", type=get_btn_type("3m"), use_container_width=True): 
                            st.session_state.candle_time_tf = "3m"
                            st.rerun()
                        if zt_col3.button("6m", key="zt_6m", type=get_btn_type("6m"), use_container_width=True): 
                            st.session_state.candle_time_tf = "6m"
                            st.rerun()
                        if zt_col4.button("1y", key="zt_1y", type=get_btn_type("1y"), use_container_width=True): 
                            st.session_state.candle_time_tf = "1y"
                            st.rerun()
                        if zt_col5.button("All", key="zt_all", type=get_btn_type("Tutto"), use_container_width=True): 
                            st.session_state.candle_time_tf = "Tutto"
                            st.rerun()

                    with col_ind8:
                        st.markdown("<small style='color: #475569;'>Zoom Vista:</small>", unsafe_allow_html=True)
                        z_col1, z_col2 = st.columns(2)
                        if "candle_zoom_bars" not in st.session_state:
                            st.session_state.candle_zoom_bars = None
                        if z_col1.button("In (+)", key="zoom_in_btn", use_container_width=True):
                            if st.session_state.candle_zoom_bars is None:
                                st.session_state.candle_zoom_bars = 126
                            else:
                                st.session_state.candle_zoom_bars = max(20, int(st.session_state.candle_zoom_bars * 0.75))
                            st.rerun()
                        if z_col2.button("Out (-)", key="zoom_out_btn", use_container_width=True):
                            if st.session_state.candle_zoom_bars is not None:
                                st.session_state.candle_zoom_bars = int(st.session_state.candle_zoom_bars * 1.33)
                                if st.session_state.candle_zoom_bars > 1000:
                                    st.session_state.candle_zoom_bars = None
                            st.rerun()
                    
                    if selected_candle_etf in df_ohlc:
                        df_c = df_ohlc[selected_candle_etf].copy()
                        
                        tf_selection = st.session_state.get("candle_time_tf", "Tutto")
                        if tf_selection == "1m" and len(df_c) >= 21: df_c = df_c.iloc[-21:]
                        elif tf_selection == "3m" and len(df_c) >= 63: df_c = df_c.iloc[-63:]
                        elif tf_selection == "6m" and len(df_c) >= 126: df_c = df_c.iloc[-126:]
                        elif tf_selection == "1y" and len(df_c) >= 252: df_c = df_c.iloc[-252:]

                        df_c = df_c.dropna(subset=['Open', 'High', 'Low', 'Close'])
                        df_c = df_c[df_c['High'] != df_c['Low']]

                        if st.session_state.candle_zoom_bars is not None and len(df_c) > st.session_state.candle_zoom_bars:
                            df_c = df_c.tail(st.session_state.candle_zoom_bars)
                        
                        x_dates = df_c.index.strftime('%Y-%m-%d')

                        has_bottom = bottom_indicator != "Nessuno"
                        if has_bottom:
                            fig_c = make_subplots(
                                rows=2, cols=1, 
                                shared_xaxes=True, 
                                vertical_spacing=0.05, 
                                row_heights=[0.75, 0.25]
                            )
                        else:
                            fig_c = go.Figure()

                        candlestick_trace = go.Candlestick(
                            x=x_dates,
                            open=df_c['Open'],
                            high=df_c['High'],
                            low=df_c['Low'],
                            close=df_c['Close'],
                            increasing_line_color='#16A34A', 
                            decreasing_line_color='#DC2626',
                            name='Prezzo'
                        )
                        
                        if has_bottom:
                            fig_c.add_trace(candlestick_trace, row=1, col=1)
                        else:
                            fig_c.add_trace(candlestick_trace)

                        if show_ma:
                            if ma_type == "SMA":
                                ma_series = df_c['Close'].rolling(window=ma_period).mean()
                            else:
                                ma_series = df_c['Close'].ewm(span=ma_period, adjust=False).mean()
                                
                            ma_trace = go.Scatter(
                                x=x_dates,
                                y=ma_series,
                                mode='lines',
                                name=f'{ma_type} {ma_period}',
                                line=dict(color='#2563EB', width=1.5)
                            )
                            if has_bottom:
                                fig_c.add_trace(ma_trace, row=1, col=1)
                            else:
                                fig_c.add_trace(ma_trace)

                        if show_bollinger:
                            bb_sma = df_c['Close'].rolling(window=20).mean()
                            bb_std = df_c['Close'].rolling(window=20).std()
                            bb_upper = bb_sma + (bb_std * 2)
                            bb_lower = bb_sma - (bb_std * 2)
                            
                            trace_upper = go.Scatter(x=x_dates, y=bb_upper, mode='lines', name='Bollinger Superiore', line=dict(color='rgba(147, 51, 234, 0.5)', width=1, dash='dot'))
                            trace_lower = go.Scatter(x=x_dates, y=bb_lower, mode='lines', name='Bollinger Inferiore', line=dict(color='rgba(147, 51, 234, 0.5)', width=1, dash='dot'), fill='tonexty', fillcolor='rgba(147, 51, 234, 0.05)')
                            
                            if has_bottom:
                                fig_c.add_trace(trace_upper, row=1, col=1)
                                fig_c.add_trace(trace_lower, row=1, col=1)
                            else:
                                fig_c.add_trace(trace_upper)
                                fig_c.add_trace(trace_lower)

                        if show_fib and not df_c.empty:
                            min_price = df_c['Low'].min()
                            max_price = df_c['High'].max()
                            diff = max_price - min_price
                            
                            fib_levels = {
                                "Fib 0.0% (Max)": max_price,
                                "Fib 23.6%": max_price - 0.236 * diff,
                                "Fib 38.2%": max_price - 0.382 * diff,
                                "Fib 50.0%": max_price - 0.5 * diff,
                                "Fib 61.8%": max_price - 0.618 * diff,
                                "Fib 100.0% (Min)": min_price
                            }
                            fib_colors = {"Fib 0.0% (Max)": "#DC2626", "Fib 23.6%": "#D97706", "Fib 38.2%": "#2563EB", "Fib 50.0%": "#059669", "Fib 61.8%": "#9333EA", "Fib 100.0% (Min)": "#16A34A"}
                            
                            for label, val in fib_levels.items():
                                if has_bottom:
                                    fig_c.add_hline(y=val, line_dash="dash", line_color=fib_colors.get(label, "#64748B"), line_width=1, annotation_text=f"{label}: {val:.2f}€", annotation_position="top left", row=1, col=1)
                                else:
                                    fig_c.add_hline(y=val, line_dash="dash", line_color=fib_colors.get(label, "#64748B"), line_width=1, annotation_text=f"{label}: {val:.2f}€", annotation_position="top left")

                        if bottom_indicator == "RSI (14)":
                            rsi_series = calculate_rsi_series(df_c['Close'], 14)
                            rsi_trace = go.Scatter(
                                x=x_dates,
                                y=rsi_series,
                                mode='lines',
                                name='RSI (14)',
                                line=dict(color='#9333EA', width=1.5)
                            )
                            fig_c.add_trace(rsi_trace, row=2, col=1)
                            fig_c.add_hline(y=70, line_dash="dash", line_color="#DC2626", line_width=1, row=2, col=1)
                            fig_c.add_hline(y=30, line_dash="dash", line_color="#16A34A", line_width=1, row=2, col=1)
                        elif bottom_indicator == "MACD":
                            exp1 = df_c['Close'].ewm(span=12, adjust=False).mean()
                            exp2 = df_c['Close'].ewm(span=26, adjust=False).mean()
                            macd_line = exp1 - exp2
                            signal_line = macd_line.ewm(span=9, adjust=False).mean()
                            hist_line = macd_line - signal_line
                            
                            fig_c.add_trace(go.Scatter(x=x_dates, y=macd_line, mode='lines', name='MACD', line=dict(color='#2563EB', width=1.2)), row=2, col=1)
                            fig_c.add_trace(go.Scatter(x=x_dates, y=signal_line, mode='lines', name='Segnale', line=dict(color='#DC2626', width=1.2)), row=2, col=1)
                            fig_c.add_trace(go.Bar(x=x_dates, y=hist_line, name='Istogramma', marker_color='#94A3B8'), row=2, col=1)

                        matched_row = active_rows[active_rows["Strumento"] == selected_candle_etf]
                        if not matched_row.empty:
                            buy_p_val = matched_row.iloc[0]["Prezzo Carico (€)"]
                            if buy_p_val > 0:
                                if has_bottom:
                                    fig_c.add_hline(y=buy_p_val, line_dash="dot", line_color="#E11D48", line_width=1.0, row=1, col=1)
                                else:
                                    fig_c.add_hline(y=buy_p_val, line_dash="dot", line_color="#E11D48", line_width=1.0)

                        layout_update = dict(
                            title=f"Grafico Tecnico - {selected_candle_etf}",
                            plot_bgcolor="white", paper_bgcolor="white",
                            font=dict(color="#475569", size=10),
                            margin=dict(l=10, r=10, t=30, b=10),
                            xaxis=dict(showgrid=True, gridcolor="#F1F5F9", type='category', nticks=10),
                            yaxis=dict(showgrid=True, gridcolor="#F1F5F9", title="Prezzo (€)"),
                            xaxis_rangeslider_visible=False,
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                        )
                        
                        if has_bottom:
                            layout_update["yaxis2"] = dict(showgrid=True, gridcolor="#F1F5F9", title=bottom_indicator.split()[0])
                            layout_update["xaxis2"] = dict(showgrid=True, gridcolor="#F1F5F9", type='category')

                        fig_c.update_layout(**layout_update)
                        st.plotly_chart(fig_c, use_container_width=True)
                    else:
                        st.warning("Dati OHLC non disponibili per questo strumento.")
                else:
                    st.info("Nessun ETF attivo selezionato per il grafico a candele.")

            # --- STORICO PERSONALIZZATO DALLA DATA DI ACQUISTO ---
            st.markdown("---")
            st.markdown("### 📈 Storico Personalizzato dall'Acquisto")
            st.markdown("<small>Seleziona un ETF del tuo portafoglio per visualizzarne lo storico dei prezzi a partire dalla specifica data di acquisto inserita.</small>", unsafe_allow_html=True)

            portfolio_invested_df = df_metrics[(df_metrics["Investito (€)"] > 0) & (df_metrics["Prezzo Carico (€)"] > 0) & (df_metrics["Data Acquisto"] != "")]

            if not portfolio_invested_df.empty:
                etf_names_list = portfolio_invested_df["Strumento"].tolist()
                selected_invested_etf = st.selectbox("Seleziona ETF da analizzare:", etf_names_list, key="selected_inv_etf_chart")

                if selected_invested_etf:
                    row_data = portfolio_invested_df[portfolio_invested_df["Strumento"] == selected_invested_etf].iloc[0]
                    buy_date_raw = row_data["Data Acquisto"]
                    buy_price_val = row_data["Prezzo Carico (€)"]
                    full_series = row_data["raw_close"]

                    parsed_buy_date = parse_custom_date(buy_date_raw)

                    if pd.notna(parsed_buy_date) and not full_series.empty:
                        series_from_buy = full_series[full_series.index >= parsed_buy_date]

                        if len(series_from_buy) >= 2:
                            fig_buy = px.line(
                                series_from_buy, 
                                labels={"value": "Prezzo (€)", "index": "Data"},
                                title=f"Andamento di {selected_invested_etf} dal {parsed_buy_date.strftime('%d/%m/%Y')}"
                            )
                            fig_buy.update_traces(line_width=2, line_color="#2563EB")

                            fig_buy.add_hline(
                                y=buy_price_val,
                                line_dash="dot",
                                line_color="#E11D48",
                                line_width=1.0,
                                annotation_text=f"Prezzo di Carico: {buy_price_val:.2f} €",
                                annotation_position="bottom right",
                                annotation_font_color="#E11D48"
                            )

                            fig_buy.update_layout(
                                plot_bgcolor="white", paper_bgcolor="white",
                                font=dict(color="#475569", size=10),
                                margin=dict(l=10, r=10, t=30, b=10),
                                xaxis=dict(showgrid=True, gridcolor="#F1F5F9"),
                                yaxis=dict(showgrid=True, gridcolor="#F1F5F9")
                            )
                            st.plotly_chart(fig_buy, use_container_width=True)
                        elif len(series_from_buy) == 1:
                            st.info(f"La data di acquisto ({parsed_buy_date.strftime('%d/%m/%Y')}) corrisponde all'ultimo prezzo disponibile. Il grafico richiede almeno due punti storici distinti per tracciare la linea. Prezzo attuale/carico registrato: **{buy_price_val:.2f} €**.")
                        else:
                            st.warning(f"La data di acquisto ({buy_date_raw}) è successiva ai dati storici disponibili o non ci sono punti in questo intervallo.")
                    else:
                        st.error(f"Formato data non valido ('{buy_date_raw}'). Assicurati di inserire la data nel formato corretto (es. 07.08.26 o 07/08/2026).")
            else:
                st.info("Nessun ETF in portafoglio ha una data di acquisto e un prezzo di carico validi. Inseriscili direttamente nella tabella sopra.")

        with tab2:
            st.markdown("### Analisi Storica Completa e Drawdown (Solo ETF Attivi)")
            
            with st.expander("⚙️ Personalizza Colonne Tabella"):
                st.markdown("<small style='color: #475569;'>Seleziona le colonne da visualizzare:</small>", unsafe_allow_html=True)
                selected_tab2_cols = []
                col_d1, col_d2 = st.columns(2)
                for i, col_name in enumerate(all_tab2_cols):
                    target_col = [col_d1, col_d2][i % 2]
                    if target_col.checkbox(col_name, value=True, key=f"chk_col_tab2_{i}"):
                        selected_tab2_cols.append(col_name)
            
            if not selected_tab2_cols:
                selected_tab2_cols = all_tab2_cols

            selected_tf = st.selectbox("Orizzonte temporale:", ["1 Mese", "3 Mesi", "6 Mesi", "1 Anno", "3 Anni", "5 Anni", "Tutto"], index=4, key="cycles_tf_select")
            
            active_names_tab2 = df_metrics[df_metrics["Attivo"] == True]["Strumento"].tolist()
            df_prices_active = df_prices[[c for c in df_prices.columns if c in active_names_tab2]] if not df_prices.empty else pd.DataFrame()

            df_cycles = compute_dynamic_cycles(df_prices_active, selected_tf) if not df_prices_active.empty else pd.DataFrame()
            if not df_cycles.empty:
                cols_to_show_tab2 = [c for c in selected_tab2_cols if c in df_cycles.columns]
                df_cycles_filtered = df_cycles[cols_to_show_tab2] if cols_to_show_tab2 else df_cycles
                
                cols_to_color = [c for c in ["Rendimento"] if c in df_cycles_filtered.columns]
                if cols_to_color:
                    st.dataframe(
                        df_cycles_filtered.style.map(color_performance, subset=cols_to_color), 
                        use_container_width=True, 
                        hide_index=True
                    )
                else:
                    st.dataframe(
                        df_cycles_filtered, 
                        use_container_width=True, 
                        hide_index=True
                    )
            else:
                st.info("Nessun ETF attivo selezionato per l'analisi dei cicli.")

        with tab3:
            st.markdown("### Opportunità di Pullback (Trend Rialzista & Storno dai Massimi)")
            st.markdown("<small>Imposta la soglia di storno desiderata per filtrare le opportunità e visualizza l'elenco completo di tutti gli altri ETF attivi sottostanti.</small>", unsafe_allow_html=True)
            
            col_s1, col_s2 = st.columns([0.4, 0.6])
            with col_s1:
                pullback_threshold = st.slider(
                    "Soglia minima di storno dai massimi (%):", 
                    min_value=-30, max_value=0, value=-5, step=1,
                    help="Es. impostando -5%, cercherà ETF stornati del 5% o più rispetto al loro picco."
                )

            matching_list = []
            other_list = []

            for idx, row in df_metrics.iterrows():
                if not row["Attivo"]:
                    continue
                name = row["Strumento"]
                sma_status = row["SMA200"]
                rsi_val = row["raw_rsi"]
                latest_p = row["raw_latest"]
                data_series = row["raw_close"]
                
                if not data_series.empty:
                    peak_price = data_series.iloc[-252:].max() if len(data_series) >= 252 else data_series.max()
                    current_dd = ((latest_p - peak_price) / peak_price) * 100
                    
                    item = {
                        "Strumento": name,
                        "Categoria": row["Categoria"],
                        "Ultimo (€)": f"{latest_p:.2f} €",
                        "Storno dai Massimi (%)": f"{current_dd:+.2f}%",
                        "SMA200": sma_status,
                        "RSI (14)": f"{rsi_val:.1f}",
                        "1 Anno (%)": row["1 Anno (%)"]
                    }
                    
                    if sma_status == "🟩" and current_dd <= pullback_threshold:
                        matching_list.append(item)
                    else:
                        other_list.append(item)
            
            st.markdown("#### 🎯 Opportunità in linea con i criteri impostati")
            if matching_list:
                df_matching = pd.DataFrame(matching_list)
                st.dataframe(
                    df_matching.style.map(color_pullback, subset=["Storno dai Massimi (%)"]).map(color_performance, subset=["1 Anno (%)"]),
                    use_container_width=True, 
                    hide_index=True
                )
            else:
                st.info(f"Nessun ETF attivo soddisfa i criteri con uno storno di almeno {pullback_threshold}% e trend sopra la SMA200.")

            st.markdown("---")
            st.markdown("#### 📋 Tutti gli altri ETF attivi in watchlist")
            if other_list:
                df_other = pd.DataFrame(other_list)
                st.dataframe(
                    df_other.style.map(color_pullback, subset=["Storno dai Massimi (%)"]).map(color_performance, subset=["1 Anno (%)"]),
                    use_container_width=True, 
                    hide_index=True
                )
            else:
                st.info("Nessun altro ETF attivo presente.")

        with tab4:
            st.markdown("### Matrice di Correlazione")
            active_rows_tab3 = df_metrics[df_metrics["Attivo"] == True]
            active_names_tab3 = active_rows_tab3["Strumento"].tolist()
            if len(active_names_tab3) > 1 and not df_prices.empty:
                returns_matrix = df_prices[[c for c in active_names_tab3 if c in df_prices.columns]].pct_change().dropna()
                corr_matrix = returns_matrix.corr()
                fig_corr = px.imshow(corr_matrix, text_auto=".2f", color_continuous_scale="Blues", zmin=-1, zmax=1)
                fig_corr.update_layout(plot_bgcolor="white", paper_bgcolor="white", height=400, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_corr, use_container_width=True)
            else:
                st.info("Seleziona almeno 2 ETF attivi.")

        with tab5:
            st.markdown("### 📘 Guida Completa, Esempi e Valutazione delle Metriche")
            st.markdown("""
            Questa sezione descrive gli indicatori presenti nell'applicazione, fornendo **esempi concreti** e **soglie di valutazione** per capire se il valore letto nella tabella è favorevole o rischioso.

            ---

            ### 1. TER (Total Expense Ratio)
            * **Cos'è**: Il costo annuo di gestione trattenuto automaticamente dall'emittente del fondo.
            * **Esempio**: Se inserisci un TER del `0.20%` su un capitale investito di `10.000 €`, stai pagando circa `20 €` all'anno in commissioni.
            * **Come valutarlo**:
                * **Ottimo**: Inferiore allo `0.20%` (tipico degli ETF azionari globali passivi broad).
                * **Medio**: Tra `0.20%` e `0.50%` (comune per ETF tematici o obbligazionari specifici).
                * **Alto**: Superiore allo `0.50%` (spesso legato a ETF attivi o materie prime fisiche particolari).

            ---

            ### 2. Volatilità (1 Anno)
            * **Cos'è**: Misura statistica di quanto il prezzo oscilla su base annualizzata. Più è alta, più il fondo è instabile/rischioso nel breve termine.
            * **Esempio**: Una volatilità del `15%` significa che, storicamente, lo strumento tende a muoversi su base annua all'interno di un range ampio di oscillazioni percentuali.
            * **Come valutarlo**:
                * **Bassa (`< 8%`)**: Tipica di ETF monetari o obbligazionari governativi a breve scadenza (movimenti pacati).
                * **Media (`10% - 18%`)**: Tipica di ETF azionari diversificati globali (es. MSCI World o S&P 500).
                * **Alta (`> 20%`)**: Tipica di ETF settoriali (es. tecnologia), mercati emergenti o materie prime.

            ---

            ### 3. Indice di Sharpe (1 Anno)
            * **Cos'è**: Misura il rendimento in eccesso ottenuto rispetto a un investimento privo di rischio, rapportato alla volatilità totale (rischio).
            * **Esempio**: Uno Sharpe di `1.2` indica che lo strumento ha generato un ottimo rendimento compensando ampiamente il rischio corso.
            * **Come valutarlo**:
                * **Negativo o `<= 0`**: Il rendimento è inferiore al tasso privo di rischio (il fondo ha reso meno della liquidità).
                * **Intorno a `1.0`**: Buono (il rendimento giustifica il rischio).
                * **Superiore a `1.5` o `2.0`**: Eccellente (rendimenti elevati a fronte di oscillazioni contenute).

            ---

            ### 4. Indice di Sortino (1 Anno)
            * **Cos'è**: Simile allo Sharpe, ma penalizza *solo* la volatilità al ribasso (le perdite). Non punisce le oscillazioni positive.
            * **Esempio**: Se un ETF ha uno Sharpe moderato ma un Sortino molto alto (es. `2.0`), significa che quando il prezzo si è mosso, lo ha fatto prevalentemente verso l'alto.
            * **Come valutarlo**: Valori superiori a `1.0` indicano una buona gestione del rischio di perdita. Se il Sortino è molto più alto dello Sharpe, il fondo mostra una forte asimmetria positiva.

            ---

            ### 5. Media Mobile (SMA / EMA)
            * **Cos'è**: Indica la tendenza di fondo del prezzo. La SMA fa una media aritmetica, mentre l'EMA dà più peso alle variazioni recenti.

            ---

            ### 6. Bande di Bollinger & Fibonacci
            * **Bollinger**: Misurano la deviazione standard del prezzo rispetto alla media; aiutano a individuare eccessi di mercato.
            * **Fibonacci**: Tracciano i livelli percentuali di ritracciamento ($23.6\%$, $38.2\%$, $50\%$, $61.8\%$) utili per individuare possibili aree di supporto durante gli storni.

            ---

            ### 7. RSI & MACD
            * **RSI**: Oscillatore di momentum (0-100) per individuare aree di ipercomprato ($>70$) o ipervenduto ($<30$).
            * **MACD**: Indicatore di convergenza/divergenza che mostra l'accelerazione del trend attraverso l'incrocio di medie mobili ed istogramma.
            """)
else:
    st.info("Aggiungi almeno un ETF dalla barra laterale.")
