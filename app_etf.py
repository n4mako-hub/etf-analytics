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

# 1. Configurazione Pagina e Styling CSS (Minimal & Monochromatic)
st.set_page_config(page_title="ETF Analytics & Portfolio Tracker", layout="wide")

# NOTA TECNICA IMPORTANTE: st.rerun() non viene MAI chiamato direttamente a metà
# script. Chiamarlo prima che un widget con stato persistente (es. il radio
# "Sezione: ETF/Crypto") sia stato istanziato in questo stesso giro di esecuzione
# fa perdere il suo valore salvato al giro successivo, anche con una key esplicita
# (comportamento sottile di Streamlit, verificato con un test isolato). Per questo,
# ogni azione che richiederebbe un rerun si limita a impostare questo flag; il
# rerun vero e proprio avviene solo alla fine dello script, quando ogni widget
# della pagina e' gia' stato renderizzato almeno una volta in questo giro.
if "_needs_rerun" not in st.session_state:
    st.session_state._needs_rerun = False

# NOTA: l'auto-refresh periodico è stato rimosso: i dati di mercato ora si
# aggiornano SOLO quando l'utente clicca esplicitamente "Aggiorna Dati".

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

    /* --- Overlay di caricamento centrato con puntini che sobbalzano --- */
    .center-loading-overlay {
        position: fixed;
        top: 0; left: 0; width: 100vw; height: 100vh;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        background: rgba(255, 255, 255, 0.85);
        z-index: 9999;
    }
    .center-loading-dots { display: flex; gap: 10px; margin-bottom: 14px; }
    .center-loading-dots span {
        width: 16px; height: 16px; border-radius: 50%;
        background-color: #2563EB;
        animation: center-loading-bounce 1.1s infinite ease-in-out both;
    }
    .center-loading-dots span:nth-child(1) { animation-delay: -0.28s; }
    .center-loading-dots span:nth-child(2) { animation-delay: -0.14s; }
    .center-loading-dots span:nth-child(3) { animation-delay: 0s; }
    @keyframes center-loading-bounce {
        0%, 80%, 100% { transform: scale(0.4); opacity: 0.5; }
        40% { transform: scale(1); opacity: 1; }
    }
    .center-loading-text { color: #475569; font-size: 0.95rem; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

def show_center_loading(text="Caricamento in corso..."):
    """Mostra un overlay a schermo intero con puntini animati al centro,
    al posto della classica clessidra in alto a sinistra di st.spinner."""
    placeholder = st.empty()
    placeholder.markdown(f"""
        <div class="center-loading-overlay">
            <div class="center-loading-dots"><span></span><span></span><span></span></div>
            <div class="center-loading-text">{text}</div>
        </div>
    """, unsafe_allow_html=True)
    return placeholder

st.title("ETF Performance Analytics")
col_refresh, col_refresh_spacer = st.columns([0.28, 0.72])
with col_refresh:
    refresh_clicked = st.button("Aggiorna Dati", use_container_width=True, help="Applica le spunte Attivo/TER modificate in tabella e ricarica prezzi e indicatori da Yahoo Finance. Nessun aggiornamento avviene finché non lo clicchi.")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WATCHLIST_FILE = os.path.join(BASE_DIR, "watchlist.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

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

# Testi informativi (tooltip) mostrati passando il mouse sulle intestazioni delle
# colonne in tabella. Riprendono le spiegazioni della tab "Guida e Metriche".
METRIC_TOOLTIPS = {
    "TER (%)": "Costo annuo di gestione trattenuto dall'emittente. Es: 0.20% su 10.000€ investiti ≈ 20€/anno. Ottimo <0.20%, medio 0.20-0.50%, alto >0.50%.",
    "Investito (€)": "Capitale totale investito: somma di tutti i carichi (acquisti) registrati per questo ETF in 'Gestione Carichi'.",
    "Prezzo Carico (€)": "Prezzo medio ponderato di acquisto, calcolato su tutti i carichi registrati per questo ETF.",
    "Data Acquisto": "Data del primo carico (acquisto) registrato per questo ETF.",
    "Valore Attuale (€)": "Valore di mercato attuale della posizione, in base all'ultimo prezzo disponibile.",
    "Profitto/Perdita (€)": "Guadagno o perdita in euro rispetto al capitale investito (prezzo medio di carico).",
    "Profitto/Perdita (%)": "Guadagno o perdita percentuale rispetto al capitale investito (prezzo medio di carico).",
    "Ultimo (€)": "Ultimo prezzo di chiusura disponibile per lo strumento.",
    "YTD (%)": "Rendimento da inizio anno (Year To Date).",
    "1 Anno (%)": "Rendimento degli ultimi 12 mesi.",
    "Volatilità 1A": "Oscillazione annualizzata del prezzo negli ultimi 12 mesi. Bassa <8% (monetari/obbligazionari brevi), media 10-18% (azionari diversificati), alta >20% (settoriali, emergenti, materie prime).",
    "Sharpe 1A": "Rendimento in eccesso ottenuto rispetto a un investimento privo di rischio, rapportato alla volatilità. Attorno a 1.0 = buono, >1.5/2.0 = eccellente, <=0 = ha reso meno della liquidità.",
    "Sortino 1A": "Come lo Sharpe, ma penalizza solo la volatilità al ribasso (le perdite), non quella al rialzo. Valori >1.0 indicano buona gestione del rischio di perdita.",
    "SMA200": "Posizione del prezzo rispetto alla media mobile a 200 giorni: 🟢 ▲ = sopra (trend di fondo rialzista), 🔴 ▼ = sotto (trend ribassista).",
    "RSI (14)": "Oscillatore di momentum (0-100) calcolato su 14 periodi. >70 = ipercomprato, <30 = ipervenduto.",
    "Storno dai Massimi (%)": "Quanto il prezzo attuale è sceso rispetto al massimo storico (o del periodo considerato).",
}

def _tcol(colname, display_name=None, **kwargs):
    """Crea una TextColumn con il tooltip di METRIC_TOOLTIPS già applicato, se disponibile."""
    return st.column_config.TextColumn(
        display_name or colname,
        help=kwargs.pop("help", METRIC_TOOLTIPS.get(colname)),
        **kwargs
    )

def parse_custom_date(date_str):
    if not date_str or str(date_str).strip() == "":
        return pd.NaT
    s = str(date_str).strip()
    parts = s.replace('/', '.').replace('-', '.').split('.')
    if len(parts) == 3 and len(parts[2]) == 2:
        parts[2] = '20' + parts[2]
        s = f"{parts[0]}.{parts[1]}.{parts[2]}"
    return pd.to_datetime(s, errors='coerce', dayfirst=True)

def compute_lot_summary(lots):
    """Dato un elenco di carichi [{'date','price','amount'}], ritorna
    (totale investito €, prezzo medio ponderato di carico, data del primo carico)."""
    if not lots:
        return 0.0, 0.0, ""
    total_invested = sum(float(l.get("amount", 0.0)) for l in lots)
    total_quantity = sum(
        float(l.get("amount", 0.0)) / float(l.get("price", 0.0))
        for l in lots if float(l.get("price", 0.0)) > 0
    )
    avg_price = (total_invested / total_quantity) if total_quantity > 0 else 0.0

    def _sort_key(l):
        d = parse_custom_date(l.get("date", ""))
        return d if pd.notna(d) else pd.Timestamp.max
    dated_lots = sorted(lots, key=_sort_key)
    first_date = dated_lots[0].get("date", "") if dated_lots else ""
    return total_invested, avg_price, first_date

def _migrate_watchlist_entry(entry):
    """Garantisce che ogni ETF abbia una lista 'lots' e ricalcola i campi
    aggregati (investito/prezzo medio/data primo carico) a partire da essa."""
    if "ter" not in entry: entry["ter"] = 0.0
    if "active" not in entry: entry["active"] = True
    if "invested_amount" not in entry: entry["invested_amount"] = 0.0
    if "buy_price" not in entry: entry["buy_price"] = 0.0
    if "buy_date" not in entry: entry["buy_date"] = ""

    if "lots" not in entry or not isinstance(entry["lots"], list):
        legacy_lots = []
        if float(entry.get("invested_amount", 0.0)) > 0 and float(entry.get("buy_price", 0.0)) > 0:
            legacy_lots.append({
                "date": entry.get("buy_date", ""),
                "price": float(entry.get("buy_price", 0.0)),
                "amount": float(entry.get("invested_amount", 0.0))
            })
        entry["lots"] = legacy_lots

    total_inv, avg_price, first_date = compute_lot_summary(entry["lots"])
    entry["invested_amount"] = total_inv
    entry["buy_price"] = avg_price
    entry["buy_date"] = first_date
    return entry

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k in data:
                    data[k] = _migrate_watchlist_entry(data[k])
                return data
        except Exception as e:
            st.sidebar.error(f"Errore nella lettura di watchlist.json ({e}). Uso la watchlist di default.")
    else:
        st.sidebar.warning(f"File watchlist.json non trovato in:\n`{WATCHLIST_FILE}`\n\nSto usando la watchlist di default. Copia il tuo watchlist.json in questa cartella (quella dello script) e ricarica la pagina.")
    default_copy = json.loads(json.dumps(DEFAULT_WATCHLIST))
    for k in default_copy:
        default_copy[k] = _migrate_watchlist_entry(default_copy[k])
    return default_copy

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
        except Exception as e:
            st.sidebar.error(f"Errore nella lettura di settings.json ({e}). Uso le impostazioni di default.")
    return {"selected_tab1_cols": default_tab1_cols.copy()}

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"Errore nel salvataggio impostazioni: {e}")

def commit_pending_table_edits():
    """Applica alla watchlist reale (e salva su disco) le modifiche Attivo/TER
    tenute in sospeso in st.session_state.pending_table_edits, poi svuota lo
    staging. Va chiamata quando l'utente clicca 'Aggiorna Dati' o 'Salva
    Modifiche Tabella'."""
    pending = st.session_state.get("pending_table_edits", {})
    if not pending:
        return
    for tk, changes in pending.items():
        if tk not in st.session_state.watchlist:
            continue
        if "active" in changes:
            st.session_state.watchlist[tk]["active"] = bool(changes["active"])
        if "ter" in changes:
            st.session_state.watchlist[tk]["ter"] = float(changes["ter"])
    save_watchlist(st.session_state.watchlist)
    st.session_state.pending_table_edits = {}

if "pending_table_edits" not in st.session_state:
    st.session_state.pending_table_edits = {}

if "watchlist" not in st.session_state:
    st.session_state.watchlist = load_watchlist()

if "focus_ticker" not in st.session_state:
    st.session_state.focus_ticker = None

if "chart_type_radio" not in st.session_state:
    st.session_state.chart_type_radio = "Linee (Normalizzato)"

if "market_data" not in st.session_state:
    st.session_state.market_data = None  # (df_metrics, df_prices, df_ohlc) in cache

if "last_data_update" not in st.session_state:
    st.session_state.last_data_update = None

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
st.sidebar.caption(f"Cartella dati: `{BASE_DIR}`")

with st.sidebar.expander("+ Aggiungi ETF", expanded=False):
    with st.form(key="add_isin_form", clear_on_submit=True):
        isin_input = st.text_input("Codice ISIN o Ticker", placeholder="es. IE00B4L5Y983")
        submit_button = st.form_submit_button(label="Aggiungi", use_container_width=True)

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
                        "buy_date": "",
                        "lots": [],
                        "asset_type": "ETF"
                    }
                    save_watchlist(st.session_state.watchlist)
                    st.session_state.market_data = None
                    st.sidebar.success("Aggiunto e salvato. Clicca 'Aggiorna Dati' per includerlo nell'analisi.")
                    st.session_state._needs_rerun = True
                else:
                    st.sidebar.error("Strumento non trovato.")

POPULAR_CRYPTOS = {
    "Bitcoin (BTC)": "BTC-EUR", "Ethereum (ETH)": "ETH-EUR", "Solana (SOL)": "SOL-EUR",
    "XRP": "XRP-EUR", "Cardano (ADA)": "ADA-EUR", "Dogecoin (DOGE)": "DOGE-EUR",
    "BNB": "BNB-EUR", "Chainlink (LINK)": "LINK-EUR", "Polkadot (DOT)": "DOT-EUR",
    "Litecoin (LTC)": "LTC-EUR",
}

with st.sidebar.expander("+ Aggiungi Crypto", expanded=False):
    st.caption("Le criptovalute usano ticker Yahoo Finance nel formato SIMBOLO-VALUTA (es. BTC-EUR).")
    quick_pick = st.selectbox("Scelta rapida", ["-- nessuna --"] + list(POPULAR_CRYPTOS.keys()), key="crypto_quick_pick")
    with st.form(key="add_crypto_form", clear_on_submit=True):
        default_crypto_ticker = POPULAR_CRYPTOS.get(quick_pick, "")
        crypto_ticker_input = st.text_input(
            "Ticker Crypto (Yahoo Finance)",
            value=default_crypto_ticker,
            placeholder="es. BTC-EUR, ETH-USD"
        )
        submit_crypto_button = st.form_submit_button(label="Aggiungi", use_container_width=True)

    if submit_crypto_button:
        clean_crypto = crypto_ticker_input.strip().upper()
        if clean_crypto:
            with st.spinner("Verifica ticker su Yahoo Finance..."):
                try:
                    crypto_info = yf.Ticker(clean_crypto).info
                    crypto_name = crypto_info.get("longName") or crypto_info.get("shortName") or clean_crypto
                    crypto_hist_check = yf.Ticker(clean_crypto).history(period="5d")
                    crypto_found = not crypto_hist_check.empty
                except Exception:
                    crypto_name = clean_crypto
                    crypto_found = False

            if crypto_found:
                st.session_state.watchlist[clean_crypto] = {
                    "name": crypto_name,
                    "isin": clean_crypto,
                    "active": True,
                    "ter": 0.0,
                    "invested_amount": 0.0,
                    "buy_price": 0.0,
                    "buy_date": "",
                    "lots": [],
                    "asset_type": "CRYPTO"
                }
                save_watchlist(st.session_state.watchlist)
                st.session_state.market_data = None
                st.sidebar.success("Aggiunta e salvata. Clicca 'Aggiorna Dati' per includerla nell'analisi.")
                st.session_state._needs_rerun = True
            else:
                st.sidebar.error(f"Ticker '{clean_crypto}' non trovato su Yahoo Finance. Controlla il formato (es. BTC-EUR).")

st.sidebar.markdown("---")

st.sidebar.markdown("### Portafoglio Personale")
portfolio_items = [(tk, inf) for tk, inf in st.session_state.watchlist.items() if inf.get("invested_amount", 0.0) > 0 and inf.get("buy_price", 0.0) > 0]

if portfolio_items:
    total_inv_sidebar = sum(inf["invested_amount"] for tk, inf in portfolio_items)
    st.sidebar.markdown(f"**Totale Investito:** `{total_inv_sidebar:,.2f} €`")
    
    if st.session_state.focus_ticker:
        focus_name = st.session_state.watchlist.get(st.session_state.focus_ticker, {}).get("name", st.session_state.focus_ticker)
        if st.sidebar.button(f"Focalizzato: {focus_name[:12]}... [Reset]", use_container_width=True):
            st.session_state.focus_ticker = None
            st.session_state._needs_rerun = True

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
            st.session_state._needs_rerun = True
            
        date_str = f" ({inf['buy_date']})" if inf.get('buy_date') else ""
        st.sidebar.markdown(f"<small style='color: #475569; margin-left: 25px;'>Inv: **{inf['invested_amount']:,.2f}€** | Carico medio: **{inf['buy_price']:.4f}€**{date_str}</small>", unsafe_allow_html=True)

        etf_lots = inf.get("lots", [])
        if etf_lots:
            df_lots_sb = pd.DataFrame(etf_lots)
            df_lots_sb["quantità"] = df_lots_sb.apply(lambda r: (r["amount"] / r["price"]) if r["price"] > 0 else 0.0, axis=1)
            df_lots_sb = df_lots_sb.rename(columns={"date": "Data", "price": "Prezzo Carico (€)", "amount": "Importo Investito (€)", "quantità": "Quantità"})
            csv_sb = df_lots_sb[["Data", "Prezzo Carico (€)", "Importo Investito (€)", "Quantità"]].to_csv(index=False).encode("utf-8-sig")
            st.sidebar.download_button(
                label="Esporta storico",
                data=csv_sb,
                file_name=f"storico_{tk}.csv",
                mime="text/csv",
                key=f"export_sb_{tk}",
                use_container_width=True
            )
        st.sidebar.markdown("")

    if portfolio_state_changed:
        save_watchlist(st.session_state.watchlist)
        st.session_state._needs_rerun = True
else:
    st.sidebar.info("Nessun ETF con dati di acquisto inseriti.")

st.sidebar.markdown("---")
st.sidebar.markdown("### Lista ETF e Selezione")
selection_scope = st.sidebar.radio("Ambito selezione:", ["Tutto", "Solo ETF", "Solo Crypto"], horizontal=True, key="selection_scope_radio")
search_query = st.sidebar.text_input("Filtra rapido:", placeholder="cerca nome o ISIN...")

def _scope_tickers():
    """Ritorna i ticker della watchlist compresi nell'ambito (Tutto/Solo ETF/Solo Crypto) selezionato."""
    if selection_scope == "Solo ETF":
        return [tk for tk, inf in st.session_state.watchlist.items() if inf.get("asset_type", "ETF") == "ETF"]
    elif selection_scope == "Solo Crypto":
        return [tk for tk, inf in st.session_state.watchlist.items() if inf.get("asset_type", "ETF") == "CRYPTO"]
    return list(st.session_state.watchlist.keys())

col_b1, col_b2, col_b3 = st.sidebar.columns(3)

def _clear_pending_active_edits():
    """Rimuove dallo staging delle modifiche 'Attivo' non ancora salvate
    (pending_table_edits) qualsiasi valore residuo, così una selezione
    massiva (Tutti/Nessun/Top 5) non viene subito sovrascritta in tabella
    da una spunta manuale fatta in precedenza e non ancora salvata.
    I pending TER (%) eventuali vengono invece preservati."""
    for tk in list(st.session_state.pending_table_edits.keys()):
        st.session_state.pending_table_edits[tk].pop("active", None)
        if not st.session_state.pending_table_edits[tk]:
            del st.session_state.pending_table_edits[tk]

if col_b1.button("Tutti", use_container_width=True):
    for tk in _scope_tickers():
        st.session_state.watchlist[tk]["active"] = True
        if f"chk_{tk}" in st.session_state:
            st.session_state[f"chk_{tk}"] = True
    _clear_pending_active_edits()
    save_watchlist(st.session_state.watchlist)
    st.session_state._needs_rerun = True

if col_b2.button("Nessun", use_container_width=True):
    for tk in _scope_tickers():
        st.session_state.watchlist[tk]["active"] = False
        if f"chk_{tk}" in st.session_state:
            st.session_state[f"chk_{tk}"] = False
    _clear_pending_active_edits()
    save_watchlist(st.session_state.watchlist)
    st.session_state._needs_rerun = True

if col_b3.button("Top 5", use_container_width=True):
    performance_scores = {}
    for tk in _scope_tickers():
        try:
            tk_obj = yf.Ticker(tk)
            data = tk_obj.history(period="max")['Close'].dropna()
            if len(data) > 0:
                performance_scores[tk] = ((data.iloc[-1] - data.iloc[0]) / data.iloc[0]) * 100
        except Exception:
            pass
    sorted_top = sorted(performance_scores.items(), key=lambda x: x[1], reverse=True)
    top_5_tickers = [item[0] for item in sorted_top[:5]]
    for tk in _scope_tickers():
        is_top5 = (tk in top_5_tickers)
        st.session_state.watchlist[tk]["active"] = is_top5
        if f"chk_{tk}" in st.session_state:
            st.session_state[f"chk_{tk}"] = is_top5
    _clear_pending_active_edits()
    save_watchlist(st.session_state.watchlist)
    st.session_state._needs_rerun = True

st.sidebar.markdown("")

grouped_watchlist = {}
for ticker, info in st.session_state.watchlist.items():
    if ticker not in _scope_tickers():
        continue
    name = info["name"]
    isin = info.get("isin", "")
    if search_query.strip():
        q = search_query.strip().upper()
        if not (q in ticker.upper() or q in name.upper() or q in isin.upper()):
            continue
    cat = detect_category(name, {})
    asset_badge = "🪙 Crypto" if info.get("asset_type", "ETF") == "CRYPTO" else "📊 ETF"
    group_key = f"{asset_badge} — {cat}" if selection_scope == "Tutto" else cat
    if group_key not in grouped_watchlist:
        grouped_watchlist[group_key] = []
    grouped_watchlist[group_key].append((ticker, info))

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
                    st.session_state._needs_rerun = True

if state_changed:
    save_watchlist(st.session_state.watchlist)
    st.session_state._needs_rerun = True

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

def _pct_change_n(series, n):
    """Variazione percentuale tra l'ultimo valore e quello di n barre prima."""
    if len(series) > n:
        base = series.iloc[-n - 1]
        if base:
            return float((series.iloc[-1] - base) / base * 100)
    return None

def compute_strategic_snapshot(df_full_c):
    """Calcola, sull'intero storico disponibile per uno strumento (df_full_c: colonne
    Open/High/Low/Close/Volume), lo stato PIU' RECENTE dei principali indicatori tecnici:
    SMA 20/50/200, RSI 14, MACD (12,26,9), Bande di Bollinger (20,2), un VWAP 'a breve'
    (ultime 20 sedute) e il range Fibonacci sull'ultimo anno. E' indipendente dagli
    interruttori SMA/Bollinger/ecc. che l'utente attiva o meno sul grafico: le
    indicazioni strategiche usano sempre lo stesso set standard, per coerenza.
    Ritorna None se lo storico disponibile è troppo corto per un'analisi minima."""
    close = df_full_c['Close'].dropna()
    if close.empty or len(close) < 15:
        return None

    last_close = float(close.iloc[-1])

    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()

    rsi14 = calculate_rsi_series(close, 14)

    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd_line = exp1 - exp2
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - macd_signal

    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + bb_std * 2
    bb_lower = bb_mid - bb_std * 2

    # VWAP 'a breve termine': ponderato sui volumi delle ultime 20 sedute. Non è un
    # VWAP di sessione intraday (dati non disponibili qui), ma una media ponderata a
    # breve termine, utile come riferimento della pressione compratori/venditori recente.
    vwap_short = None
    if 'Volume' in df_full_c.columns and df_full_c['Volume'].fillna(0).sum() > 0:
        window = df_full_c.tail(20)
        typical = (window['High'] + window['Low'] + window['Close']) / 3
        vol = window['Volume'].fillna(0)
        if vol.sum() > 0:
            vwap_short = float((typical * vol).sum() / vol.sum())

    # Fibonacci sull'ultimo anno (o su tutto lo storico se più corto)
    fib_window = df_full_c.tail(252) if len(df_full_c) >= 252 else df_full_c
    fib_max = fib_window['High'].max()
    fib_min = fib_window['Low'].min()

    def _last(s):
        v = s.iloc[-1] if not s.empty else None
        return float(v) if v is not None and pd.notna(v) else None

    return {
        "last_close": last_close,
        "sma20": _last(sma20), "sma50": _last(sma50), "sma200": _last(sma200),
        "rsi14": _last(rsi14),
        "macd_line": _last(macd_line), "macd_signal": _last(macd_signal),
        "macd_hist": _last(macd_hist), "macd_hist_prev": _last(macd_hist.shift(3)),
        "bb_upper": _last(bb_upper), "bb_lower": _last(bb_lower),
        "vwap_short": vwap_short,
        "fib_max": float(fib_max) if pd.notna(fib_max) else None,
        "fib_min": float(fib_min) if pd.notna(fib_min) else None,
        "ret_3m": _pct_change_n(close, 63),
        "ret_12m": _pct_change_n(close, 252),
    }

def generate_strategic_signals(snap):
    """Trasforma lo snapshot indicatori in 3 giudizi (Breve/Medio/Lungo termine) + una
    sintesi complessiva. Ogni giudizio è una somma di punti (+1 rialzista / -1
    ribassista / 0 neutro/non disponibile) assegnati da regole tecniche standard,
    normalizzata in una frazione -1..+1 e tradotta in etichetta/colore.
    E' un'analisi puramente tecnica sui soli prezzi storici (nessuna AI generativa
    coinvolta in questo calcolo): NON è un consiglio di investimento personalizzato."""

    def bucket(frac):
        if frac >= 0.5: return ("Ingresso interessante", "#16A34A", "▲▲")
        if frac >= 0.15: return ("Lieve propensione rialzista", "#65A30D", "▲")
        if frac > -0.15: return ("Neutro — attendere conferma", "#64748B", "▬")
        if frac > -0.5: return ("Lieve propensione ribassista", "#EA580C", "▼")
        return ("Segnali di debolezza", "#DC2626", "▼▼")

    last = snap["last_close"]

    # --- BREVE TERMINE (giorni/poche settimane): RSI, MACD hist, Bollinger, VWAP breve ---
    short_points, short_notes = [], []
    if snap["rsi14"] is not None:
        r = snap["rsi14"]
        if r < 30:
            short_points.append(1); short_notes.append(f"RSI({r:.0f}) in ipervenduto: possibile rimbalzo")
        elif r > 70:
            short_points.append(-1); short_notes.append(f"RSI({r:.0f}) in ipercomprato: possibile storno")
        else:
            short_points.append(0); short_notes.append(f"RSI({r:.0f}) in zona neutra")
    if snap["macd_hist"] is not None and snap["macd_hist_prev"] is not None:
        h, hp = snap["macd_hist"], snap["macd_hist_prev"]
        if h > 0 and h >= hp:
            short_points.append(1); short_notes.append("Istogramma MACD positivo e in espansione: momentum rialzista")
        elif h < 0 and h <= hp:
            short_points.append(-1); short_notes.append("Istogramma MACD negativo e in espansione: momentum ribassista")
        else:
            short_points.append(0); short_notes.append("Istogramma MACD in fase di transizione")
    if snap["bb_upper"] is not None and snap["bb_lower"] is not None:
        if last <= snap["bb_lower"]:
            short_points.append(1); short_notes.append("Prezzo sulla/oltre la banda di Bollinger inferiore: possibile ipervenduto")
        elif last >= snap["bb_upper"]:
            short_points.append(-1); short_notes.append("Prezzo sulla/oltre la banda di Bollinger superiore: possibile ipercomprato")
        else:
            short_points.append(0); short_notes.append("Prezzo all'interno delle Bande di Bollinger")
    if snap["vwap_short"] is not None:
        if last > snap["vwap_short"]:
            short_points.append(1); short_notes.append("Prezzo sopra il VWAP a breve: pressione compratori")
        else:
            short_points.append(-1); short_notes.append("Prezzo sotto il VWAP a breve: pressione venditori")
    short_frac = sum(short_points) / len(short_points) if short_points else 0.0

    # --- MEDIO TERMINE (settimane/mesi): prezzo vs SMA50, MACD linea vs segnale, momentum 3M ---
    med_points, med_notes = [], []
    if snap["sma50"] is not None:
        if last > snap["sma50"]:
            med_points.append(1); med_notes.append("Prezzo sopra la SMA50: trend di medio termine positivo")
        else:
            med_points.append(-1); med_notes.append("Prezzo sotto la SMA50: trend di medio termine negativo")
    if snap["macd_line"] is not None and snap["macd_signal"] is not None:
        if snap["macd_line"] > snap["macd_signal"]:
            med_points.append(1); med_notes.append("MACD sopra la linea di segnale: momentum a favore")
        else:
            med_points.append(-1); med_notes.append("MACD sotto la linea di segnale: momentum contrario")
    if snap["ret_3m"] is not None:
        if snap["ret_3m"] > 0:
            med_points.append(1); med_notes.append(f"Rendimento ultimi 3 mesi positivo ({snap['ret_3m']:+.1f}%)")
        else:
            med_points.append(-1); med_notes.append(f"Rendimento ultimi 3 mesi negativo ({snap['ret_3m']:+.1f}%)")
    med_frac = sum(med_points) / len(med_points) if med_points else 0.0

    # --- LUNGO TERMINE (mesi/anni): prezzo vs SMA200, Golden/Death Cross, momentum 12M ---
    long_points, long_notes = [], []
    if snap["sma200"] is not None:
        if last > snap["sma200"]:
            long_points.append(1); long_notes.append("Prezzo sopra la SMA200: trend di lungo termine rialzista")
        else:
            long_points.append(-1); long_notes.append("Prezzo sotto la SMA200: trend di lungo termine ribassista")
    if snap["sma50"] is not None and snap["sma200"] is not None:
        if snap["sma50"] > snap["sma200"]:
            long_points.append(1); long_notes.append("SMA50 sopra SMA200 (contesto Golden Cross): struttura di fondo positiva")
        else:
            long_points.append(-1); long_notes.append("SMA50 sotto SMA200 (contesto Death Cross): struttura di fondo negativa")
    if snap["ret_12m"] is not None:
        if snap["ret_12m"] > 0:
            long_points.append(1); long_notes.append(f"Rendimento ultimi 12 mesi positivo ({snap['ret_12m']:+.1f}%)")
        else:
            long_points.append(-1); long_notes.append(f"Rendimento ultimi 12 mesi negativo ({snap['ret_12m']:+.1f}%)")
    long_frac = sum(long_points) / len(long_points) if long_points else 0.0

    horizons = {
        "Breve termine": {"frac": short_frac, "notes": short_notes, **dict(zip(["label", "color", "icon"], bucket(short_frac)))},
        "Medio termine": {"frac": med_frac, "notes": med_notes, **dict(zip(["label", "color", "icon"], bucket(med_frac)))},
        "Lungo termine": {"frac": long_frac, "notes": long_notes, **dict(zip(["label", "color", "icon"], bucket(long_frac)))},
    }

    # Il lungo termine pesa doppio nella sintesi complessiva (impostazione da 'cassettista':
    # i segnali di breve termine sono più rumorosi e meno indicativi per decidere se entrare).
    overall_frac = (short_frac + med_frac + 2 * long_frac) / 4
    overall_label, overall_color, overall_icon = bucket(overall_frac)

    fib_note = None
    if snap["fib_max"] is not None and snap["fib_min"] is not None and snap["fib_max"] > snap["fib_min"]:
        rng = snap["fib_max"] - snap["fib_min"]
        levels = {
            "0% (Massimo)": snap["fib_max"],
            "23.6%": snap["fib_max"] - 0.236 * rng,
            "38.2%": snap["fib_max"] - 0.382 * rng,
            "50%": snap["fib_max"] - 0.5 * rng,
            "61.8%": snap["fib_max"] - 0.618 * rng,
            "100% (Minimo)": snap["fib_min"],
        }
        nearest_label = min(levels, key=lambda k: abs(levels[k] - last))
        fib_note = (
            f"Il prezzo attuale è vicino al livello di ritracciamento Fibonacci {nearest_label} "
            f"({levels[nearest_label]:.2f}€), calcolato sull'ultimo anno: livelli come questo sono "
            f"spesso osservati come area di supporto/resistenza."
        )

    return {
        "horizons": horizons,
        "overall_frac": overall_frac, "overall_label": overall_label,
        "overall_color": overall_color, "overall_icon": overall_icon,
        "fib_note": fib_note,
    }

def calculate_atr_series(df, period=14):
    """Average True Range: misura di volatilità media giornaliera, usata per
    dimensionare Stop Loss/Stop Protettivo in modo proporzionato alla volatilità
    reale dello strumento (uno stop troppo stretto su una crypto volatile o troppo
    largo su un ETF monetario avrebbe poco senso)."""
    high, low, close = df['High'], df['Low'], df['Close']
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def compute_operational_levels(df_full_c, snap):
    """A partire dallo snapshot indicatori (compute_strategic_snapshot) e dallo storico
    OHLC, individua supporti/resistenze tecniche più vicine al prezzo attuale (SMA,
    Bande di Bollinger, livelli Fibonacci, massimo/minimo degli ultimi 3 mesi) e li
    traduce in livelli operativi indicativi: Acquisto Limite, Stop Loss, Take Profit,
    Vendita Limite, Stop Protettivo. Sono livelli puramente tecnici calcolati dai
    prezzi storici: NON sono ordini pronti da eseguire né una raccomandazione."""
    if snap is None:
        return None
    close = df_full_c['Close'].dropna()
    if close.empty or len(close) < 20:
        return None

    last = snap["last_close"]
    atr_series = calculate_atr_series(df_full_c, 14)
    atr14 = float(atr_series.iloc[-1]) if not atr_series.empty and pd.notna(atr_series.iloc[-1]) else None

    candidates = []
    if snap.get("sma20") is not None: candidates.append(("SMA20", snap["sma20"]))
    if snap.get("sma50") is not None: candidates.append(("SMA50", snap["sma50"]))
    if snap.get("sma200") is not None: candidates.append(("SMA200", snap["sma200"]))
    if snap.get("bb_upper") is not None: candidates.append(("Banda Bollinger Superiore", snap["bb_upper"]))
    if snap.get("bb_lower") is not None: candidates.append(("Banda Bollinger Inferiore", snap["bb_lower"]))

    if snap.get("fib_max") is not None and snap.get("fib_min") is not None and snap["fib_max"] > snap["fib_min"]:
        rng = snap["fib_max"] - snap["fib_min"]
        for pct, lbl in [(0.0, "Fib 0%"), (0.236, "Fib 23.6%"), (0.382, "Fib 38.2%"), (0.5, "Fib 50%"), (0.618, "Fib 61.8%"), (1.0, "Fib 100%")]:
            candidates.append((lbl, snap["fib_max"] - pct * rng))

    swing_window = df_full_c.tail(60)
    if not swing_window.empty:
        candidates.append(("Massimo 3 mesi", float(swing_window['High'].max())))
        candidates.append(("Minimo 3 mesi", float(swing_window['Low'].min())))

    def _dedupe(levels):
        # Scarta livelli entro l'1% l'uno dall'altro, per non affollare la lista con
        # doppioni sostanzialmente coincidenti (es. SMA20 e Bollinger Mid quasi uguali).
        levels_sorted = sorted(levels, key=lambda t: t[1])
        out = []
        for lbl, price in levels_sorted:
            if out and price > 0 and abs(price - out[-1][1]) / price < 0.01:
                continue
            out.append((lbl, price))
        return out

    supports = _dedupe([(l, p) for l, p in candidates if p < last])
    resistances = _dedupe([(l, p) for l, p in candidates if p > last])
    supports.sort(key=lambda t: -t[1])
    resistances.sort(key=lambda t: t[1])

    nearest_support = supports[0] if supports else None
    nearest_resistance = resistances[0] if resistances else None

    buy_limit = nearest_support[1] if nearest_support else None
    take_profit = nearest_resistance[1] if nearest_resistance else None
    sell_limit = nearest_resistance[1] if nearest_resistance else None

    stop_loss = None
    if buy_limit is not None:
        stop_loss = buy_limit - (atr14 * 1.5) if atr14 else buy_limit * 0.98

    protective_stop = None
    if nearest_support is not None:
        protective_stop = nearest_support[1] - (atr14 * 0.5) if atr14 else nearest_support[1] * 0.99

    risk_reward = None
    if buy_limit is not None and take_profit is not None and stop_loss is not None and (buy_limit - stop_loss) > 0:
        risk_reward = (take_profit - buy_limit) / (buy_limit - stop_loss)

    return {
        "last_close": last, "atr14": atr14,
        "nearest_support": nearest_support, "nearest_resistance": nearest_resistance,
        "supports": supports[:3], "resistances": resistances[:3],
        "buy_limit": buy_limit, "stop_loss": stop_loss, "take_profit": take_profit,
        "sell_limit": sell_limit, "protective_stop": protective_stop,
        "risk_reward": risk_reward,
    }

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
                
                sma_val = "🟢 ▲" if sma_200 and latest_price >= sma_200 else ("🔴 ▼" if sma_200 else "N/D")
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

def render_dashboard(df_metrics, df_prices, df_ohlc, key_prefix, section_label):
    """Disegna l'intero cruscotto (le 6 tab: Performance, Cicli, Pullback, Correlazione,
    Guida, Assistente AI) per un sottoinsieme di asset (ETF oppure Crypto). df_metrics/
    df_prices/df_ohlc devono essere GIA' filtrati per il tipo di asset desiderato.
    key_prefix garantisce chiavi widget uniche cosi' le due sezioni non collidono."""
    if df_metrics.empty:
        st.info(f"Nessun asset {section_label} in watchlist (o nessuno ancora attivo). Aggiungine uno dalla barra laterale.")
        return

    if f"{key_prefix}_selected_tab1_cols" not in st.session_state:
        saved_settings = load_settings()
        st.session_state[f"{key_prefix}_selected_tab1_cols"] = saved_settings.get(f"{key_prefix}_selected_tab1_cols", default_tab1_cols.copy())
    if f"{key_prefix}_gemini_chat_history" not in st.session_state:
        st.session_state[f"{key_prefix}_gemini_chat_history"] = []

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Performance e Grafici", 
        "Analisi Cicli & Drawdown", 
        "Opportunità di Pullback",
        "Correlazione & Backtest",
        "Guida e Metriche",
        "Assistente AI (Gemini)"
    ])

    with tab1:
        st.markdown("### Portafoglio & Gestione ETF")
        
        with st.expander("Personalizza Colonne Tabella"):
            st.markdown("<small style='color: #475569;'>Seleziona le colonne da visualizzare:</small>", unsafe_allow_html=True)
            temp_selected_cols = []
            col_c1, col_c2, col_c3, col_c4 = st.columns(4)
            for i, col_name in enumerate(all_tab1_cols):
                default_checked = col_name in st.session_state[f"{key_prefix}_selected_tab1_cols"]
                target_col = [col_c1, col_c2, col_c3, col_c4][i % 4]
                if target_col.checkbox(col_name, value=default_checked, key=f"{key_prefix}_chk_col_tab1_{i}"):
                    temp_selected_cols.append(col_name)
            
            if temp_selected_cols != st.session_state[f"{key_prefix}_selected_tab1_cols"]:
                st.session_state[f"{key_prefix}_selected_tab1_cols"] = temp_selected_cols
        
        if not st.session_state[f"{key_prefix}_selected_tab1_cols"]:
            st.session_state[f"{key_prefix}_selected_tab1_cols"] = default_tab1_cols.copy()

        active_df_metrics = df_metrics[df_metrics["Attivo"] == True].copy()

        if not active_df_metrics.empty:
            st.markdown("<small>Modifica direttamente qui sotto le spunte **Attivo** o il **TER (%)**: vengono applicate e salvate subito, senza bisogno di premere 'Aggiorna Dati' (quel pulsante serve solo a ricaricare i prezzi da Yahoo Finance). Il **Capitale Investito**, il **Prezzo di Carico** (media ponderata) e la **Data di Acquisto** sono calcolati automaticamente dai carichi inseriti nella sezione **'Gestione Carichi'** più sotto.</small>", unsafe_allow_html=True)

            cols_to_display = st.session_state[f"{key_prefix}_selected_tab1_cols"].copy()
            if "ticker_internal" not in cols_to_display:
                cols_to_display_full = cols_to_display + ["ticker_internal"]
            else:
                cols_to_display_full = cols_to_display

            display_cols_clean = [c for c in cols_to_display_full if not c.startswith("raw_")]

            editor_input_df = active_df_metrics[cols_to_display_full][[c for c in cols_to_display_full if c in display_cols_clean or c == "ticker_internal"]].copy()

            # Sovrappone le modifiche Attivo/TER ancora in sospeso (non salvate),
            # così restano visibili anche se nel frattempo cambi le colonne
            # mostrate (che altrimenti farebbero perdere le modifiche non salvate).
            for tk, changes in st.session_state.pending_table_edits.items():
                mask = editor_input_df["ticker_internal"] == tk
                if not mask.any():
                    continue
                if "active" in changes and "Attivo" in editor_input_df.columns:
                    editor_input_df.loc[mask, "Attivo"] = changes["active"]
                if "ter" in changes and "TER (%)" in editor_input_df.columns:
                    editor_input_df.loc[mask, "TER (%)"] = changes["ter"]

            edited_df = st.data_editor(
                editor_input_df,
                use_container_width=True,
                hide_index=True,
                disabled=[c for c in display_cols_clean if c not in ["Attivo", "TER (%)"]] + ["ticker_internal"],
                column_config={
                    "ticker_internal": None,
                    "Strumento": st.column_config.TextColumn("Strumento"),
                    "Categoria": st.column_config.TextColumn("Categoria"),
                    "ISIN": st.column_config.TextColumn("ISIN"),
                    "Data Emissione": st.column_config.TextColumn("Data Emissione"),
                    "JustETF": st.column_config.LinkColumn("Scheda", display_text="[Link]"),
                    "Attivo": st.column_config.CheckboxColumn("Attivo"),
                    "TER (%)": st.column_config.NumberColumn("TER (%)", format="%.2f%%", help=METRIC_TOOLTIPS["TER (%)"]),
                    "Investito (€)": st.column_config.NumberColumn("Capitale Investito (€)", min_value=0.0, step=100.0, format="%.2f €", help=METRIC_TOOLTIPS["Investito (€)"]),
                    "Prezzo Carico (€)": st.column_config.NumberColumn("Prezzo di Carico (€)", min_value=0.0, step=0.01, format="%.2f €", help=METRIC_TOOLTIPS["Prezzo Carico (€)"]),
                    "Data Acquisto": st.column_config.TextColumn("Data Acquisto", help=METRIC_TOOLTIPS["Data Acquisto"]),
                    "Valore Attuale (€)": _tcol("Valore Attuale (€)"),
                    "Profitto/Perdita (€)": _tcol("Profitto/Perdita (€)", "P&L (€)"),
                    "Profitto/Perdita (%)": _tcol("Profitto/Perdita (%)", "P&L (%)"),
                    "Ultimo (€)": _tcol("Ultimo (€)"),
                    "YTD (%)": _tcol("YTD (%)"),
                    "1 Anno (%)": _tcol("1 Anno (%)"),
                    "Volatilità 1A": _tcol("Volatilità 1A"),
                    "Sharpe 1A": _tcol("Sharpe 1A"),
                    "Sortino 1A": _tcol("Sortino 1A"),
                    "SMA200": _tcol("SMA200"),
                    "RSI (14)": _tcol("RSI (14)", "RSI")
                },
                key=f"{key_prefix}_portfolio_editor"
            )

            # Registra nello staging ogni modifica appena fatta (di questo giro) e la
            # applica SUBITO alla watchlist reale (commit + salvataggio su disco).
            # Attivo/TER non richiedono nuovi dati da Yahoo Finance: filtrano solo
            # ciò che è già in cache, quindi non serve aspettare 'Aggiorna Dati'
            # (quel pulsante resta utile solo per ricaricare prezzi e indicatori).
            editor_state = st.session_state.get(f"{key_prefix}_portfolio_editor", {})
            new_edit_applied = False
            for row_idx_str, changes in editor_state.get("edited_rows", {}).items():
                try:
                    row_idx = int(row_idx_str)
                except (TypeError, ValueError):
                    continue
                if row_idx >= len(editor_input_df):
                    continue
                tk = editor_input_df.iloc[row_idx]["ticker_internal"]
                entry = st.session_state.pending_table_edits.setdefault(tk, {})
                if "Attivo" in changes:
                    entry["active"] = bool(changes["Attivo"])
                    new_edit_applied = True
                if "TER (%)" in changes:
                    entry["ter"] = float(changes["TER (%)"])
                    new_edit_applied = True

            if new_edit_applied:
                commit_pending_table_edits()
                # Pulisce lo stato interno del data_editor (edited_rows) subito dopo
                # averlo applicato. Necessario perché la tabella mostra SOLO le righe
                # Attive: appena una viene disattivata, la tabella si restringe e gli
                # indici di riga si spostano. Senza questo reset, Streamlit riapplica
                # la stessa modifica "vecchia" (legata all'indice) al giro successivo,
                # finendo per colpire un ticker diverso da quello inteso.
                st.session_state[f"{key_prefix}_portfolio_editor"] = {
                    "edited_rows": {}, "added_rows": [], "deleted_rows": []
                }
                st.session_state._needs_rerun = True

            if st.session_state.pending_table_edits:
                st.caption(f"{len(st.session_state.pending_table_edits)} modifica/che in sospeso — clicca 'Aggiorna Dati' o 'Salva Modifiche Tabella' per applicarle.")

            if st.button("Salva Modifiche Tabella", use_container_width=True, key=f"{key_prefix}_save_table_edits"):
                commit_pending_table_edits()
                save_settings({f"{key_prefix}_selected_tab1_cols": st.session_state[f"{key_prefix}_selected_tab1_cols"]})
                st.success("Modifiche e impostazioni salvate con successo!")
                st.session_state._needs_rerun = True
        else:
            st.info("Nessun ETF attivo. Usa i pulsanti nella barra laterale (es. 'Tutti' o seleziona qualche spunta) per visualizzarli nella tabella.")

        # --- GESTIONE CARICHI (PIÙ ACQUISTI PER LO STESSO ETF) ---
        st.markdown("---")
        st.markdown("### Gestione Carichi (Prezzo Medio di Carico)")
        st.markdown("<small>Per ogni ETF puoi registrare più carichi (acquisti in date/prezzi diversi). Modifica i valori direttamente nella tabella, usa la riga vuota in fondo per aggiungerne uno nuovo, o il cestino a sinistra per eliminarne uno. Clicca **'Salva Carichi'** per confermare: il **Capitale Investito**, il **Prezzo di Carico medio ponderato** e il **P&L** in tabella si aggiornano di conseguenza.</small>", unsafe_allow_html=True)

        section_tickers = set(df_metrics["ticker_internal"].tolist()) if "ticker_internal" in df_metrics.columns else set()
        lots_ticker_options = {f"{inf['name']} ({tk})": tk for tk, inf in st.session_state.watchlist.items() if tk in section_tickers}
        if lots_ticker_options:
            selected_lots_label = st.selectbox("Seleziona ETF:", list(lots_ticker_options.keys()), key=f"{key_prefix}_lots_etf_select")
            selected_lots_tk = lots_ticker_options[selected_lots_label]
            current_lots = st.session_state.watchlist[selected_lots_tk].get("lots", [])

            tot_inv, avg_p, first_d = compute_lot_summary(current_lots)
            st.markdown(f"<small>**Totale investito:** {tot_inv:,.2f} € | **Prezzo medio di carico:** {avg_p:.4f} € | **Primo carico:** {first_d or 'N/D'}</small>", unsafe_allow_html=True)

            if current_lots:
                df_lots = pd.DataFrame(current_lots)[["date", "price", "amount"]]
            else:
                df_lots = pd.DataFrame(columns=["date", "price", "amount"])
            df_lots = df_lots.rename(columns={"date": "Data", "price": "Prezzo Carico (€)", "amount": "Importo Investito (€)"})

            edited_lots_df = st.data_editor(
                df_lots,
                use_container_width=True,
                hide_index=True,
                num_rows="dynamic",
                column_config={
                    "Data": st.column_config.TextColumn("Data", help="Es. 07.08.26 o 07/08/2026"),
                    "Prezzo Carico (€)": st.column_config.NumberColumn("Prezzo di Carico (€)", min_value=0.0, step=0.01, format="%.2f €"),
                    "Importo Investito (€)": st.column_config.NumberColumn("Importo Investito (€)", min_value=0.0, step=100.0, format="%.2f €"),
                },
                key=f"{key_prefix}_lots_editor_{selected_lots_tk}"
            )

            save_col, export_col = st.columns([0.5, 0.5])
            with save_col:
                if st.button("Salva Carichi", use_container_width=True, key=f"{key_prefix}_save_lots"):
                    new_lots = []
                    for _, r in edited_lots_df.iterrows():
                        price = float(r["Prezzo Carico (€)"]) if pd.notna(r["Prezzo Carico (€)"]) else 0.0
                        amount = float(r["Importo Investito (€)"]) if pd.notna(r["Importo Investito (€)"]) else 0.0
                        date_val = str(r["Data"]).strip() if pd.notna(r["Data"]) else ""
                        if price > 0 and amount > 0:
                            new_lots.append({"date": date_val, "price": price, "amount": amount})
                    st.session_state.watchlist[selected_lots_tk]["lots"] = new_lots
                    st.session_state.watchlist[selected_lots_tk] = _migrate_watchlist_entry(st.session_state.watchlist[selected_lots_tk])
                    save_watchlist(st.session_state.watchlist)
                    st.success("Carichi salvati. Prezzo medio e P&L in tabella aggiornati.")
                    st.session_state._needs_rerun = True
            with export_col:
                if current_lots:
                    df_export = pd.DataFrame(current_lots)
                    df_export["quantità"] = df_export.apply(lambda r: (r["amount"] / r["price"]) if r["price"] > 0 else 0.0, axis=1)
                    df_export = df_export.rename(columns={"date": "Data", "price": "Prezzo Carico (€)", "amount": "Importo Investito (€)", "quantità": "Quantità"})
                    csv_export = df_export[["Data", "Prezzo Carico (€)", "Importo Investito (€)", "Quantità"]].to_csv(index=False).encode("utf-8-sig")
                    st.download_button(
                        label="Esporta storico operazioni",
                        data=csv_export,
                        file_name=f"storico_{selected_lots_tk}.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key=f"{key_prefix}_export_lots_btn"
                    )
                else:
                    st.button("Esporta storico operazioni", disabled=True, use_container_width=True, help="Nessun carico da esportare", key=f"{key_prefix}_export_disabled")
        else:
            st.info("Aggiungi almeno un ETF alla watchlist per gestire i carichi.")

        st.markdown("---")
        st.markdown("### Storico Prezzi & Confronto")
        
        c_opt1, c_opt2, c_opt3 = st.columns([0.35, 0.35, 0.3])
        with c_opt1:
            chart_options = ["Linee (Normalizzato)", "Candele (Candlestick)"]
            current_chart_selection = st.session_state.get(f"{key_prefix}_chart_type_radio", "Linee (Normalizzato)")
            default_idx = chart_options.index(current_chart_selection) if current_chart_selection in chart_options else 0
            
            chart_type = st.radio("Tipo di Grafico:", chart_options, index=default_idx, horizontal=True, key=f"{key_prefix}_chart_type_radio")
        with c_opt2:
            timeframe = st.radio("Orizzonte temporale:", ["1 Anno", "3 Anni", "5 Anni", "Tutto"], index=0, horizontal=True, key=f"{key_prefix}_tf_chart")
        with c_opt3:
            selected_benchmarks = st.multiselect("Aggiungi Benchmark:", ["MSCI World (SWDA.MI)", "S&P 500 (SPY)", "All-World (VWCE.DE)"], key=f"{key_prefix}_benchmarks_multiselect")

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
                        df_filtered_prices[f"[Benchmark] {benchmark_choice}"] = b_data
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
                    if trace.name and "[Benchmark]" in trace.name:
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
                    height=500,
                    plot_bgcolor="white", paper_bgcolor="white",
                    font=dict(color="#475569", size=10),
                    margin=dict(l=10, r=10, t=10, b=10),
                    hovermode="x unified",
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor="#F1F5F9", side="right"),
                    legend=dict(title_text='', orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=9))
                )
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    config=dict(displaylogo=False, scrollZoom=True, modeBarButtonsToRemove=["select2d", "lasso2d", "autoScale2d"]),
                    key=f"{key_prefix}_line_chart_main"
                )

        else:
            active_candle_rows = df_metrics[df_metrics["Attivo"] == True]
            candlestick_names = active_candle_rows["Strumento"].tolist()

            if st.session_state.focus_ticker:
                focused_info = st.session_state.watchlist.get(st.session_state.focus_ticker, {})
                focused_name = focused_info.get("name")
                if focused_name:
                    candlestick_names = [focused_name]

            if candlestick_names:
                selected_candle_etf = st.selectbox("Seleziona ETF per il grafico a candele:", candlestick_names, key=f"{key_prefix}_select_candle_etf")

                total_bars_available = len(df_ohlc[selected_candle_etf]) if selected_candle_etf in df_ohlc else 0
                TF_BAR_MAP = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "Tutto": total_bars_available}

                if f"{key_prefix}_sma_slots" not in st.session_state:
                    loaded_settings = load_settings()
                    st.session_state[f"{key_prefix}_sma_slots"] = loaded_settings.get(f"{key_prefix}_sma_slots", [
                        {"enabled": False, "period": 20, "color": "#F59E0B"},
                        {"enabled": True, "period": 50, "color": "#7C3AED"},
                        {"enabled": True, "period": 200, "color": "#2563EB"},
                    ])
                if f"{key_prefix}_chart_colors" not in st.session_state:
                    loaded_settings = load_settings()
                    st.session_state[f"{key_prefix}_chart_colors"] = loaded_settings.get(f"{key_prefix}_chart_colors", {
                        "candle_up": "#16A34A",
                        "candle_down": "#DC2626",
                        "bollinger": "#9333EA",
                        "rsi": "#9333EA",
                    })
                if f"{key_prefix}_candle_time_tf" not in st.session_state:
                    st.session_state[f"{key_prefix}_candle_time_tf"] = "6m"
                if f"{key_prefix}_candle_zoom_bars" not in st.session_state:
                    st.session_state[f"{key_prefix}_candle_zoom_bars"] = None

                # Se si cambia ETF, la 'Zoom Vista' extra si azzera per ripartire dalla
                # vista piena del periodo selezionato (evita zoom incoerenti tra ETF diversi).
                if st.session_state.get(f"{key_prefix}_last_candle_etf") != selected_candle_etf:
                    st.session_state[f"{key_prefix}_candle_zoom_bars"] = None
                    st.session_state[f"{key_prefix}_last_candle_etf"] = selected_candle_etf

                # --- CONTROLLI PRINCIPALI (sempre visibili, navigazione del grafico) ---
                st.markdown("<small style='color: #475569;'>**Periodo:**</small>", unsafe_allow_html=True)
                current_tf = st.session_state[f"{key_prefix}_candle_time_tf"]
                nav_cols = st.columns([1, 1, 1, 1, 1, 0.15, 1, 1])

                def get_btn_type(tf_name):
                    return "primary" if current_tf == tf_name else "secondary"

                tf_labels = [("1m", "1 mese"), ("3m", "3 mesi"), ("6m", "6 mesi"), ("1y", "1 anno"), ("Tutto", "Tutto")]
                for idx_tf, (tf_key, tf_label) in enumerate(tf_labels):
                    if nav_cols[idx_tf].button(tf_key if tf_key != "Tutto" else "All", key=f"{key_prefix}_zt_{tf_key}", type=get_btn_type(tf_key), use_container_width=True, help=tf_label):
                        st.session_state[f"{key_prefix}_candle_time_tf"] = tf_key
                        st.session_state[f"{key_prefix}_candle_zoom_bars"] = None  # reset dello zoom extra quando si cambia periodo
                        st.session_state._needs_rerun = True

                if nav_cols[6].button("−", key=f"{key_prefix}_zoom_out_btn", use_container_width=True, help="Zoom Out: mostra più candele"):
                    tf_max = TF_BAR_MAP.get(st.session_state[f"{key_prefix}_candle_time_tf"], total_bars_available)
                    base = st.session_state.get(f"{key_prefix}_candle_zoom_bars") or tf_max
                    new_val = int(base * 1.33)
                    st.session_state[f"{key_prefix}_candle_zoom_bars"] = None if new_val >= tf_max else new_val
                    st.session_state._needs_rerun = True
                if nav_cols[7].button("+", key=f"{key_prefix}_zoom_in_btn", use_container_width=True, help="Zoom In: mostra meno candele, più dettaglio"):
                    tf_max = TF_BAR_MAP.get(st.session_state[f"{key_prefix}_candle_time_tf"], total_bars_available)
                    base = st.session_state.get(f"{key_prefix}_candle_zoom_bars") or tf_max
                    st.session_state[f"{key_prefix}_candle_zoom_bars"] = max(15, int(base * 0.75))
                    st.session_state._needs_rerun = True

                st.markdown("<small style='color: #94A3B8;'>Puoi anche zoomare con la rotellina del mouse direttamente sul grafico, o trascinare per spostarti (pan).</small>", unsafe_allow_html=True)

                # --- INDICATORI AVANZATI (raggruppati, richiudibili per non affollare la vista) ---
                with st.expander("Indicatori Tecnici Avanzati (SMA, Bollinger, Fibonacci, RSI/MACD, Colori)", expanded=False):
                    st.markdown("<small style='color: #475569;'>Medie Mobili (SMA): spunta 'Attiva' per mostrarle sul grafico, imposta il periodo e il colore che vuoi.</small>", unsafe_allow_html=True)

                    for i, slot in enumerate(st.session_state[f"{key_prefix}_sma_slots"]):
                        c_chk, c_num, c_col = st.columns([0.35, 0.35, 0.3])
                        with c_chk:
                            new_enabled = st.checkbox(
                                f"Attiva SMA {i+1}", value=slot["enabled"], key=f"{key_prefix}_sma_enabled_{i}"
                            )
                        with c_num:
                            new_period = st.number_input(
                                f"Periodo SMA {i+1}", min_value=2, max_value=500,
                                value=slot["period"], step=1, key=f"{key_prefix}_sma_period_{i}"
                            )
                        with c_col:
                            new_color = st.color_picker(f"Colore SMA {i+1}", value=slot["color"], key=f"{key_prefix}_sma_color_{i}")
                        st.session_state[f"{key_prefix}_sma_slots"][i]["enabled"] = new_enabled
                        st.session_state[f"{key_prefix}_sma_slots"][i]["period"] = int(new_period)
                        st.session_state[f"{key_prefix}_sma_slots"][i]["color"] = new_color

                    st.markdown("---")
                    col_ind4, col_ind5, col_ind6 = st.columns(3)
                    with col_ind4:
                        show_bollinger = st.checkbox("Bollinger", value=False, key=f"{key_prefix}_show_bollinger")
                    with col_ind5:
                        show_fib = st.checkbox("Ritracciamenti Fibonacci", value=False, key=f"{key_prefix}_show_fib")
                    with col_ind6:
                        bottom_indicator = st.selectbox("Indicatore inferiore:", ["RSI (14)", "MACD", "Nessuno"], index=0, key=f"{key_prefix}_bottom_indicator")

                    show_sma_cross = st.checkbox(
                        "Evidenzia incroci tra SMA (Golden Cross / Death Cross)", value=True,
                        help="Segna sul grafico i punti in cui la SMA più breve attiva incrocia quella più lunga attiva: incrocio al rialzo (Golden Cross) = segnale rialzista, al ribasso (Death Cross) = segnale ribassista. Servono almeno 2 SMA attive.",
                        key=f"{key_prefix}_show_sma_cross"
                    )

                    st.markdown("---")
                    col_vol1, col_vol2, col_vol3 = st.columns(3)
                    with col_vol1:
                        show_volume = st.checkbox(
                            "Volumi di scambio", value=True,
                            help="Mostra un istogramma dei volumi scambiati sotto il grafico prezzi. Un movimento (breakout, rimbalzo su supporto) supportato da volumi elevati ha molta più valenza.",
                            key=f"{key_prefix}_show_volume"
                        )
                    with col_vol2:
                        show_vwap = st.checkbox(
                            "VWAP", value=False,
                            help="Volume Weighted Average Price: prezzo medio ponderato per i volumi scambiati, calcolato dall'inizio del periodo visualizzato. Prezzo sopra il VWAP = pressione d'acquisto prevalente; sotto = pressione di vendita.",
                            key=f"{key_prefix}_show_vwap"
                        )
                    with col_vol3:
                        st.session_state[f"{key_prefix}_chart_colors"].setdefault("vwap", "#0891B2")
                        st.session_state[f"{key_prefix}_chart_colors"]["vwap"] = st.color_picker(
                            "Colore VWAP", value=st.session_state[f"{key_prefix}_chart_colors"]["vwap"], key=f"{key_prefix}_color_vwap"
                        )

                    st.markdown("**Colori** (candele, Bollinger, RSI):")
                    cc1, cc2, cc3, cc4 = st.columns(4)
                    with cc1:
                        st.session_state[f"{key_prefix}_chart_colors"]["candle_up"] = st.color_picker(
                            "Candela rialzo", value=st.session_state[f"{key_prefix}_chart_colors"]["candle_up"], key=f"{key_prefix}_color_candle_up"
                        )
                    with cc2:
                        st.session_state[f"{key_prefix}_chart_colors"]["candle_down"] = st.color_picker(
                            "Candela ribasso", value=st.session_state[f"{key_prefix}_chart_colors"]["candle_down"], key=f"{key_prefix}_color_candle_down"
                        )
                    with cc3:
                        st.session_state[f"{key_prefix}_chart_colors"]["bollinger"] = st.color_picker(
                            "Bollinger", value=st.session_state[f"{key_prefix}_chart_colors"]["bollinger"], key=f"{key_prefix}_color_bollinger"
                        )
                    with cc4:
                        st.session_state[f"{key_prefix}_chart_colors"]["rsi"] = st.color_picker(
                            "RSI", value=st.session_state[f"{key_prefix}_chart_colors"]["rsi"], key=f"{key_prefix}_color_rsi"
                        )

                    if st.button("Salva Aspetto Grafico (SMA e Colori)", help="Salva SMA e colori come predefiniti per le prossime sessioni", key=f"{key_prefix}_save_chart_style"):
                        current_settings = load_settings()
                        current_settings[f"{key_prefix}_sma_slots"] = st.session_state[f"{key_prefix}_sma_slots"]
                        current_settings[f"{key_prefix}_chart_colors"] = st.session_state[f"{key_prefix}_chart_colors"]
                        save_settings(current_settings)
                        st.success("Configurazione salvata.")

                if selected_candle_etf in df_ohlc:
                    df_full_c = df_ohlc[selected_candle_etf].copy()

                    df_full_c = df_full_c.dropna(subset=['Open', 'High', 'Low', 'Close'])
                    # NOTA: in precedenza si scartava ogni riga con High == Low, ma per
                    # strumenti a bassissima volatilità (es. ETF monetari/liquidità come
                    # XEON.DE) questo è normalissimo e capitava quasi ogni giorno,
                    # svuotando quasi del tutto il grafico. Ora scartiamo solo le righe
                    # davvero prive di scambi reali: OHLC tutti coincidenti E volume nullo.
                    no_real_trading = (
                        (df_full_c['High'] == df_full_c['Low'])
                        & (df_full_c['Open'] == df_full_c['Close'])
                        & (df_full_c['High'] == df_full_c['Open'])
                        & (df_full_c['Volume'].fillna(0) == 0 if 'Volume' in df_full_c.columns else True)
                    )
                    df_full_c = df_full_c[~no_real_trading]

                    # df_c e' la sola FINESTRA VISUALIZZATA (periodo + zoom); df_full_c resta
                    # sempre lo storico completo e pulito, usato per calcolare gli indicatori
                    # (SMA, Bollinger, RSI, MACD) cosi' che una SMA200 o un incrocio possano
                    # sempre "vedere" abbastanza storia anche quando la vista e' ravvicinata
                    # (es. 1 mese), invece di risultare vuoti/NaN per mancanza di barre precedenti.
                    df_c = df_full_c.copy()
                    tf_selection = st.session_state.get(f"{key_prefix}_candle_time_tf", "Tutto")
                    if tf_selection == "1m" and len(df_c) >= 21: df_c = df_c.iloc[-21:]
                    elif tf_selection == "3m" and len(df_c) >= 63: df_c = df_c.iloc[-63:]
                    elif tf_selection == "6m" and len(df_c) >= 126: df_c = df_c.iloc[-126:]
                    elif tf_selection == "1y" and len(df_c) >= 252: df_c = df_c.iloc[-252:]

                    if st.session_state.get(f"{key_prefix}_candle_zoom_bars") is not None and len(df_c) > st.session_state.get(f"{key_prefix}_candle_zoom_bars"):
                        df_c = df_c.tail(st.session_state.get(f"{key_prefix}_candle_zoom_bars"))

                    st.caption(f"Visualizzate {len(df_c)} candele su {total_bars_available} disponibili.")

                    x_dates = df_c.index.strftime('%d/%m/%y')

                    has_bottom = bottom_indicator != "Nessuno"
                    has_volume = show_volume and "Volume" in df_c.columns and df_c["Volume"].fillna(0).sum() > 0

                    # La struttura del grafico resta SEMPRE fissa a 3 righe (Prezzo,
                    # Volume, Indicatore inferiore): quando una riga non serve non la
                    # rimuoviamo dalla struttura, la rendiamo solo minima e senza
                    # etichette. Cambiare il NUMERO di assi tra un render e l'altro è
                    # ciò che causava grafici "fantasma" sovrapposti: con una struttura
                    # costante Plotly/Streamlit aggiornano il grafico esistente invece
                    # di doverne ricostruire uno con una forma diversa.
                    price_row, volume_row, bottom_row = 1, 2, 3
                    n_rows = 3
                    if has_volume and has_bottom:
                        row_heights = [0.58, 0.16, 0.26]
                    elif has_volume and not has_bottom:
                        row_heights = [0.75, 0.24, 0.01]
                    elif not has_volume and has_bottom:
                        row_heights = [0.72, 0.01, 0.27]
                    else:
                        row_heights = [0.98, 0.01, 0.01]

                    fig_c = make_subplots(
                        rows=n_rows, cols=1,
                        shared_xaxes=True,
                        vertical_spacing=0.03,
                        row_heights=row_heights
                    )

                    def add_to_price(trace):
                        fig_c.add_trace(trace, row=price_row, col=1)

                    candlestick_trace = go.Candlestick(
                        x=x_dates,
                        open=df_c['Open'],
                        high=df_c['High'],
                        low=df_c['Low'],
                        close=df_c['Close'],
                        increasing_line_color=st.session_state[f"{key_prefix}_chart_colors"]["candle_up"], 
                        decreasing_line_color=st.session_state[f"{key_prefix}_chart_colors"]["candle_down"],
                        increasing_fillcolor=st.session_state[f"{key_prefix}_chart_colors"]["candle_up"],
                        decreasing_fillcolor=st.session_state[f"{key_prefix}_chart_colors"]["candle_down"],
                        line=dict(width=1),
                        whiskerwidth=0.6,
                        name='Prezzo'
                    )
                    
                    add_to_price(candlestick_trace)

                    sma_series_by_period = {}
                    for i, slot in enumerate(st.session_state[f"{key_prefix}_sma_slots"]):
                        if not slot["enabled"]:
                            continue
                        sma_full = df_full_c['Close'].rolling(window=slot["period"]).mean()
                        sma_series = sma_full.reindex(df_c.index)
                        sma_series_by_period[slot["period"]] = sma_series
                        sma_trace = go.Scatter(
                            x=x_dates,
                            y=sma_series,
                            mode='lines',
                            name=f'SMA {slot["period"]}',
                            line=dict(color=slot["color"], width=1.5)
                        )
                        add_to_price(sma_trace)

                    # --- Incroci tra SMA (Golden Cross / Death Cross) ---
                    if show_sma_cross and len(sma_series_by_period) >= 2:
                        periods_sorted = sorted(sma_series_by_period.keys())
                        short_period, long_period = periods_sorted[0], periods_sorted[-1]
                        sma_short = sma_series_by_period[short_period]
                        sma_long = sma_series_by_period[long_period]

                        diff = sma_short - sma_long
                        diff_prev = diff.shift(1)
                        golden_mask = (diff_prev < 0) & (diff >= 0)
                        death_mask = (diff_prev > 0) & (diff <= 0)
                        cross_mask = (golden_mask | death_mask).fillna(False)

                        if cross_mask.any():
                            is_classic = (short_period == 50 and long_period == 200)
                            cross_x = x_dates[cross_mask.values]
                            cross_y = sma_short[cross_mask.values]
                            cross_is_golden = golden_mask[cross_mask.values]
                            cross_colors = ["#16A34A" if g else "#DC2626" for g in cross_is_golden]
                            cross_symbols = ["triangle-up" if g else "triangle-down" for g in cross_is_golden]
                            label_up = "Golden Cross" if is_classic else f"Incrocio rialzista (SMA{short_period}/{long_period})"
                            label_down = "Death Cross" if is_classic else f"Incrocio ribassista (SMA{short_period}/{long_period})"
                            cross_labels = [label_up if g else label_down for g in cross_is_golden]

                            cross_trace = go.Scatter(
                                x=cross_x,
                                y=cross_y,
                                mode='markers',
                                marker=dict(size=13, symbol=cross_symbols, color=cross_colors, line=dict(width=1.5, color='white')),
                                name="Golden/Death Cross" if is_classic else f"Incroci SMA{short_period}/{long_period}",
                                hovertext=cross_labels,
                                hoverinfo='text+x'
                            )
                            add_to_price(cross_trace)

                            # Annotazione sull'incrocio più recente, per evidenziarlo subito a colpo d'occhio
                            last_cross_pos = cross_mask.values.nonzero()[0][-1]
                            last_is_golden = golden_mask.iloc[last_cross_pos]
                            fig_c.add_annotation(
                                x=x_dates[last_cross_pos], y=sma_short.iloc[last_cross_pos],
                                text=(label_up if last_is_golden else label_down),
                                showarrow=True, arrowhead=2, ax=0, ay=-35 if last_is_golden else 35,
                                font=dict(size=9, color="#16A34A" if last_is_golden else "#DC2626"),
                                row=price_row if n_rows > 1 else None, col=1 if n_rows > 1 else None
                            )

                    if show_bollinger:
                        bb_sma_full = df_full_c['Close'].rolling(window=20).mean()
                        bb_std_full = df_full_c['Close'].rolling(window=20).std()
                        bb_upper = (bb_sma_full + (bb_std_full * 2)).reindex(df_c.index)
                        bb_lower = (bb_sma_full - (bb_std_full * 2)).reindex(df_c.index)
                        
                        bb_color_hex = st.session_state[f"{key_prefix}_chart_colors"]["bollinger"].lstrip("#")
                        bb_r, bb_g, bb_b = tuple(int(bb_color_hex[j:j+2], 16) for j in (0, 2, 4))
                        trace_upper = go.Scatter(x=x_dates, y=bb_upper, mode='lines', name='Bollinger Superiore', line=dict(color=f'rgba({bb_r}, {bb_g}, {bb_b}, 0.5)', width=1, dash='dot'))
                        trace_lower = go.Scatter(x=x_dates, y=bb_lower, mode='lines', name='Bollinger Inferiore', line=dict(color=f'rgba({bb_r}, {bb_g}, {bb_b}, 0.5)', width=1, dash='dot'), fill='tonexty', fillcolor=f'rgba({bb_r}, {bb_g}, {bb_b}, 0.05)')
                        add_to_price(trace_upper)
                        add_to_price(trace_lower)

                    if show_vwap and "Volume" in df_c.columns and df_c["Volume"].fillna(0).sum() > 0:
                        typical_price = (df_c['High'] + df_c['Low'] + df_c['Close']) / 3
                        vol_safe = df_c['Volume'].fillna(0)
                        cum_pv = (typical_price * vol_safe).cumsum()
                        cum_vol = vol_safe.cumsum().replace(0, np.nan)
                        vwap_series = cum_pv / cum_vol
                        vwap_trace = go.Scatter(
                            x=x_dates, y=vwap_series, mode='lines', name='VWAP',
                            line=dict(color=st.session_state[f"{key_prefix}_chart_colors"].get("vwap", "#0891B2"), width=1.5, dash='dash')
                        )
                        add_to_price(vwap_trace)

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
                            if n_rows > 1:
                                fig_c.add_hline(y=val, line_dash="dash", line_color=fib_colors.get(label, "#64748B"), line_width=1, annotation_text=f"{label}: {val:.2f}€", annotation_position="top left", row=price_row, col=1)
                            else:
                                fig_c.add_hline(y=val, line_dash="dash", line_color=fib_colors.get(label, "#64748B"), line_width=1, annotation_text=f"{label}: {val:.2f}€", annotation_position="top left")

                    if has_volume:
                        vol_colors = [
                            st.session_state[f"{key_prefix}_chart_colors"]["candle_up"] if c >= o else st.session_state[f"{key_prefix}_chart_colors"]["candle_down"]
                            for o, c in zip(df_c['Open'], df_c['Close'])
                        ]
                        volume_trace = go.Bar(
                            x=x_dates, y=df_c['Volume'].fillna(0), name='Volume',
                            marker_color=vol_colors, marker_opacity=0.75
                        )
                        fig_c.add_trace(volume_trace, row=volume_row, col=1)

                    if bottom_indicator == "RSI (14)":
                        rsi_series = calculate_rsi_series(df_full_c['Close'], 14).reindex(df_c.index)
                        rsi_trace = go.Scatter(
                            x=x_dates,
                            y=rsi_series,
                            mode='lines',
                            name='RSI (14)',
                            line=dict(color=st.session_state[f"{key_prefix}_chart_colors"]["rsi"], width=1.5)
                        )
                        fig_c.add_trace(rsi_trace, row=bottom_row, col=1)
                        fig_c.add_hline(y=70, line_dash="dash", line_color="#DC2626", line_width=1, row=bottom_row, col=1)
                        fig_c.add_hline(y=30, line_dash="dash", line_color="#16A34A", line_width=1, row=bottom_row, col=1)
                    elif bottom_indicator == "MACD":
                        exp1_full = df_full_c['Close'].ewm(span=12, adjust=False).mean()
                        exp2_full = df_full_c['Close'].ewm(span=26, adjust=False).mean()
                        macd_line_full = exp1_full - exp2_full
                        signal_line_full = macd_line_full.ewm(span=9, adjust=False).mean()
                        hist_line_full = macd_line_full - signal_line_full
                        macd_line = macd_line_full.reindex(df_c.index)
                        signal_line = signal_line_full.reindex(df_c.index)
                        hist_line = hist_line_full.reindex(df_c.index)

                        fig_c.add_trace(go.Scatter(x=x_dates, y=macd_line, mode='lines', name='MACD', line=dict(color='#2563EB', width=1.2)), row=bottom_row, col=1)
                        fig_c.add_trace(go.Scatter(x=x_dates, y=signal_line, mode='lines', name='Segnale', line=dict(color='#DC2626', width=1.2)), row=bottom_row, col=1)
                        fig_c.add_trace(go.Bar(x=x_dates, y=hist_line, name='Istogramma', marker_color='#94A3B8'), row=bottom_row, col=1)

                    matched_row = active_rows[active_rows["Strumento"] == selected_candle_etf]
                    if not matched_row.empty:
                        buy_p_val = matched_row.iloc[0]["Prezzo Carico (€)"]
                        if buy_p_val > 0:
                            fig_c.add_hline(y=buy_p_val, line_dash="dot", line_color="#E11D48", line_width=1.0, row=price_row, col=1)

                    _zoom_bars_val = st.session_state.get(f"{key_prefix}_candle_zoom_bars")
                    layout_update = dict(
                        title=f"Grafico Tecnico - {selected_candle_etf}",
                        height=650 if (has_volume and has_bottom) else (560 if (has_volume or has_bottom) else 500),
                        plot_bgcolor="white", paper_bgcolor="white",
                        font=dict(color="#475569", size=10),
                        margin=dict(l=10, r=10, t=40, b=10),
                        hovermode="x unified",
                        uirevision=f"{key_prefix}-{selected_candle_etf}-{tf_selection}-{_zoom_bars_val}",
                        xaxis=dict(
                            showgrid=False,
                            type='category',
                            nticks=min(12, max(4, len(df_c) // 10)),
                            tickangle=-45,
                            tickfont=dict(size=9)
                        ),
                        yaxis=dict(showgrid=True, gridcolor="#F1F5F9", title="Prezzo (€)", side="right"),
                        xaxis_rangeslider_visible=False,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=9))
                    )

                    # Righe 2 e 3 sono sempre presenti nella struttura; se non usate
                    # in questa configurazione vengono solo nascoste (nessuna
                    # etichettatura, altezza minima), non rimosse dalla struttura.
                    for extra_row, extra_title, extra_active in [
                        (volume_row, "Volume", has_volume),
                        (bottom_row, bottom_indicator.split()[0] if has_bottom else "", has_bottom)
                    ]:
                        if extra_active:
                            layout_update[f"yaxis{extra_row}"] = dict(showgrid=True, gridcolor="#F1F5F9", title=extra_title, side="right")
                            layout_update[f"xaxis{extra_row}"] = dict(showgrid=False, type='category', tickangle=-45, tickfont=dict(size=9))
                        else:
                            layout_update[f"yaxis{extra_row}"] = dict(showgrid=False, showticklabels=False, title="")
                            layout_update[f"xaxis{extra_row}"] = dict(showgrid=False, showticklabels=False, type='category')

                    fig_c.update_layout(**layout_update)
                    st.plotly_chart(
                        fig_c,
                        use_container_width=True,
                        config=dict(displaylogo=False, scrollZoom=True, modeBarButtonsToRemove=["select2d", "lasso2d", "autoScale2d"]),
                        key=f"{key_prefix}_candle_chart_main"
                    )

                    # --- INDICAZIONI STRATEGICHE (analisi tecnica regola-based) ---
                    st.markdown("---")
                    st.markdown("### 🎯 Indicazioni Strategiche")
                    strat_snap = compute_strategic_snapshot(df_full_c)
                    if strat_snap is None:
                        st.info("Storico insufficiente per calcolare indicazioni strategiche (servono almeno ~15-20 sedute valide).")
                    else:
                        strat_signals = generate_strategic_signals(strat_snap)
                        st.markdown(
                            f"<div style='padding:12px 16px;border-radius:10px;background:{strat_signals['overall_color']}15;"
                            f"border:1px solid {strat_signals['overall_color']}55;margin-bottom:10px;'>"
                            f"<b>Valutazione complessiva su {selected_candle_etf}:</b> "
                            f"<span style='color:{strat_signals['overall_color']};font-weight:700;'>{strat_signals['overall_icon']} {strat_signals['overall_label']}</span>"
                            f"<br><small style='color:#475569;'>Sintesi pesata di breve, medio e lungo termine (il lungo termine pesa doppio, "
                            f"in ottica da 'cassettista'). È una lettura puramente tecnica basata sullo storico dei prezzi: non tiene conto di "
                            f"fondamentali, notizie, fiscalità o della tua situazione personale.</small>"
                            f"</div>", unsafe_allow_html=True
                        )
                        if strat_signals["fib_note"]:
                            st.caption(f"📐 {strat_signals['fib_note']}")

                        strat_cols = st.columns(3)
                        for strat_col, (h_name, h_data) in zip(strat_cols, strat_signals["horizons"].items()):
                            with strat_col:
                                notes_html = "".join(f"<div style='font-size:11px;color:#475569;margin-bottom:3px;'>• {n}</div>" for n in h_data["notes"])
                                st.markdown(
                                    f"<div style='padding:10px 12px;border-radius:8px;background:{h_data['color']}12;"
                                    f"border:1px solid {h_data['color']}40;height:100%;'>"
                                    f"<div style='font-size:12px;color:#475569;font-weight:600;'>{h_name}</div>"
                                    f"<div style='font-size:15px;font-weight:700;color:{h_data['color']};margin:4px 0 8px 0;'>{h_data['icon']} {h_data['label']}</div>"
                                    f"{notes_html}</div>", unsafe_allow_html=True
                                )

                        st.markdown(
                            "<small style='color:#94A3B8;'>⚠️ Indicazioni generate automaticamente da regole tecniche standard "
                            "(SMA, RSI, MACD, Bollinger, VWAP, Fibonacci) applicate ai soli prezzi storici. Non costituiscono consulenza "
                            "finanziaria né una raccomandazione di acquisto/vendita: sono un supporto alla tua analisi. Valuta sempre anche "
                            "fondamentali, orizzonte personale e tolleranza al rischio, ed eventualmente un consulente finanziario abilitato.</small>",
                            unsafe_allow_html=True
                        )

                        # --- LIVELLI OPERATIVI (Acquisto Limite, Stop Loss, Take Profit, ecc.) ---
                        op_levels = compute_operational_levels(df_full_c, strat_snap)
                        if op_levels is not None:
                            st.markdown("#### 📌 Livelli Operativi Indicativi")

                            def _fmt_p(x):
                                if x is None:
                                    return "—"
                                return f"{x:,.4f}€" if abs(x) < 10 else f"{x:,.2f}€"

                            if strat_signals["overall_frac"] <= -0.5:
                                st.warning("Il quadro tecnico complessivo è ribassista: valuta con cautela nuovi ingressi in acquisto. I livelli qui sotto restano comunque un riferimento operativo, utile anche per chi è già investito.")

                            lv_cols = st.columns(4)
                            with lv_cols[0]:
                                st.metric("Prezzo Attuale", _fmt_p(op_levels["last_close"]))
                            with lv_cols[1]:
                                st.metric(
                                    "Acquisto Limite", _fmt_p(op_levels["buy_limit"]),
                                    help=f"Supporto più vicino: {op_levels['nearest_support'][0]}" if op_levels["nearest_support"] else "Nessun supporto tecnico rilevante individuato"
                                )
                            with lv_cols[2]:
                                st.metric(
                                    "Take Profit", _fmt_p(op_levels["take_profit"]),
                                    help=f"Resistenza più vicina: {op_levels['nearest_resistance'][0]}" if op_levels["nearest_resistance"] else "Nessuna resistenza tecnica rilevante individuata"
                                )
                            with lv_cols[3]:
                                st.metric(
                                    "Stop Loss", _fmt_p(op_levels["stop_loss"]),
                                    help="Acquisto Limite − 1.5 × ATR(14)" if op_levels["atr14"] else "Supporto −2% (ATR non disponibile)"
                                )

                            lv_cols2 = st.columns(3)
                            with lv_cols2[0]:
                                st.metric(
                                    "Vendita Limite", _fmt_p(op_levels["sell_limit"]),
                                    help="Per chi è già investito e vuole fissare un target di uscita sulla resistenza più vicina"
                                )
                            with lv_cols2[1]:
                                st.metric(
                                    "Stop Protettivo (se già investito)", _fmt_p(op_levels["protective_stop"]),
                                    help="Poco sotto il supporto più vicino: riferimento per proteggere una posizione già aperta"
                                )
                            with lv_cols2[2]:
                                rr_txt = f"{op_levels['risk_reward']:.2f} : 1" if op_levels["risk_reward"] is not None else "—"
                                st.metric(
                                    "Rapporto Rischio/Rendimento", rr_txt,
                                    help="(Take Profit − Acquisto Limite) / (Acquisto Limite − Stop Loss). Sopra 1.5-2 è generalmente considerato interessante."
                                )

                            with st.expander("Come sono calcolati questi livelli"):
                                sup_txt = ", ".join(f"{l} ({_fmt_p(p)})" for l, p in op_levels["supports"]) or "nessuno individuato"
                                res_txt = ", ".join(f"{l} ({_fmt_p(p)})" for l, p in op_levels["resistances"]) or "nessuna individuata"
                                st.markdown(
                                    f"- **Supporti più vicini** (candidati: SMA20/50/200, Bande di Bollinger, livelli Fibonacci, minimo 3 mesi): {sup_txt}\n"
                                    f"- **Resistenze più vicine** (stessi candidati, sopra il prezzo): {res_txt}\n"
                                    f"- **ATR(14)** (volatilità media giornaliera): {_fmt_p(op_levels['atr14']) if op_levels['atr14'] else 'non disponibile'}\n"
                                    f"- **Acquisto Limite** = supporto tecnico più vicino sotto il prezzo attuale\n"
                                    f"- **Stop Loss** = Acquisto Limite − 1.5 × ATR(14)\n"
                                    f"- **Take Profit / Vendita Limite** = resistenza tecnica più vicina sopra il prezzo attuale\n"
                                    f"- **Stop Protettivo** = supporto più vicino − 0.5 × ATR(14), per chi ha già una posizione aperta"
                                )

                            st.markdown(
                                "<small style='color:#94A3B8;'>⚠️ Livelli puramente tecnici calcolati dai prezzi storici (supporti/resistenze, ATR): "
                                "non sono ordini pronti da eseguire, né una raccomandazione di acquisto/vendita. Vanno sempre valutati insieme al tuo "
                                "piano di investimento, all'orizzonte temporale e alla tua tolleranza al rischio.</small>",
                                unsafe_allow_html=True
                            )
                else:
                    st.warning("Dati OHLC non disponibili per questo strumento.")
            else:
                st.info("Nessun ETF attivo selezionato per il grafico a candele.")

        # --- STORICO PERSONALIZZATO DALLA DATA DI ACQUISTO ---
        st.markdown("---")
        st.markdown("### Storico Personalizzato dall'Acquisto")
        st.markdown("<small>Seleziona un ETF del tuo portafoglio per visualizzarne lo storico dei prezzi a partire dalla specifica data di acquisto inserita.</small>", unsafe_allow_html=True)

        portfolio_invested_df = df_metrics[(df_metrics["Investito (€)"] > 0) & (df_metrics["Prezzo Carico (€)"] > 0) & (df_metrics["Data Acquisto"] != "")]

        if not portfolio_invested_df.empty:
            etf_names_list = portfolio_invested_df["Strumento"].tolist()
            selected_invested_etf = st.selectbox("Seleziona ETF da analizzare:", etf_names_list, key=f"{key_prefix}_selected_inv_etf_chart")

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
        
        with st.expander("Personalizza Colonne Tabella"):
            st.markdown("<small style='color: #475569;'>Seleziona le colonne da visualizzare:</small>", unsafe_allow_html=True)
            selected_tab2_cols = []
            col_d1, col_d2 = st.columns(2)
            for i, col_name in enumerate(all_tab2_cols):
                target_col = [col_d1, col_d2][i % 2]
                if target_col.checkbox(col_name, value=True, key=f"{key_prefix}_chk_col_tab2_{i}"):
                    selected_tab2_cols.append(col_name)
        
        if not selected_tab2_cols:
            selected_tab2_cols = all_tab2_cols

        selected_tf = st.selectbox("Orizzonte temporale:", ["1 Mese", "3 Mesi", "6 Mesi", "1 Anno", "3 Anni", "5 Anni", "Tutto"], index=4, key=f"{key_prefix}_cycles_tf_select")
        
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
        st.markdown("<small>Imposta la soglia di storno desiderata e flagga la colonna **Attivo** nelle tabelle sottostanti per aggiungere o rimuovere gli ETF dalla tua lista di interesse. Clicca su **'Salva Modifiche Pullback'** in fondo per confermare.</small>", unsafe_allow_html=True)
        
        col_s1, col_s2 = st.columns([0.4, 0.6])
        with col_s1:
            pullback_threshold = st.slider(
                "Soglia minima di storno dai massimi (%):", 
                min_value=-30, max_value=0, value=-5, step=1,
                help="Es. impostando -5%, cercherà ETF stornati del 5% o più rispetto al loro picco.",
                key=f"{key_prefix}_pullback_threshold"
            )

        matching_list = []
        other_list = []

        for idx, row in df_metrics.iterrows():
            tk_internal = row["ticker_internal"]
            is_currently_active = row["Attivo"]
            name = row["Strumento"]
            sma_status = row["SMA200"]
            rsi_val = row["raw_rsi"]
            latest_p = row["raw_latest"]
            data_series = row["raw_close"]
            
            if not data_series.empty:
                peak_price = data_series.iloc[-252:].max() if len(data_series) >= 252 else data_series.max()
                current_dd = ((latest_p - peak_price) / peak_price) * 100
                
                item = {
                    "Attivo": bool(is_currently_active),
                    "Strumento": name,
                    "Categoria": row["Categoria"],
                    "Ultimo (€)": f"{latest_p:.2f} €",
                    "Storno dai Massimi (%)": f"{current_dd:+.2f}%",
                    "SMA200": sma_status,
                    "RSI (14)": f"{rsi_val:.1f}",
                    "1 Anno (%)": row["1 Anno (%)"],
                    "ticker_internal": tk_internal
                }
                
                if "▲" in str(sma_status) and current_dd <= pullback_threshold:
                    matching_list.append(item)
                else:
                    other_list.append(item)
        
        st.markdown("#### Opportunità in linea con i criteri impostati")
        edited_matching = None
        if matching_list:
            df_matching = pd.DataFrame(matching_list)
            ordered_cols = ["Attivo", "Strumento", "Categoria", "Ultimo (€)", "Storno dai Massimi (%)", "SMA200", "RSI (14)", "1 Anno (%)", "ticker_internal"]
            
            edited_matching = st.data_editor(
                df_matching[ordered_cols],
                use_container_width=True,
                hide_index=True,
                disabled=[c for c in ordered_cols if c not in ["Attivo", "ticker_internal"]],
                column_config={
                    "ticker_internal": None,
                    "Attivo": st.column_config.CheckboxColumn("Attivo", help="Spunta per attivare/aggiungere alla lista"),
                    "Strumento": st.column_config.TextColumn("Strumento"),
                    "Categoria": st.column_config.TextColumn("Categoria"),
                    "Ultimo (€)": _tcol("Ultimo (€)"),
                    "Storno dai Massimi (%)": _tcol("Storno dai Massimi (%)"),
                    "SMA200": _tcol("SMA200"),
                    "RSI (14)": _tcol("RSI (14)"),
                    "1 Anno (%)": _tcol("1 Anno (%)")
                },
                key=f"{key_prefix}_editor_matching_pullback"
            )
        else:
            st.info(f"Nessun ETF attivo soddisfa i criteri con uno storno di almeno {pullback_threshold}% e trend sopra la SMA200.")

        st.markdown("---")
        st.markdown("#### Tutti gli altri ETF in watchlist")
        edited_other = None
        if other_list:
            df_other = pd.DataFrame(other_list)
            ordered_cols_other = ["Attivo", "Strumento", "Categoria", "Ultimo (€)", "Storno dai Massimi (%)", "SMA200", "RSI (14)", "1 Anno (%)", "ticker_internal"]
            
            edited_other = st.data_editor(
                df_other[ordered_cols_other],
                use_container_width=True,
                hide_index=True,
                disabled=[c for c in ordered_cols_other if c not in ["Attivo", "ticker_internal"]],
                column_config={
                    "ticker_internal": None,
                    "Attivo": st.column_config.CheckboxColumn("Attivo", help="Spunta per attivare/aggiungere alla lista"),
                    "Strumento": st.column_config.TextColumn("Strumento"),
                    "Categoria": st.column_config.TextColumn("Categoria"),
                    "Ultimo (€)": _tcol("Ultimo (€)"),
                    "Storno dai Massimi (%)": _tcol("Storno dai Massimi (%)"),
                    "SMA200": _tcol("SMA200"),
                    "RSI (14)": _tcol("RSI (14)"),
                    "1 Anno (%)": _tcol("1 Anno (%)")
                },
                key=f"{key_prefix}_editor_other_pullback"
            )
        else:
            st.info("Nessun altro ETF presente.")

        if st.button("Salva Modifiche Pullback", use_container_width=True, key=f"{key_prefix}_save_pullback_edits"):
            changes_saved = False
            
            if edited_matching is not None and not edited_matching.empty:
                for idx, row in edited_matching.iterrows():
                    tk = row["ticker_internal"]
                    new_act = row["Attivo"]
                    if tk in st.session_state.watchlist:
                        if st.session_state.watchlist[tk]["active"] != bool(new_act):
                            st.session_state.watchlist[tk]["active"] = bool(new_act)
                            if f"chk_{tk}" in st.session_state:
                                st.session_state[f"chk_{tk}"] = bool(new_act)
                            changes_saved = True

            if edited_other is not None and not edited_other.empty:
                for idx, row in edited_other.iterrows():
                    tk = row["ticker_internal"]
                    new_act = row["Attivo"]
                    if tk in st.session_state.watchlist:
                        if st.session_state.watchlist[tk]["active"] != bool(new_act):
                            st.session_state.watchlist[tk]["active"] = bool(new_act)
                            if f"chk_{tk}" in st.session_state:
                                st.session_state[f"chk_{tk}"] = bool(new_act)
                            changes_saved = True

            if changes_saved:
                save_watchlist(st.session_state.watchlist)
                st.success("Stato degli ETF aggiornato e salvato con successo!")
                st.session_state._needs_rerun = True
            else:
                st.info("Nessuna modifica rilevata.")

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
        st.markdown("### Guida Completa, Esempi e Valutazione delle Metriche")
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

        ### 5. Matrice di Correlazione (Scala da -1 a +1)
        * **Cos'è**: Misura statistica di quanto due strumenti si muovono in sincronia tra loro.
        * **Come interpretare i valori**:
            * **+1.00 (Correlazione Perfetta Positiva)**: I due ETF fanno esattamente la stessa identica cosa. È inutile averli entrambi in portafoglio.
            * **Tra +0.70 e +0.90 (Correlazione Alta)**: I strumenti seguono quasi sempre la stessa tendenza (poca diversificazione).
            * **Tra +0.30 e +0.69 (Correlazione Moderata / Medio-Bassa)**: Condividono il trend generale ma reagiscono in tempi e modi diversi (ottima diversificazione, es. unire un ETF globale Value a uno tecnologico/AI).
            * **Intorno a 0.00 (Incorrelati / Indipendenti)**: I movimenti dell'uno non dipendono dai movimenti dell'altro.
            * **Valori Negativi (da 0 a -1.00) (Correlazione Negativa)**: I due strumenti si muovono in direzione opposta (uno sale quando l'altro scende, utili come copertura o assicurazione).

        ---

        ### 6. Medie Mobili (SMA) — fino a 3 configurabili
        * **Cos'è**: La SMA (Simple Moving Average) è la media aritmetica del prezzo di chiusura sugli ultimi N giorni. Appiattisce le oscillazioni giornaliere e mostra la tendenza di fondo: se il prezzo sta sopra la sua SMA, il trend di quel periodo è tendenzialmente rialzista; se sta sotto, ribassista.
        * **Come si usano in questa app**: Nel pannello "Indicatori Tecnici Avanzati" del grafico a candele puoi attivare **fino a 3 SMA indipendenti**, ognuna con periodo e colore a tua scelta (di default 20, 50 e 200 giorni). Bastano la spunta "Attiva" e il numero di giorni per attivarle.
        * **Esempio**: Attivando una SMA a 20 giorni (breve termine) e una a 200 giorni (lungo termine), puoi vedere a colpo d'occhio se il trend di breve va nella stessa direzione di quello di lungo periodo o se sta divergendo.
        * **Come valutarla**: Più il periodo è **corto** (es. 20), più la SMA reagisce in fretta ai movimenti recenti ma genera più "falsi segnali". Più è **lungo** (es. 200), più è stabile ma reagisce con ritardo — la SMA 200 è quella più usata per giudicare il trend di fondo di lungo periodo (è anche il criterio usato dalla colonna **SMA200** in tabella: 🟢 ▲ verde = prezzo sopra, trend rialzista; 🔴 ▼ rosso = prezzo sotto, trend ribassista).

        ---

        ### 6bis. Incroci tra SMA — Golden Cross / Death Cross
        * **Cos'è**: Un segnale tecnico classico che si genera quando una SMA più breve (es. 50 giorni) attraversa una SMA più lunga (es. 200 giorni).
            * **Golden Cross** (incrocio al rialzo, marcato **▲ verde** sul grafico): la SMA breve supera dal basso verso l'alto quella lunga → segnale di forza, spesso interpretato come inizio di un trend rialzista prolungato.
            * **Death Cross** (incrocio al ribasso, marcato **▼ rosso**): la SMA breve scende sotto quella lunga → segnale di debolezza, spesso interpretato come inizio di un trend ribassista prolungato.
        * **Come si usa in questa app**: attiva la checkbox "Evidenzia incroci tra SMA" (nel pannello Indicatori Tecnici Avanzati) con **almeno 2 SMA attive**: il sistema prende automaticamente la più breve e la più lunga tra quelle attive e segna ogni punto di incrocio, con etichetta e freccia sull'incrocio più recente. Il nome "Golden/Death Cross" (quello tecnico riconosciuto) appare solo se le due SMA attive sono esattamente 50 e 200; con altre combinazioni di periodi vedrai comunque il segnale, etichettato genericamente "incrocio rialzista/ribassista".
        * **Esempio**: se attivi SMA 50 e SMA 200 e sul grafico vedi un triangolo verde nell'ultimo mese, significa che di recente si è verificato un Golden Cross — storicamente un segnale che molti investitori istituzionali monitorano come conferma di un'inversione di tendenza.
        * **Attenzione**: è un indicatore **ritardato** (lagging), perché si basa su medie di prezzi passati — conferma un trend già in corso, non lo anticipa. Va sempre incrociato con altri segnali (volumi, RSI) prima di prendere decisioni.

        ---

        ### 7. Bande di Bollinger & Ritracciamenti di Fibonacci
        * **Bollinger**: Bande costruite attorno a una media mobile a 20 giorni, larghe quanto 2 deviazioni standard del prezzo. Quando il prezzo tocca la banda superiore è vicino a un massimo statistico recente (possibile ipercomprato); quando tocca quella inferiore, un minimo statistico recente (possibile ipervenduto). Bande che si stringono segnalano bassa volatilità (spesso preludio a un movimento più ampio); bande che si allargano segnalano alta volatilità.
        * **Fibonacci**: Traccia livelli percentuali (`23.6%`, `38.2%`, `50%`, `61.8%`) tra il massimo e il minimo del periodo visualizzato. Sono aree dove, storicamente, il prezzo tende a rallentare o "rimbalzare" durante un ritracciamento, utili per individuare possibili zone di supporto (durante un calo) o resistenza (durante un rialzo).
        * **Esempio**: se un ETF sale da 100€ a 150€ e poi inizia a scendere, il livello Fib 38.2% si troverebbe a circa 131€: molti trader guardano quella zona come primo possibile punto di rimbalzo.

        ---

        ### 8. RSI & MACD
        * **RSI (Relative Strength Index)**: Oscillatore di momentum (0-100) calcolato sui 14 periodi. Sopra `70` = ipercomprato (il prezzo è salito molto e velocemente, possibile correzione in arrivo); sotto `30` = ipervenduto (possibile rimbalzo). Tra 30 e 70 il mercato è in una fase più "neutra".
        * **MACD (Moving Average Convergence Divergence)**: Mostra la relazione tra due medie mobili esponenziali (12 e 26 giorni). Quando la linea MACD incrocia al rialzo la linea di Segnale (9 giorni), è un segnale potenzialmente rialzista; quando la incrocia al ribasso, potenzialmente ribassista. L'istogramma mostra la distanza tra le due linee: barre che crescono indicano un trend che sta accelerando.

        ---

        ### 9. Volumi di Scambio
        * **Cos'è**: Il numero di quote scambiate in una singola seduta, mostrato come istogramma sotto il grafico prezzi (colorato di verde/rosso a seconda che la seduta sia chiusa in rialzo o ribasso).
        * **Perché è fondamentale**: Un movimento di prezzo (breakout sopra una resistenza, rimbalzo su un supporto, un Golden Cross) ha **molta più valenza** se accompagnato da volumi elevati, perché indica che l'interesse è concreto e diffuso (spesso legato a investitori istituzionali), non solo a pochi scambi isolati che potrebbero facilmente invertirsi.
        * **Esempio**: se un ETF rompe al rialzo un massimo recente ma con volumi bassi (barre più piccole della media), il breakout è "debole" e a rischio di rientro; se lo stesso breakout avviene con una barra di volume molto più alta delle altre, è un segnale molto più credibile che il movimento continui.
        * **Come si usa in questa app**: attiva "Volumi di scambio" nel pannello Indicatori Tecnici Avanzati (attivo di default): comparirà un sottografico dedicato, sincronizzato con l'asse temporale del grafico prezzi.

        ---

        ### 10. VWAP (Volume Weighted Average Price)
        * **Cos'è**: Il prezzo medio a cui l'ETF è stato effettivamente scambiato in un periodo, ponderato per i volumi di ogni singola seduta (non è una semplice media dei prezzi, ma tiene conto di QUANTO si è scambiato a ogni prezzo).
        * **Come si usa in questa app**: il VWAP è calcolato "ancorato" dall'inizio del periodo che stai visualizzando (cambia quindi in base al filtro Periodo/Zoom selezionato — se guardi gli ultimi 6 mesi, il VWAP riparte da lì).
        * **Come interpretarlo**: Prezzo sopra il VWAP → la pressione d'acquisto ha prevalso su quel periodo (i compratori hanno "vinto" mediamente); prezzo sotto il VWAP → ha prevalso la pressione di vendita. È molto usato insieme ai volumi per validare la forza di un movimento: un breakout sopra una resistenza CON il prezzo sopra il VWAP e volumi elevati è il tipo di conferma più solida che un movimento sia sostenuto da interesse reale, non da rumore di mercato.
        * **Esempio**: se il prezzo sfonda un livello di supporto ma resta sopra il VWAP, il segnale ribassista è meno convincente rispetto a uno sfondamento accompagnato da un prezzo che scende anche sotto il VWAP.

        ---

        ### 11. Gestione Carichi e Prezzo Medio di Carico
        * **Cos'è**: Per ogni ETF puoi registrare più "carichi" (acquisti fatti in date e prezzi diversi), invece di un unico prezzo di carico fisso.
        * **Come funziona il calcolo**: Il **Capitale Investito** è la somma di tutti gli importi investiti nei vari carichi; il **Prezzo di Carico** mostrato in tabella è la **media ponderata** dei prezzi di ogni carico (pesata per l'importo investito in ciascuno, non una semplice media aritmetica); il **Profitto/Perdita (€ e %)** viene calcolato confrontando il valore attuale della posizione con questo prezzo medio.
        * **Esempio**: se compri 500€ di un ETF a 200€/quota e in seguito altri 500€ a 250€/quota, il prezzo medio di carico non è (200+250)/2=225€, ma la media ponderata per l'importo investito in ciascun carico: in questo caso, investendo lo stesso importo nei due carichi, il risultato coincide (225€), ma se gli importi fossero diversi (es. 800€ al primo carico e 200€ al secondo) il prezzo medio si sposterebbe molto più vicino ai 200€, perché quel carico pesa di più sul totale investito.
        * **Come si usa**: nella sezione "Gestione Carichi" (sotto la tabella principale), seleziona l'ETF e modifica/aggiungi/elimina i carichi direttamente nella tabella editabile, poi clicca "Salva Carichi". Puoi anche esportare lo storico completo delle operazioni in CSV con il pulsante "Esporta storico operazioni" (disponibile anche accanto a ogni ETF nella barra laterale).

        ---

        ### 12. Zoom e Navigazione del Grafico a Candele
        * **Periodo**: i pulsanti 1m / 3m / 6m / 1y / All impostano l'ampiezza temporale di base del grafico (es. "6m" mostra gli ultimi 6 mesi di candele).
        * **Zoom Vista (− / +)**: agiscono in aggiunta al Periodo scelto. "+" restringe la vista mostrando meno candele (più dettaglio), "−" la allarga mostrando più candele, fino a tornare alla vista piena del periodo selezionato. Sotto il grafico trovi sempre un contatore ("Visualizzate X di Y candele disponibili") per capire a che punto sei.
        * **Rotella del mouse**: puoi zoomare direttamente sul grafico posizionando il cursore su di esso e usando la rotella; puoi anche trascinare (pan) per spostarti lungo l'asse temporale senza cambiare il livello di zoom.
        * **Suggerimento**: parti sempre da un Periodo stretto (es. 1-3 mesi) quando vuoi analizzare un singolo pattern (es. un incrocio SMA recente), e allarga il Periodo quando vuoi valutare il trend di lungo termine.

        ---

        ### 13. Aggiornamento Dati vs Modifiche alla Tabella
        * **"Aggiorna Dati"** (in alto): ricarica prezzi e indicatori da Yahoo Finance E applica in un solo click tutte le spunte Attivo/TER che hai modificato in tabella. Nessun aggiornamento avviene automaticamente: finché non lo clicchi, i dati di mercato restano quelli dell'ultimo caricamento (mostrato sotto il titolo).
        * **"Salva Modifiche Tabella"**: salva le spunte Attivo/TER senza ricaricare i prezzi da Yahoo Finance — utile se vuoi solo cambiare quali ETF sono "attivi" senza aspettare un nuovo fetch dei dati.
        * **Perché funziona così**: evita chiamate di rete non necessarie ogni volta che spunti/togli una casella, e ti lascia il controllo su quando effettivamente "spendere" una richiesta di aggiornamento dati.

        ---

        ### 14. Personalizzazione dei Colori
        * Puoi personalizzare liberamente il colore di ciascuna delle 3 SMA, delle candele (rialzo/ribasso), delle Bande di Bollinger, della linea RSI e del VWAP, tramite i selettori colore nel pannello "Indicatori Tecnici Avanzati".
        * Il pulsante "Salva Aspetto Grafico (SMA e Colori)" rende la configurazione (periodi SMA, colori) predefinita anche per le prossime sessioni, salvandola in `settings.json`.

        ---

        ### 15. Storno dai Massimi (Drawdown) & Strategia Pullback
        * **Cos'è lo Storno dai Massimi**: la distanza percentuale tra il prezzo attuale e il massimo storico (o del periodo considerato) toccato dallo strumento. Un valore di `-12%` significa che il prezzo oggi è il 12% più basso rispetto al suo picco massimo.
        * **A cosa serve nella tab "Opportunità di Pullback"**: incrocia lo storno dai massimi con il trend di fondo (posizione rispetto alla SMA200) per individuare ETF che sono **ancora in trend rialzista di lungo periodo** (prezzo sopra SMA200) ma che nel breve hanno subito un ritracciamento (storno negativo) — una situazione che molti investitori considerano un potenziale punto di ingresso più favorevole rispetto a comprare sui massimi.
        * **Come si usa**: nella tab imposti una soglia di storno (es. "-10%"): l'app segnala gli ETF che soddisfano contemporaneamente le due condizioni (trend di fondo rialzista + storno oltre la soglia), evidenziandoli come possibili "opportunità di pullback".
        * **Attenzione**: uno storno può anche essere l'inizio di un'inversione di trend più profonda, non un semplice ritracciamento temporaneo — per questo va sempre incrociato con altri segnali (volumi, RSI, eventuali Death Cross) prima di considerarlo un'opportunità.

        ---

        ### 16. Analisi Cicli & Drawdown / Correlazione & Backtest
        * **Analisi Cicli & Drawdown** (tab dedicata): mostra lo storico completo di ogni ETF attivo con il relativo drawdown (calo percentuale rispetto al massimo storico) lungo tutto il periodo disponibile, utile per farsi un'idea di quanto in profondità è sceso lo strumento nei momenti peggiori del passato — un indizio pratico della sua rischiosità reale, più concreto della sola volatilità.
        * **Correlazione & Backtest** (tab dedicata): calcola la matrice di correlazione (vedi punto 5) tra tutti gli ETF attivi in portafoglio, per capire quanto sono davvero diversificati tra loro o se, di fatto, replicano movimenti molto simili.
        """)

    with tab6:
        st.markdown("### Assistente AI — Chiedi a Gemini")
        st.markdown(
            "<small style='color:#475569;'>Usa questo assistente per farti spiegare al volo un indicatore che vedi nei grafici "
            "(es. \"Come interpreto la SMA200 che vedo nel grafico a candele?\"), senza dover cercare nella guida. "
            "Le risposte sono generate da <b>Google Gemini</b> (non da Anthropic): serve una tua chiave API gratuita di Google AI Studio.</small>",
            unsafe_allow_html=True
        )

        if "gemini_api_key" not in st.session_state:
            _gemini_saved = load_settings()
            st.session_state.gemini_api_key = _gemini_saved.get("gemini_api_key", "")
        if "gemini_model" not in st.session_state:
            _gemini_saved = load_settings()
            st.session_state.gemini_model = _gemini_saved.get("gemini_model", "gemini-3.6-flash")

        gemini_preset_models = ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]

        with st.expander("Configurazione chiave API Gemini", expanded=not bool(st.session_state.gemini_api_key)):
            st.markdown(
                "<small>Puoi crearne una gratuitamente su "
                "<a href='https://aistudio.google.com/apikey' target='_blank'>Google AI Studio</a>. "
                "Non è una chiave Anthropic/Claude: è una chiave separata di Google.</small>",
                unsafe_allow_html=True
            )
            col_key1, col_key2 = st.columns([0.7, 0.3])
            with col_key1:
                new_gemini_key = st.text_input(
                    "Chiave API Gemini", value=st.session_state.gemini_api_key,
                    type="password", key=f"{key_prefix}_gemini_api_key_input"
                )
                if new_gemini_key != st.session_state.gemini_api_key:
                    st.session_state.gemini_api_key = new_gemini_key
            with col_key2:
                _model_idx = gemini_preset_models.index(st.session_state.gemini_model) if st.session_state.gemini_model in gemini_preset_models else 0
                selected_preset_model = st.selectbox("Modello", gemini_preset_models, index=_model_idx, key=f"{key_prefix}_gemini_model_select")

            custom_model_input = st.text_input(
                "Oppure specifica manualmente un altro modello Gemini (opzionale, ha priorità sul menu sopra)",
                value="" if st.session_state.gemini_model in gemini_preset_models else st.session_state.gemini_model,
                placeholder="es. gemini-3.8-flash, utile se Google rilascia un modello più recente non ancora in elenco",
                key=f"{key_prefix}_gemini_custom_model_input"
            )
            st.session_state.gemini_model = custom_model_input.strip() if custom_model_input.strip() else selected_preset_model

            remember_gemini_key = st.checkbox(
                "Ricorda questa chiave anche ai prossimi avvii (salvata in settings.json sul tuo computer)",
                value=False, key=f"{key_prefix}_gemini_remember_key",
                help="Se disattivato, la chiave resta solo in questa sessione del browser e va reinserita ogni volta che riavvii l'app."
            )
            if st.button("Salva configurazione", key=f"{key_prefix}_save_gemini_cfg"):
                current_settings_gemini = load_settings()
                if remember_gemini_key:
                    current_settings_gemini["gemini_api_key"] = st.session_state.gemini_api_key
                    current_settings_gemini["gemini_model"] = st.session_state.gemini_model
                    save_settings(current_settings_gemini)
                    st.success("Chiave e modello salvati sul tuo computer.")
                else:
                    current_settings_gemini.pop("gemini_api_key", None)
                    save_settings(current_settings_gemini)
                    st.success("Configurazione aggiornata (chiave non salvata su disco: resta solo in questa sessione).")

        GEMINI_SYSTEM_CONTEXT = (
            "Sei un assistente integrato in un'app Streamlit italiana di analisi ETF e gestione portafoglio. "
            "L'utente ti chiede soprattutto di interpretare gli indicatori tecnici che vede nei grafici dell'app: "
            "medie mobili SMA (e incroci Golden Cross/Death Cross), Bande di Bollinger, Ritracciamenti di Fibonacci, "
            "RSI, MACD, Volumi di scambio, VWAP, Storno dai Massimi (Drawdown), Indice di Sharpe e Sortino, "
            "Volatilità e matrice di Correlazione. L'app mostra anche un pannello 'Indicazioni Strategiche' sotto il "
            "grafico a candele, che assegna una valutazione (rialzista/neutra/ribassista) su breve, medio e lungo "
            "termine combinando questi stessi indicatori con regole tecniche standard (non è generato da te/AI: è "
            "calcolato deterministicamente dall'app). Se l'utente ti chiede di quel pannello, spiega la logica delle "
            "regole (es. RSI<30 e prezzo sotto Bollinger inferiore = ipervenduto a breve; prezzo sopra SMA200 e SMA50 "
            "sopra SMA200 = trend di lungo termine positivo) ma ricorda sempre che è un'analisi puramente tecnica sui "
            "prezzi storici, non una consulenza finanziaria personalizzata. Sotto quel pannello c'è anche 'Livelli "
            "Operativi Indicativi' (Acquisto Limite, Stop Loss, Take Profit, Vendita Limite, Stop Protettivo, Rapporto "
            "Rischio/Rendimento): sono livelli tecnici derivati dai supporti/resistenze più vicini al prezzo (SMA, "
            "Bande di Bollinger, Fibonacci, massimo/minimo 3 mesi) e dall'ATR(14) per la volatilità, calcolati "
            "deterministicamente dall'app, non ordini pronti da eseguire né consulenza finanziaria. Rispondi sempre "
            "in italiano, in modo chiaro, sintetico e pratico, con esempi numerici quando aiutano la comprensione. "
            "Se la domanda esula da questi temi, rispondi comunque nel modo più utile possibile."
        )

        for _msg in st.session_state[f"{key_prefix}_gemini_chat_history"]:
            with st.chat_message("user" if _msg["role"] == "user" else "assistant"):
                st.markdown(_msg["content"])

        if st.button("Cancella conversazione", key=f"{key_prefix}_clear_gemini_chat"):
            st.session_state[f"{key_prefix}_gemini_chat_history"] = []
            st.session_state._needs_rerun = True

        gemini_question = st.chat_input("Scrivi una domanda, es: 'Come interpreto la SMA200 nel grafico a candele?'", key=f"{key_prefix}_gemini_chat_input")

        if gemini_question:
            if not st.session_state.gemini_api_key:
                st.error("Inserisci prima una chiave API Gemini valida nella sezione 'Configurazione chiave API Gemini' qui sopra.")
            else:
                st.session_state[f"{key_prefix}_gemini_chat_history"].append({"role": "user", "content": gemini_question})
                with st.chat_message("user"):
                    st.markdown(gemini_question)

                gemini_contents = [
                    {"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
                    for m in st.session_state[f"{key_prefix}_gemini_chat_history"]
                ]
                gemini_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{st.session_state.gemini_model}:generateContent"
                gemini_payload = {
                    "contents": gemini_contents,
                    "system_instruction": {"parts": [{"text": GEMINI_SYSTEM_CONTEXT}]}
                }
                gemini_headers = {"Content-Type": "application/json", "x-goog-api-key": st.session_state.gemini_api_key}

                with st.chat_message("assistant"):
                    with st.spinner("Gemini sta rispondendo..."):
                        try:
                            gemini_resp = requests.post(gemini_endpoint, headers=gemini_headers, json=gemini_payload, timeout=30)
                            if gemini_resp.status_code == 200:
                                gemini_json = gemini_resp.json()
                                gemini_candidates = gemini_json.get("candidates", [])
                                if gemini_candidates and "content" in gemini_candidates[0] and "parts" in gemini_candidates[0]["content"]:
                                    gemini_answer = "".join(p.get("text", "") for p in gemini_candidates[0]["content"]["parts"])
                                else:
                                    gemini_answer = "Nessuna risposta ricevuta da Gemini (risposta vuota o bloccata dai filtri di sicurezza)."
                            elif gemini_resp.status_code == 400:
                                gemini_answer = "Richiesta non valida: controlla che la chiave API e il modello selezionato siano corretti."
                            elif gemini_resp.status_code == 403:
                                gemini_answer = "Accesso negato: la chiave API non è valida o non ha i permessi necessari."
                            elif gemini_resp.status_code == 429:
                                gemini_answer = "Hai superato il limite di richieste gratuite di Gemini per ora. Riprova tra qualche minuto."
                            else:
                                gemini_answer = f"Errore nella chiamata a Gemini (codice {gemini_resp.status_code}): {gemini_resp.text[:200]}"
                        except requests.exceptions.Timeout:
                            gemini_answer = "Richiesta scaduta (timeout): controlla la connessione e riprova."
                        except Exception as e:
                            gemini_answer = f"Errore imprevisto nel contattare Gemini: {e}"

                        st.markdown(gemini_answer)

                st.session_state[f"{key_prefix}_gemini_chat_history"].append({"role": "assistant", "content": gemini_answer})


if st.session_state.watchlist:
    need_initial_load = st.session_state.market_data is None
    if refresh_clicked:
        commit_pending_table_edits()
    if refresh_clicked or need_initial_load:
        loading_placeholder = show_center_loading("Elaborazione dati finanziari e calcolo indicatori in corso...")
        fetched = get_etf_data(list(st.session_state.watchlist.keys()))
        loading_placeholder.empty()
        st.session_state.market_data = fetched
        st.session_state.last_data_update = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    df_metrics, df_prices, df_ohlc = st.session_state.market_data

    if st.session_state.last_data_update:
        st.caption(f"Ultimo aggiornamento dati: {st.session_state.last_data_update} — le modifiche in tabella si applicano cliccando 'Aggiorna Dati' (o 'Salva Modifiche Tabella' se vuoi solo salvarle senza ricaricare i prezzi).")

    if not df_metrics.empty:
        # Rispecchia SEMPRE lo stato "Attivo" corrente della watchlist (spunte),
        # senza bisogno di rifare le chiamate a Yahoo Finance.
        df_metrics["Attivo"] = df_metrics["ticker_internal"].map(
            lambda tk: bool(st.session_state.watchlist.get(tk, {}).get("active", False))
        )
        # TER, capitale investito, prezzo di carico medio e data primo carico non
        # richiedono dati di mercato: li rispecchiamo sempre live dalla watchlist,
        # così le modifiche (TER, nuovi carichi) si riflettono subito in tabella
        # senza dover premere "Aggiorna Dati" (serve solo per prezzi/indicatori).
        df_metrics["TER (%)"] = df_metrics["ticker_internal"].map(
            lambda tk: float(st.session_state.watchlist.get(tk, {}).get("ter", 0.0))
        )
        df_metrics["Investito (€)"] = df_metrics["ticker_internal"].map(
            lambda tk: float(st.session_state.watchlist.get(tk, {}).get("invested_amount", 0.0))
        )
        df_metrics["Prezzo Carico (€)"] = df_metrics["ticker_internal"].map(
            lambda tk: float(st.session_state.watchlist.get(tk, {}).get("buy_price", 0.0))
        )
        df_metrics["Data Acquisto"] = df_metrics["ticker_internal"].map(
            lambda tk: str(st.session_state.watchlist.get(tk, {}).get("buy_date", ""))
        )

        def _recompute_pnl(row):
            inv_amt = row["Investito (€)"]
            buy_pr = row["Prezzo Carico (€)"]
            latest_price = row.get("raw_latest", None)
            if inv_amt > 0 and buy_pr > 0 and latest_price is not None:
                shares = inv_amt / buy_pr
                current_val_eur = shares * latest_price
                pnl_eur = current_val_eur - inv_amt
                pnl_pct = (pnl_eur / inv_amt) * 100
                val_str = f"{current_val_eur:.2f} €"
                pnl_eur_str = f"+{pnl_eur:.2f} €" if pnl_eur > 0 else f"{pnl_eur:.2f} €"
                pnl_pct_str = f"+{pnl_pct:.2f}%" if pnl_pct > 0 else f"{pnl_pct:.2f}%"
            else:
                val_str, pnl_eur_str, pnl_pct_str = "N/D", "N/D", "N/D"
            return pd.Series([val_str, pnl_eur_str, pnl_pct_str])

        df_metrics[["Valore Attuale (€)", "Profitto/Perdita (€)", "Profitto/Perdita (%)"]] = df_metrics.apply(_recompute_pnl, axis=1)

        df_metrics["asset_type"] = df_metrics["ticker_internal"].map(
            lambda tk: st.session_state.watchlist.get(tk, {}).get("asset_type", "ETF")
        )

        # NOTA TECNICA: qui si usava st.tabs(["ETF","Crypto"]) ma la tab attiva di
        # st.tabs() e' uno stato puramente lato browser, MAI salvato in session_state.
        # Con tab annidate (queste esterne + le 6 sotto-tab di render_dashboard) e un
        # rerun avviato da un widget FUORI dalle tab (es. la spunta "Attivo" in
        # sidebar), quel meccanismo si rompe e la vista torna sempre alla prima tab.
        # st.radio con una key esplicita, invece, e' garantito da Streamlit persistere
        # in session_state attraverso QUALSIASI rerun, indipendentemente da cosa lo
        # scatena: risolve il problema alla radice invece di limitarsi ad aggirarlo.
        active_section = st.radio(
            "Sezione:", ["\U0001F4CA ETF", "\U0001FA99 Crypto"],
            horizontal=True, key="top_level_section"
        )
        st.markdown("---")

        if active_section == "\U0001F4CA ETF":
            df_metrics_etf = df_metrics[df_metrics["asset_type"] == "ETF"].reset_index(drop=True)
            names_etf = df_metrics_etf["Strumento"].tolist()
            df_prices_etf = df_prices[[c for c in df_prices.columns if c in names_etf]]
            df_ohlc_etf = {k: v for k, v in df_ohlc.items() if k in names_etf}
            render_dashboard(df_metrics_etf, df_prices_etf, df_ohlc_etf, "etf", "ETF")
        else:
            df_metrics_crypto = df_metrics[df_metrics["asset_type"] == "CRYPTO"].reset_index(drop=True)
            names_crypto = df_metrics_crypto["Strumento"].tolist()
            df_prices_crypto = df_prices[[c for c in df_prices.columns if c in names_crypto]]
            df_ohlc_crypto = {k: v for k, v in df_ohlc.items() if k in names_crypto}
            render_dashboard(df_metrics_crypto, df_prices_crypto, df_ohlc_crypto, "crypto", "Crypto")
else:
    st.info("Aggiungi almeno un ETF dalla barra laterale.")

# Rerun differito: eseguito qui, alla fine dello script, DOPO che ogni widget della
# pagina (incluso il radio "Sezione: ETF/Crypto" e tutti quelli delle 6 sotto-tab)
# e' gia' stato renderizzato in questo giro. Vedi nota tecnica in cima al file.
if st.session_state._needs_rerun:
    st.session_state._needs_rerun = False
    st.rerun()
