from binance.client import Client
from pathlib import Path
import json
import time
from datetime import datetime
import csv
import os

def load_config():
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    with open(config_path) as f:
        return json.load(f)

def get_binance_client():
    config_path = Path("config/config.json")  # Update this path if needed
    with open(config_path) as f:
        config = json.load(f)
    return Client(config["api_key"], config["api_secret"])

def get_price_dict(client):
    tickers = client.get_all_tickers()
    return {t['symbol']: float(t['price']) for t in tickers}

def get_spot_account_value(client, price_dict):
    account = client.get_account()
    total_value = 0
    balances = []

    for b in account['balances']:
        asset = b['asset']
        free = float(b['free'])
        locked = float(b['locked'])
        total = free + locked
        symbol = asset + "USDT"

        if total > 0 and symbol in price_dict:
            value = total * price_dict[symbol]
            balances.append((asset, total, value))
            total_value += value

    print("=== SPOT BALANCES ===")
    for asset, amount, value in balances:
        print(f"{asset:<6} {amount:>12.6f} ≈ ${value:,.2f}")
    print(f"\nTotal Spot Account Value: ${total_value:,.2f}")

    return total_value

def get_all_trade_history(
    client,
    start_date: str,
    output_file="data/trade_history.csv",
    symbols_log_file="data/symbols_log.json",
    use_saved_symbols=False,
    quote_assets=("USDT", "USDC")
):
    """
    Fetches spot trade history from Binance since a given start date, merges with existing CSV,
    and optionally caches traded symbols to reduce API calls.
    Always writes a CSV with headers, even if no trades are found.
    """

    # Ensure paths are pathlib.Path
    output_file = Path(output_file)
    symbols_log_file = Path(symbols_log_file)

    # Ensure the data folder exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Convert start_date to Binance-compatible timestamp
    start_ts = int(time.mktime(datetime.strptime(start_date, "%Y-%m-%d").timetuple()) * 1000)

    # Load or fetch symbols
    if use_saved_symbols and symbols_log_file.exists():
        try:
            with open(symbols_log_file, "r") as f:
                symbols = json.load(f)
            if not symbols:
                print(f"⚠️ Warning: {symbols_log_file} is empty — no symbols to process.")
                symbols = []
        except json.JSONDecodeError:
            print(f"❌ Error: {symbols_log_file} is not valid JSON.")
            symbols = []
    else:
        exchange_info = client.get_exchange_info()
        symbols = [
            s['symbol'] for s in exchange_info['symbols']
            if s['status'] == 'TRADING' and any(s['symbol'].endswith(q) for q in quote_assets)
        ]
        with open(symbols_log_file, "w") as f:
            json.dump(symbols, f, indent=2)
        print(f"🧭 Fetched and saved {len(symbols)} symbols to {symbols_log_file}")

    print(f"\n=== Fetching TRADE HISTORY since {start_date} ===")

    all_rows = []

    for symbol in symbols:
        try:
            trades = client.get_my_trades(symbol=symbol, startTime=start_ts)
            for trade in trades:
                time_str = datetime.fromtimestamp(trade['time'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                row = {
                    "datetime": time_str,
                    "symbol": symbol,
                    "side": "BUY" if trade['isBuyer'] else "SELL",
                    "price": trade['price'],
                    "quantity": trade['qty'],
                    "quoteQty": trade['quoteQty'],
                    "fee": trade['commission'],
                    "feeAsset": trade['commissionAsset'],
                    "tradeId": str(trade['id'])
                }
                all_rows.append(row)
        except Exception as e:
            if "No trades" in str(e) or "Invalid symbol" in str(e):
                continue
            else:
                print(f"❌ Error fetching {symbol}: {e}")

    # Load existing CSV if present
    existing_rows = []
    if output_file.exists():
        with open(output_file, "r", newline="") as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)

    # Merge and deduplicate
    combined = existing_rows + all_rows
    unique_trades = {}
    for row in combined:
        key = f"{row['symbol']}_{row['tradeId']}"
        unique_trades[key] = row

    sorted_trades = sorted(unique_trades.values(), key=lambda x: x.get("datetime", ""))

    # Define column headers
    keys = [
        "datetime", "symbol", "side", "price",
        "quantity", "quoteQty", "fee", "feeAsset", "tradeId"
    ]

    # ✅ Always write the CSV file, even if empty
    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(sorted_trades)

    print(f"✅ Trade history saved to '{output_file}' with {len(sorted_trades)} unique trades.")
