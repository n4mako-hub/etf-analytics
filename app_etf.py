import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import plotly.graph_objects as go
import requests

# Configurazione della pagina
st.set_page_config(
    page_title="ETF Performance Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 1. GESTIONE WATCHLIST IN MEMORIA (SESSION STATE) ---
DEFAULT_WATCHLIST = [
    {"ticker": "VWCE.DE", "name": "Vanguard FTSE All-World UCITS ETF", "category": "Azionario Globale", "isin": "IE00BK5BQT36", "ter": 0.22, "start_date": "2019-07-01"},
    {"ticker": "SWDA.MI", "name": "iShares Core MSCI World UCITS ETF", "category": "Azionario Globale", "isin": "IE00B4L5Y983", "ter": 0.20, "start_date": "2009-09-01"},
    {"ticker": "XEON.DE", "name": "Xtrackers II EUR Overnight Rate Swap", "category": "Monetario / Liquidità", "isin": "LU0290358497", "ter": 0.10, "start_date": "2008-01-01"}
]

if "user_watchlist" not in st.session_state:
    st.session_state.user_watchlist = DEFAULT_WATCHLIST

# --- FUNZIONE PER TROVARE IL TICKER TRAMITE ISIN ---
def find_ticker_by_isin(isin):
    try:
        url = "https://query1.finance.yahoo.com/v1/finance/search"
        headers = {'User-Agent': 'Mozilla/5.0'}
        params = {'q': isin, 'quotesCount': 1, 'newsCount': 0}
        resp = requests.get(url, headers=headers, params=params, timeout=5)
        data = resp.json()
        if 'quotes' in data and len(data['quotes']) > 0:
            quote = data['quotes'][0]
            return quote.get('symbol'), quote.get('shortname') or quote.get('longname')
    except Exception:
        pass
    return None, None

# --- 2. BARRA LATERALE: GESTIONE STRUMENTI ---
st.sidebar.header("📁 Gestione Watchlist")

with st.sidebar.expander("➕ Aggiungi Strumento"):
    with st.form("add_form_full"):
        input_isin = st.text_input("Inserisci ISIN (es. IE00BK5BQT36)").strip().upper()
        manual_ticker = st.text_input("Ticker Yahoo opzionale (se vuoto usa ISIN)").strip().upper()
        new_category = st.selectbox("Categoria", ["Azionario Globale", "Azionario Settoriale/Tematico", "Obbligazionario", "Monetario / Liquidità", "Commodities"])
        new_ter = st.number_input("TER (%)", min_value=0.0, max_value=5.0, value=0.20, step=0.01)
        new_start = st.text_input("Data Inizio (YYYY-MM-DD)", value="2020-01-01").strip()
        
        submitted = st.form_submit_button("Aggiungi alla lista")
        if submitted and input_isin:
            ticker_to_use = manual_ticker if manual_ticker else None
            name_to_use = None
            
            # Se non viene inserito il ticker manuale, cerchiamo con l'ISIN
            if not ticker_to_use:
                found_sym, found_name = find_ticker_by_isin(input_isin)
                if found_sym:
                    ticker_to_use = found_sym
                    name_to_use = found_name
                else:
                    ticker_to_use = input_isin # Fallback se l'API non risponde
                    name_to_use = f"ETF {input_isin}"
            
            if not name_to_use:
                name_to_use = ticker_to_use

            exists = any(item['ticker'] == ticker_to_use for item in st.session_state.user_watchlist)
            if not exists:
                st.session_state.user_watchlist.append({
                    "ticker": ticker_to_use,
                    "name": name_to_use,
                    "category": new_category,
                    "isin": input_isin,
                    "ter": new_ter,
                    "start_date": new_start
                })
                st.sidebar.success(f"Aggiunto {name_to_use} ({ticker_to_use})!")
                st.rerun()
            else:
                st.sidebar.warning("Strumento già presente nella lista.")

st.sidebar.markdown("---")
st.sidebar.subheader("Strumenti attivi nella sessione:")
for item in st.session_state.user_watchlist:
    col1, col2 = st.sidebar.columns([4, 1])
    col1.text(f"{item['name']} ({item['ticker']})")
    if col2.button("🗑️", key=f"del_{item['ticker']}"):
        st.session_state.user_watchlist = [x for x in st.session_state.user_watchlist if x['ticker'] != item['ticker']]
        st.rerun()

# --- 3. FUNZIONI DI SCARICAMENTO E CALCOLO DATI ---
@st.cache_data(ttl=3600)
def download_data(tickers, start_date):
    try:
        df = yf.download(tickers, start=start_date, progress=False)['Close']
        if isinstance(df, pd.Series):
            df = df.to_frame()
            df.columns = [tickers[0]]
        return df.dropna(how="all")
    except Exception as e:
        st.error(f"Errore nel download dei dati: {e}")
        return pd.DataFrame()

tickers_list = [item['ticker'] for item in st.session_state.user_watchlist]
earliest_date = min([item['start_date'] for item in st.session_state.user_watchlist]) if st.session_state.user_watchlist else "2020-01-01"

data = download_data(tickers_list, earliest_date)

# --- 4. CORPO PRINCIPALE DELL'APP ---
st.title("ETF Performance Analytics")
st.markdown("Dashboard avanzata per l'analisi dei portafogli ETF. *Sessione utente isolata.*")

if data.empty or not tickers_list:
    st.warning("Nessun dato disponibile o watchlist vuota. Aggiungi almeno uno strumento dalla barra laterale.")
else:
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Performance e Grafici", "📉 Analisi Cicli & Drawdown", "🎯 Opportunità di Pullback", "ℹ️ Guida e Metriche"])
    
    with tab1:
        st.subheader("Rendimenti e Performance Storiche")
        
        col_f1, col_f2 = st.columns([2, 6])
        with col_f1:
            time_horizon = st.radio("Orizzonte temporale grafico:", ["1 Anno", "3 Anni", "5 Anni", "Tutto"], horizontal=True)
        
        end_date_val = datetime.date.today()
        if time_horizon == "1 Anno":
            start_date_val = end_date_val - datetime.timedelta(days=365)
        elif time_horizon == "3 Anni":
            start_date_val = end_date_val - datetime.timedelta(days=365*3)
        elif time_horizon == "5 Anni":
            start_date_val = end_date_val - datetime.timedelta(days=365*5)
        else:
            start_date_val = pd.to_datetime(earliest_date).date()
            
        plot_data = data[data.index >= pd.to_datetime(start_date_val)]
        
        if not plot_data.empty:
            norm_data = plot_data.div(plot_data.iloc[0]) * 100
            
            fig = go.Figure()
            for col in norm_data.columns:
                item_info = next((i for i in st.session_state.user_watchlist if i['ticker'] == col), None)
                label = item_info['name'] if item_info else col
                fig.add_trace(go.Scatter(x=norm_data.index, y=norm_data[col], mode='lines', name=label))
                
            fig.update_layout(
                title="Andamento Storico Normalizzato (Base 100)",
                xaxis_title="Data",
                yaxis_title="Indice (Base 100)",
                template="plotly_white",
                height=500,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)
            
        summary_rows = []
        for item in st.session_state.user_watchlist:
            t = item['ticker']
            if t in data.columns:
                series = data[t].dropna()
                if not series.empty:
                    ultimo_prezzo = series.iloc[-1]
                    
                    def get_perf(days):
                        target_date = series.index[-1] - datetime.timedelta(days=days)
                        filtered = series[series.index >= target_date]
                        if not filtered.empty:
                            return ((series.iloc[-1] / filtered.iloc[0]) - 1) * 100
                        return np.nan

                    ytd_val = get_perf((datetime.date.today() - datetime.date(datetime.date.today().year, 1, 1)).days)
                    y1_val = get_perf(365)
                    y3_val = get_perf(365 * 3)
                    
                    summary_rows.append({
                        "Strumento": item['name'],
                        "Ticker": t,
                        "Categoria": item['category'],
                        "ISIN": item['isin'],
                        "TER (%)": item['ter'],
                        "Ultimo (€)": f"{ultimo_prezzo:.2f} €",
                        "YTD (%)": f"{ytd_val:+.2f}%" if not np.isnan(ytd_val) else "N/D",
                        "1 Anno (%)": f"{y1_val:+.2f}%" if not np.isnan(y1_val) else "N/D",
                        "3 Anni Ann. (%)": f"{y3_val:+.2f}%" if not np.isnan(y3_val) else "N/D",
                    })
                    
        if summary_rows:
            df_summary = pd.DataFrame(summary_rows)
            st.dataframe(df_summary, use_container_width=True)

    with tab2:
        st.subheader("📉 Analisi Drawdown Storico")
        st.write("Il drawdown misura la perdita percentuale massima dai massimi storici registrati nel periodo.")
        
        if not data.empty:
            rolling_max = data.cummax()
            drawdown = (data - rolling_max) / rolling_max * 100
            
            fig_dd = go.Figure()
            for col in drawdown.columns:
                item_info = next((i for i in st.session_state.user_watchlist if i['ticker'] == col), None)
                label = item_info['name'] if item_info else col
                fig_dd.add_trace(go.Scatter(x=drawdown.index, y=drawdown[col], mode='lines', name=label, fill='tozeroy'))
                
            fig_dd.update_layout(
                title="Profondità dei Drawdown (%)",
                xaxis_title="Data",
                yaxis_title="Drawdown (%)",
                template="plotly_white",
                height=450
            )
            st.plotly_chart(fig_dd, use_container_width=True)

    with tab3:
        st.subheader("🎯 Opportunità di Pullback dai Massimi")
        st.write("Monitoraggio della distanza attuale dei singoli ETF rispetto ai loro massimi recenti.")
        
        pullback_rows = []
        for item in st.session_state.user_watchlist:
            t = item['ticker']
            if t in data.columns:
                series = data[t].dropna()
                if not series.empty:
                    max_val = series.max()
                    current_val = series.iloc[-1]
                    dist_from_max = ((current_val / max_val) - 1) * 100
                    pullback_rows.append({
                        "Strumento": item['name'],
                        "Ticker": t,
                        "Prezzo Attuale": f"{current_val:.2f} €",
                        "Massimo Storico": f"{max_val:.2f} €",
                        "Distanza dal Massimo (%)": f"{dist_from_max:.2f}%"
                    })
        if pullback_rows:
            st.dataframe(pd.DataFrame(pullback_rows), use_container_width=True)

    with tab4:
        st.subheader("ℹ️ Informazioni sulla Modalità di Utilizzo")
        st.markdown("""
        * **Ricerca Automatica da ISIN:** Inserendo l'ISIN, l'app interroga Yahoo Finance per ricavare in automatico il ticker e il nome dello strumento.
        * **Sessione Isolata:** Questa versione dell'applicazione gestisce la tua watchlist in memoria temporanea.
        * **Nessun Dato Persistente Condiviso:** Le modifiche che fai tu non impattano gli altri utenti che aprono il link.
        """)
