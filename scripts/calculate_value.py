from binance.client import Client
from pathlib import Path
import json

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

def main():
    config = load_config()
    client = Client(config["api_key"], config["api_secret"])
    price_dict = get_price_dict(client)
    print_spot_balances(client, price_dict)

if __name__ == "__main__":
    main()
