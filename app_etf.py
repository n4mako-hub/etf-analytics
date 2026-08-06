import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import json
import os
from datetime import datetime
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# 1. Configurazione Pagina e Styling CSS (Ottimizzato per Desktop e Mobile)
st.set_page_config(page_title="ETF Analytics", layout="wide")

# Aggiornamento automatico ogni 15 minuti (900000 millisecondi)
count = st_autorefresh(interval=15 * 60 * 1000, key="datarefresh")

st.markdown("""
    <style>
    /* Regole generali di base */
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

    /* Ottimizzazioni specifiche per Smartphone (Media Query) */
    @media (max-width: 768px) {
        .block-container {
            padding-top: 0.8rem !important;
            padding-bottom: 0.8rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        h1 { font-size: 1.1rem !important; }
        h2, h3 { font-size: 0.85rem !important; }
        /* Rende i bottoni full-width o più compatti su mobile se necessario */
        .stButton button {
            width: 100% !important;
        }
    }
    </style>
""", unsafe_allow_html=True)

st.title("ETF Performance Analytics")

WATCHLIST_FILE = "watchlist.json"

DEFAULT_WATCHLIST = {
    "VWCE.DE": {"name": "Vanguard FTSE All-World UCITS ETF", "isin": "IE00BK5BQT36", "active": True, "ter": 0.22},
    "SWDA.MI": {"name": "iShares Core MSCI World UCITS ETF", "isin": "IE00B4L5Y983", "active": False, "ter": 0.20},
    "XEON.DE": {"name": "Xtrackers EUR Overnight Rate Swap UCITS ETF", "isin": "LU0290358497", "active": False, "ter": 0.10}
}

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k in data:
                    if "ter" not in data[k]:
                        data[k]["ter"] = 0.0
                return data
        except Exception:
            return DEFAULT_WATCHLIST.copy()
    return DEFAULT_WATCHLIST.copy()

def save_watchlist(watchlist):
    try:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"Errore nel salvataggio: {e}")

if "watchlist" not in st.session_state:
    st.session_state.watchlist = load_watchlist()

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

# --- BARRA LATERALE ORDINATA E PULITA ---
st.sidebar.markdown("### 🎛️ Gestione Watchlist")

# Sezione 1: Aggiunta rapida tramite Expander pulito
with st.sidebar.expander("➕ Aggiungi Strumento", expanded=False):
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
                        "ter": 0.0
                    }
                    save_watchlist(st.session_state.watchlist)
                    st.sidebar.success("Aggiunto e salvato")
                    st.rerun()
                else:
                    st.sidebar.error("Strumento non trovato.")

    st.markdown("---")
    st.markdown("**🌐 Ricerca Globale Database**")
    global_query = st.text_input("Parola chiave:", placeholder="es. Artificial Intelligence", key="glob_query")

    if "global_search_results" not in st.session_state:
        st.session_state.global_search_results = []

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("Cerca", use_container_width=True):
            if global_query.strip():
                with st.spinner("Ricerca in corso..."):
                    try:
                        results = yf.Search(global_query.strip(), max_results=8).quotes
                        st.session_state.global_search_results = results
                    except Exception as e:
                        st.sidebar.error(f"Errore: {e}")
    with col_s2:
        if st.button("Pulisci", use_container_width=True):
            st.session_state.global_search_results = []
            st.rerun()

    if st.session_state.global_search_results:
        st.markdown("**Risultati:**")
        for item in st.session_state.global_search_results:
            tk = item.get('symbol')
            name = item.get('longname') or item.get('shortname') or tk
            if tk:
                already_in = tk in st.session_state.watchlist
                col_res1, col_res2 = st.columns([0.7, 0.3])
                col_res1.markdown(f"<small>{name} ({tk})</small>", unsafe_allow_html=True)
                
                if already_in:
                    col_res2.markdown("<small style='color: #16A34A; font-weight: 600;'>In lista</small>", unsafe_allow_html=True)
                else:
                    if col_res2.button("+", key=f"btn_add_{tk}"):
                        st.session_state.watchlist[tk] = {
                            "name": name, 
                            "isin": tk, 
                            "active": True,
                            "ter": 0.0
                        }
                        save_watchlist(st.session_state.watchlist)
                        st.rerun()

st.sidebar.markdown("---")

# Sezione 2: Lista ETF Riorganizzata per Categorie
st.sidebar.markdown("### 📋 Lista ETF e Selezione")
search_query = st.sidebar.text_input("🔍 Filtra rapido:", placeholder="cerca nome o ISIN...")

# Bottoni di controllo rapido compatti
col_b1, col_b2, col_b3 = st.sidebar.columns(3)
if col_b1.button("Tutti", use_container_width=True):
    for tk in st.session_state.watchlist:
        st.session_state.watchlist[tk]["active"] = True
    save_watchlist(st.session_state.watchlist)
    st.rerun()

if col_b2.button("Nessun", use_container_width=True):
    for tk in st.session_state.watchlist:
        st.session_state.watchlist[tk]["active"] = False
    save_watchlist(st.session_state.watchlist)
    st.rerun()

if col_b3.button("Top 5", use_container_width=True, help="Seleziona i top 5 per rendimento storico"):
    performance_scores = {}
    for tk in st.session_state.watchlist:
        try:
            tk_obj = yf.Ticker(tk)
            data = tk_obj.history(period="max")['Close'].dropna()
            if len(data) > 252:
                latest = data.iloc[-1]
                first = data.iloc[0]
                total_years = len(data) / 252.0
                cagr = (((latest / first) ** (1 / total_years)) - 1) * 100
                performance_scores[tk] = cagr
            elif len(data) > 0:
                latest = data.iloc[-1]
                first = data.iloc[0]
                tot_ret = ((latest - first) / first) * 100
                performance_scores[tk] = tot_ret
        except Exception:
            pass
    
    sorted_top = sorted(performance_scores.items(), key=lambda x: x[1], reverse=True)
    top_5_tickers = [item[0] for item in sorted_top[:5]]
    
    for tk in st.session_state.watchlist:
        st.session_state.watchlist[tk]["active"] = (tk in top_5_tickers)
        
    save_watchlist(st.session_state.watchlist)
    st.rerun()

st.sidebar.markdown("")

# Prepariamo i dati raggruppandoli per categoria
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
    st.sidebar.info("Nessun ETF trovato con il filtro corrente.")
else:
    for cat, items in sorted(grouped_watchlist.items()):
        active_count_in_cat = sum(1 for tk, inf in items if inf["active"])
        cat_label = f"📁 {cat} ({active_count_in_cat}/{len(items)})"
        
        with st.sidebar.expander(cat_label, expanded=(len(grouped_watchlist) == 1 or search_query.strip() != "")):
            for tk, info in items:
                current_status = info["active"]
                col_item_chk, col_item_del = st.columns([0.82, 0.18])
                
                new_status = col_item_chk.checkbox(f"{info['name']} ({tk})", value=current_status, key=f"chk_{tk}")
                if new_status != current_status:
                    st.session_state.watchlist[tk]["active"] = new_status
                    state_changed = True
                    
                if col_item_del.button("🗑️", key=f"del_btn_{tk}", help="Elimina definitamente"):
                    del st.session_state.watchlist[tk]
                    save_watchlist(st.session_state.watchlist)
                    st.rerun()

if state_changed:
    save_watchlist(st.session_state.watchlist)
    st.rerun()

st.sidebar.markdown("---")
with st.sidebar.expander("⚙️ Gestione Avanzata"):
    if st.session_state.watchlist:
        ticker_to_delete = st.selectbox("Rimuovi definitivo:", options=list(st.session_state.watchlist.keys()), format_func=lambda x: st.session_state.watchlist[x]["name"])
        if st.button("Elimina elemento"):
            del st.session_state.watchlist[ticker_to_delete]
            save_watchlist(st.session_state.watchlist)
            st.success("Eliminato!")
            st.rerun()
    else:
        st.info("Watchlist vuota.")

active_tickers = [tk for tk, info in st.session_state.watchlist.items() if info["active"]]

# --- RECUPERO DATI E ANALISI (PARTE PRINCIPALE) ---
def get_etf_data(tickers_list):
    metrics_list = []
    historical_prices = pd.DataFrame()

    for ticker in tickers_list:
        info_dict = st.session_state.watchlist.get(ticker, {})
        name = info_dict.get("name", ticker)
        isin_val = info_dict.get("isin", ticker.split(".")[0])
        ter_val = info_dict.get("ter", 0.0)
        
        justetf_url = f"https://www.justetf.com/it/etf-profile.html?isin={isin_val}"
        
        try:
            tk_obj = yf.Ticker(ticker)
            data = tk_obj.history(period="max")['Close']
            
            if not isinstance(data.index, pd.DatetimeIndex):
                data.index = pd.to_datetime(data.index)
            data = data.tz_localize(None)

            info = tk_obj.info
            category = detect_category(name, info)

            if not data.empty:
                historical_prices[name] = data
                latest_price = data.iloc[-1]
                start_date_str = data.index[0].strftime("%m/%Y")
                
                price_1y = data.iloc[-252] if len(data) >= 252 else data.iloc[0]
                ret_1y = ((latest_price - price_1y) / price_1y) * 100
                
                current_year = datetime.now().year
                ytd_data = data[data.index.year == current_year]
                ret_ytd = ((latest_price - ytd_data.iloc[0]) / ytd_data.iloc[0]) * 100 if not ytd_data.empty else 0.0
                
                price_3y = data.iloc[-252 * 3] if len(data) >= 252 * 3 else None
                ret_3y_ann = (((latest_price / price_3y) ** (1/3)) - 1) * 100 if price_3y is not None else None

                price_5y = data.iloc[-252 * 5] if len(data) >= 252 * 5 else None
                ret_5y_ann = (((latest_price / price_5y) ** (1/5)) - 1) * 100 if price_5y is not None else None

                total_years = len(data) / 252.0
                first_price = data.iloc[0]
                ret_max_ann = (((latest_price / first_price) ** (1 / total_years)) - 1) * 100 if total_years >= 1 else None

                def fmt_pct(val):
                    return f"{val:+.2f}%" if isinstance(val, (int, float)) else "N/D"

                metrics_list.append({
                    "ticker_internal": ticker,
                    "Strumento": name,
                    "Categoria": category,
                    "ISIN": isin_val,
                    "JustETF": justetf_url,
                    "TER (%)": float(ter_val),
                    "Ultimo (€)": f"{latest_price:.2f} €",
                    "YTD (%)": fmt_pct(ret_ytd),
                    "1 Anno (%)": fmt_pct(ret_1y),
                    "3 Anni Ann. (%)": fmt_pct(ret_3y_ann),
                    "5 Anni Ann. (%)": fmt_pct(ret_5y_ann),
                    "Max Ann. (%)": fmt_pct(ret_max_ann),
                    "Data Inizio": start_date_str
                })
        except Exception:
            pass

    return pd.DataFrame(metrics_list), historical_prices

def compute_dynamic_cycles(historical_prices, timeframe_choice):
    cycles_list = []
    tf_map = {
        "1 Mese": 21,
        "3 Mesi": 63,
        "6 Mesi": 126,
        "1 Anno": 252,
        "3 Anni": 252 * 3,
        "5 Anni": 252 * 5,
        "Tutto": None
    }
    days = tf_map.get(timeframe_choice)

    for name in historical_prices.columns:
        data = historical_prices[name].dropna()
        if len(data) > 2:
            if days and len(data) > days:
                period_data = data.iloc[-days:]
            else:
                period_data = data

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
                f"Rendimento ({timeframe_choice})": f"{period_return:+.2f}%",
                f"Crollo Max ({timeframe_choice})": f"{max_dd_in_period:.2f}% ({max_dd_date})",
                "Miglior Anno Solare": best_str,
                "Peggior Anno Solare": worst_str,
                "Peggior Crollo Storico": f"{max_dd_val:.2f}% ({max_dd_date_all})"
            })

    return pd.DataFrame(cycles_list)

def compute_pullback_opportunities(historical_prices):
    pullback_list = []
    for name in historical_prices.columns:
        data = historical_prices[name].dropna()
        if len(data) > 60:
            recent_data = data.iloc[-126:] if len(data) >= 126 else data
            recent_high = recent_data.max()
            recent_high_date = recent_data.idxmax().strftime("%d/%m/%Y")
            
            latest_price = data.iloc[-1]
            distance_from_high = ((latest_price - recent_high) / recent_high) * 100
            
            price_1y = data.iloc[-252] if len(data) >= 252 else data.iloc[0]
            ret_1y = ((latest_price - price_1y) / price_1y) * 100
            
            price_3m = data.iloc[-63] if len(data) >= 63 else data.iloc[0]
            ret_3m = ((latest_price - price_3m) / price_3m) * 100

            pullback_list.append({
                "Strumento": name,
                "Prezzo Attuale": latest_price,
                "Massimo Recente (6M)": recent_high,
                "Distanza dai Massimi": distance_from_high,
                "Rend. 3 Mesi": ret_3m,
                "Rend. 1 Anno": ret_1y,
                "Data Massimo": recent_high_date
            })

    df_pb = pd.DataFrame(pullback_list)
    if not df_pb.empty:
        df_pb = df_pb.sort_values(by="Distanza dai Massimi", ascending=True)
    return df_pb

if active_tickers:
    with st.spinner('Caricamento dati in corso...'):
        df_metrics, df_prices = get_etf_data(active_tickers)

    if not df_metrics.empty:
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Performance e Grafici", "📉 Analisi Cicli & Drawdown", "🎯 Opportunità di Pullback", "ℹ️ Guida e Metriche"])

        with tab1:
            header_col1, header_col2 = st.columns([0.92, 0.08])
            with header_col1:
                st.markdown("### Rendimenti e Performance Storiche")
            with header_col2:
                with st.popover("❓ Info"):
                    st.markdown("""
                    **Legenda delle Metriche:**
                    * **Categoria:** Macro-categoria stimata.
                    * **ISIN / JustETF:** Link diretto alla scheda del fondo.
                    * **TER (%):** Costo di gestione annuo (modificabile).
                    """)

            editor_df = df_metrics.copy()
            edited_df = st.data_editor(
                editor_df,
                use_container_width=True,
                hide_index=True,
                disabled=["ticker_internal", "Strumento", "Categoria", "ISIN", "JustETF", "Ultimo (€)", "YTD (%)", "1 Anno (%)", "3 Anni Ann. (%)", "5 Anni Ann. (%)", "Max Ann. (%)", "Data Inizio"],
                column_config={
                    "ticker_internal": None,
                    "JustETF": st.column_config.LinkColumn("Scheda", help="Apri su JustETF", display_text="🌐"),
                    "TER (%)": st.column_config.NumberColumn("TER (%)", min_value=0.0, max_value=5.0, step=0.01, format="%.2f%%")
                },
                key="etf_performance_editor"
            )

            if st.button("Salva modifiche TER"):
                ter_updated = False
                for idx, row in edited_df.iterrows():
                    tk = row["ticker_internal"]
                    new_ter = row["TER (%)"]
                    old_ter = st.session_state.watchlist.get(tk, {}).get("ter", 0.0)
                    if float(new_ter) != float(old_ter):
                        st.session_state.watchlist[tk]["ter"] = float(new_ter)
                        ter_updated = True

                if ter_updated:
                    save_watchlist(st.session_state.watchlist)
                    st.success("TER aggiornato!")
                    st.rerun()

            st.markdown("### Storico Prezzi")
            timeframe = st.radio("Orizzonte temporale grafico:", ["1 Anno", "3 Anni", "5 Anni", "Tutto"], index=1, horizontal=True, key="tf_chart")

            df_filtered_prices = df_prices.ffill().bfill().dropna()
            if not df_filtered_prices.empty:
                if timeframe == "1 Anno" and len(df_filtered_prices) >= 252:
                    df_filtered_prices = df_filtered_prices.iloc[-252:]
                elif timeframe == "3 Anni" and len(df_filtered_prices) >= 252*3:
                    df_filtered_prices = df_filtered_prices.iloc[-252*3:]
                elif timeframe == "5 Anni" and len(df_filtered_prices) >= 252*5:
                    df_filtered_prices = df_filtered_prices.iloc[-252*5:]

                distinct_colors = ['#2563EB', '#16A34A', '#EA580C', '#9333EA', '#DC2626', '#0891B2', '#CA8A04']
                if len(active_tickers) == 1:
                    fig = px.line(df_filtered_prices, labels={"value": "Prezzo (€)", "index": "Data"})
                    fig.update_traces(line_color="#2563EB", line_width=1.8)
                else:
                    normalized_prices = (df_filtered_prices / df_filtered_prices.iloc[0]) * 100
                    fig = px.line(normalized_prices, labels={"value": "Indice (Base 100)", "index": "Data"}, color_discrete_sequence=distinct_colors)
                    fig.update_traces(line_width=1.8)

                fig.update_layout(
                    plot_bgcolor="white", paper_bgcolor="white",
                    font=dict(color="#475569", size=10),
                    margin=dict(l=10, r=10, t=10, b=10),
                    xaxis=dict(showgrid=True, gridcolor="#F1F5F9"),
                    yaxis=dict(showgrid=True, gridcolor="#F1F5F9"),
                    legend=dict(title_text='', orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.markdown("### Analisi Storica Completa e Dinamica")
            selected_tf = st.selectbox("Orizzonte temporale:", ["1 Mese", "3 Mesi", "6 Mesi", "1 Anno", "3 Anni", "5 Anni", "Tutto"], index=4)
            df_cycles = compute_dynamic_cycles(df_prices, selected_tf)
            if not df_cycles.empty:
                ret_col = f"Rendimento ({selected_tf})"
                def color_performance(val):
                    if isinstance(val, str):
                        if val.startswith('+'): return 'color: #16A34A; font-weight: 600;'
                        elif val.startswith('-'): return 'color: #DC2626; font-weight: 600;'
                    return ''
                st.dataframe(df_cycles.style.map(color_performance, subset=[ret_col]), use_container_width=True, hide_index=True)

        with tab3:
            st.markdown("### Analisi Opportunità di Pullback (Buy the Dip)")
            df_pullback = compute_pullback_opportunities(df_prices)

            if not df_pullback.empty:
                f_col1, f_col2 = st.columns(2)
                with f_col1:
                    max_distance_filter = st.slider("Distanza massima dai massimi:", -30.0, 0.0, -1.0, 0.5)
                with f_col2:
                    only_positive_trend = st.checkbox("Solo trend annuale positivo (> 0%)", value=True)

                filtered_pb = df_pullback[df_pullback["Distanza dai Massimi"] <= max_distance_filter]
                if only_positive_trend:
                    filtered_pb = filtered_pb[filtered_pb["Rend. 1 Anno"] > 0.0]

                if not filtered_pb.empty:
                    st.markdown(f"**Trovati {len(filtered_pb)} strumenti in ritracciamento utile:**")
                    display_pb = filtered_pb.copy()
                    display_pb["Prezzo Attuale"] = display_pb["Prezzo Attuale"].apply(lambda x: f"{x:.2f} €")
                    display_pb["Massimo Recente (6M)"] = display_pb["Massimo Recente (6M)"].apply(lambda x: f"{x:.2f} €")
                    display_pb["Distanza dai Massimi"] = display_pb["Distanza dai Massimi"].apply(lambda x: f"{x:+.2f}%")
                    display_pb["Rend. 3 Mesi"] = display_pb["Rend. 3 Mesi"].apply(lambda x: f"{x:+.2f}%")
                    display_pb["Rend. 1 Anno"] = display_pb["Rend. 1 Anno"].apply(lambda x: f"{x:+.2f}%")

                    def color_dist(val):
                        if isinstance(val, str):
                            num = float(val.replace('%', '').replace('+', ''))
                            if -15.0 <= num <= -2.0: return 'color: #16A34A; font-weight: 700; background-color: #F0FDF4;'
                            elif num < -15.0: return 'color: #D97706; font-weight: 600;'
                        return ''

                    st.dataframe(display_pb.style.map(color_dist, subset=["Distanza dai Massimi"]), use_container_width=True, hide_index=True)
                else:
                    st.info("Nessun ETF soddisfa i criteri attuali.")

                excluded_pb = df_pullback[~df_pullback.index.isin(filtered_pb.index)]
                if not excluded_pb.empty:
                    with st.expander(f"📌 Altri strumenti in portafoglio (Sui massimi o fuori soglia) ({len(excluded_pb)})"):
                        display_exc = excluded_pb.copy()
                        display_exc["Prezzo Attuale"] = display_exc["Prezzo Attuale"].apply(lambda x: f"{x:.2f} €")
                        display_exc["Massimo Recente (6M)"] = display_exc["Massimo Recente (6M)"].apply(lambda x: f"{x:.2f} €")
                        display_exc["Distanza dai Massimi"] = display_exc["Distanza dai Massimi"].apply(lambda x: f"{x:+.2f}%")
                        display_exc["Rend. 3 Mesi"] = display_exc["Rend. 3 Mesi"].apply(lambda x: f"{x:+.2f}%")
                        display_exc["Rend. 1 Anno"] = display_exc["Rend. 1 Anno"].apply(lambda x: f"{x:+.2f}%")
                        st.dataframe(display_exc, use_container_width=True, hide_index=True)

        with tab4:
            st.markdown("### 📘 Guida e Metriche")
            with st.expander("🎯 Come funziona l'Analisi dei Pullback"):
                st.markdown("Misura la distanza percentuale dai massimi degli ultimi 6 mesi per trovare sconti sani tra -2% e -15%.")
            with st.expander("📉 Analisi Cicli e Drawdown"):
                st.markdown("Monitora la tenuta storica e i crolli massimi su finestre temporali dinamiche.")
            with st.expander("🔄 Aggiornamento Dati"):
                st.markdown("I dati vengono aggiornati automaticamente in background ogni 15 minuti tramite Yahoo Finance.")
else:
    st.info("Seleziona almeno un ETF dalla barra laterale.")
