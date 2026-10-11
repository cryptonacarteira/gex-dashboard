import csv
from datetime import datetime
import os
import re
import sys

import requests

CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/_SPX.json"
OUTPUT = "spx_quotedata.csv"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}


OCC_PATTERN = re.compile(r"^([A-Z]+)(\d{6})([CP])(\d{8})$")


def parse_occ(symbol):
    # OCC: ROOT (SPX/SPXW) + YYMMDD + C/P + strike (últimos 8 dígitos = strike * 1000)
    m = OCC_PATTERN.match(symbol)
    if not m:
        raise ValueError(f"Símbolo OCC inesperado: {symbol}")
    _, date_part, option_type, strike_part = m.groups()
    strike = int(strike_part) / 1000.0
    exp = datetime.strptime(date_part, "%y%m%d")
    return exp, option_type, strike


def main():
    print("Baixando cadeia de opções SPX da API pública da Cboe...")
    resp = requests.get(CBOE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    data = resp.json()["data"]
    spot = float(data["current_price"])
    options = data["options"]

    if not options or spot <= 0:
        print("Erro: API retornou dados vazios/inválidos.", file=sys.stderr)
        sys.exit(1)

    rows = []
    for op in options:
        exp, option_type, strike = parse_occ(op["option"])
        exp_label = exp.strftime("%a %b %d %Y")

        def num(key):
            v = op.get(key, 0)
            return v if v is not None else 0

        if option_type == "C":
            rows.append([
                exp_label, op["option"],
                num("last_trade_price"), num("change"),
                num("bid"), num("ask"),
                num("volume"), num("iv"), num("delta"), num("gamma"), num("open_interest"),
                f"{strike:.3f}",
                "", 0, 0, 0, 0, 0, 0, 0, 0, 0,
            ])
        else:
            rows.append([
                exp_label, "", 0, 0, 0, 0, 0, 0, 0, 0, 0,
                f"{strike:.3f}",
                op["option"],
                num("last_trade_price"), num("change"),
                num("bid"), num("ask"),
                num("volume"), num("iv"), num("delta"), num("gamma"), num("open_interest"),
            ])

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["SPX^QUOTES - Delayed Quotes"])
        w.writerow([f"Underlying,Last:{spot},Net Chg,Bid,Ask,Volume,Open High,Open Low,Previous Close"])
        w.writerow([])
        w.writerow([
            "Expiration Date", "Calls", "Last Sale", "Net", "Bid", "Ask", "Volume",
            "IV", "Delta", "Gamma", "Open Int", "Strike",
            "Puts", "Last Sale", "Net", "Bid", "Ask", "Volume",
            "IV", "Delta", "Gamma", "Open Int",
        ])
        for r in rows:
            w.writerow(r)

    print(f"OK: {len(rows)} opções processadas. Spot SPX = {spot:.2f}")
    print(f"Arquivo {OUTPUT} gerado no formato CBOE.")


if __name__ == "__main__":
    main()