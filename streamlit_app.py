import streamlit as st
import pandas as pd
import csv
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from binance.client import Client
from scripts.calculate_value import get_binance_client

# === CONFIG ===
TRADE_HISTORY_FILE = Path("data") / "trade_history.csv"
QUOTE_ASSET = "USDT"  # default quote

# === INIT BINANCE CLIENT ===
client = get_binance_client()

# === LOAD AND BUILD BALANCE HISTORY ===
@st.cache_data
def build_asset_history():
    if not TRADE_HISTORY_FILE.exists():
        st.error(f"Trade history file not found: {TRADE_HISTORY_FILE}")
        return pd.DataFrame()

    with open(TRADE_HISTORY_FILE, "r") as f:
        reader = csv.DictReader(f)
        trades = sorted(reader, key=lambda x: x["datetime"])

    balances = defaultdict(float)
    snapshots = []

    for trade in trades:
        dt = datetime.strptime(trade["datetime"], "%Y-%m-%d %H:%M:%S")
        symbol = trade["symbol"]
        side = trade["side"]
        qty = float(trade["quantity"])
        quote_qty = float(trade["quoteQty"])
        fee = float(trade["fee"])
        fee_asset = trade["feeAsset"]

        for quote in ["USDT", "USDC", "BUSD"]:
            if symbol.endswith(quote):
                base_asset = symbol.replace(quote, "")
                quote_asset = quote
                break
        else:
            continue

        if side == "BUY":
            balances[base_asset] += qty
            balances[quote_asset] -= quote_qty
        elif side == "SELL":
            balances[base_asset] -= qty
            balances[quote_asset] += quote_qty

        balances[fee_asset] -= fee

        snapshot = {
            "datetime": dt,
            **{asset: round(amount, 8) for asset, amount in balances.items() if abs(amount) > 1e-10}
        }
        snapshots.append(snapshot)

    df = pd.DataFrame(snapshots).fillna(0)
    df.set_index("datetime", inplace=True)
    return df


# === GET HISTORICAL PRICES FROM BINANCE ===
@st.cache_data
def get_binance_historical_prices(_client, assets, _dates, quote_asset="USDT"):
    from collections import defaultdict

    prices = defaultdict(dict)
    for asset in assets:
        symbol = asset + quote_asset
        for date in _dates:
            start = datetime.combine(date, datetime.min.time())
            end = start + timedelta(days=1)
            try:
                klines = _client.get_historical_klines(
                    symbol=symbol,
                    interval=Client.KLINE_INTERVAL_1HOUR,
                    start_str=start.strftime("%d %b %Y %H:%M:%S"),
                    end_str=end.strftime("%d %b %Y %H:%M:%S")
                )
                if klines:
                    close_price = float(klines[-1][4])
                    prices[asset][date] = close_price
            except Exception as e:
                print(f"❌ {symbol} on {date}: {e}")
                prices[asset][date] = None
    return prices


# === CALCULATE USD VALUE ===
def calculate_usd_value(df_balances, asset_prices):
    df_usd = pd.DataFrame(index=df_balances.index)
    for asset in df_balances.columns:
        price_series = pd.Series(asset_prices.get(asset, {})).reindex(df_balances.index, method="ffill").fillna(0)
        df_usd[asset] = df_balances[asset] * price_series
    df_usd["Total"] = df_usd.sum(axis=1)
    return df_usd


# === STREAMLIT APP ===
st.set_page_config(page_title="📊 Binance Portfolio Tracker", layout="wide")
st.title("📊 Binance Portfolio Tracker (with Historical USD Value)")

df_balances = build_asset_history()
if df_balances.empty:
    st.stop()

# === SIDEBAR CONTROLS ===
with st.sidebar:
    st.header("🔧 Filters")

    all_assets = df_balances.columns.tolist()
    selected_assets = st.multiselect("Assets to display", all_assets, default=all_assets)

    min_date = df_balances.index.min().date()
    max_date = df_balances.index.max().date()
    date_range = st.date_input("Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)

    view_mode = st.radio("View Mode", ["Asset Balances", "USD Value"])
    show_table = st.checkbox("Show Data Table")

# === FILTER DATA ===
df_balances = df_balances[selected_assets]
df_balances = df_balances[(df_balances.index.date >= date_range[0]) & (df_balances.index.date <= date_range[1])]

# === MAIN DISPLAY ===
if view_mode == "Asset Balances":
    st.subheader("📈 Asset Balances Over Time")
    st.line_chart(df_balances)
    if show_table:
        st.dataframe(df_balances)

else:
    st.subheader("💰 Portfolio USD Value Over Time (Binance Prices)")
    with st.spinner("Fetching Binance prices..."):
        unique_dates = pd.to_datetime(df_balances.index).normalize().unique()
        asset_prices = get_binance_historical_prices(client, selected_assets, unique_dates)
        df_usd = calculate_usd_value(df_balances, asset_prices)

    st.line_chart(df_usd["Total"])
    if show_table:
        st.dataframe(df_usd)
