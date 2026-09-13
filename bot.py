import requests, time
import pandas as pd
from datetime import datetime, timezone

TG = "8854505310:AAHA91tLQUvEPiiTOxW1S_x1kfIA8Cmwsyk"
CI = "5885172416"
DK = "3140708eff5b411786b7b5e6c95c11d1"

def get_session():
    h = datetime.now(timezone.utc).hour
    if h >= 22 or h < 4:
        return "MORNING"
    if 8 <= h < 12:
        return "LONDON"
    if 12 <= h < 17:
        return "NY_OVERLAP"
    if 17 <= h < 21:
        return "NY"
    return "ASIAN"

def fetch(i, s):
    u = "https://api.twelvedata.com/time_series"
    p = {"symbol": "XAU/USD", "interval": i, "outputsize": s, "apikey": DK}
    r = requests.get(u, params=p, timeout=30).json()
    if "values" not in r:
        return None
    d = pd.DataFrame(r["values"])
    d["dt"] = pd.to_datetime(d["datetime"])
    for c in ["open", "high", "low", "close"]:
        d[c] = d[c].astype(float)
    return d.sort_values("dt").reset_index(drop=True)

def ema(a, p):
    k = 2.0 / (p + 1)
    e = a[0]
    for x in a[1:]:
        e = x * k + e * (1 - k)
    return e

def rsi(a, p=14):
    g = 0
    l = 0
    for i in range(len(a) - p, len(a)):
        d = a[i] - a[i - 1]
        if d > 0:
            g += d
        else:
            l -= d
    if l == 0:
        return 100
    return 100 - 100 / (1 + (g / p) / (l / p))

def find_fvg(df):
    out = []
    for i in range(2, len(df)):
        c1h = df["high"].iloc[i-2]
        c1l = df["low"].iloc[i-2]
        c3h = df["high"].iloc[i]
        c3l = df["low"].iloc[i]
        if c1h < c3l:
            out.append({"t": "B", "ce": (c1h + c3l) / 2})
        if c1l > c3h:
            out.append({"t": "S", "ce": (c1l + c3h) / 2})
    return out

def find_ob(df):
    b_ob = None
    s_ob = None
    for i in range(len(df) - 3, max(len(df) - 30, 0), -1):
        c = df.iloc[i]
        n1 = df.iloc[i + 1]
        n2 = df.iloc[i + 2]
        if b_ob is None and c["close"] < c["open"] and n1["close"] > n1["open"] and n2["close"] > n2["open"]:
            b_ob = {"top": c["open"], "bot": c["close"]}
        if s_ob is None and c["close"] > c["open"] and n1["close"] < n1["open"] and n2["close"] < n2["open"]:
            s_ob = {"top": c["close"], "bot": c["open"]}
    return b_ob, s_ob

def swings(df, w=3):
    H = []
    L = []
    for i in range(w, len(df) - w):
        if df["high"].iloc[i] == df["high"].iloc[i-w:i+w+1].max():
            H.append(df["high"].iloc[i])
        if df["low"].iloc[i] == df["low"].iloc[i-w:i+w+1].min():
            L.append(df["low"].iloc[i])
    return H, L

def run():
    session = get_session()
    data = {}
    tfs = [("daily", "1day", 150), ("h4", "4h", 200), ("h1", "1h", 250), ("m15", "15min", 200), ("m5", "5min", 200), ("m1", "1min", 200)]
    for n, i, s in tfs:
        data[n] = fetch(i, s)
        time.sleep(8)
    if any(v is None for v in data.values()):
        print("Fetch failed")
        return
    daily = data["daily"]
    h4 = data["h4"]
    h1 = data["h1"]
    m15 = data["m15"]
    m5 = data["m5"]
    m1 = data["m1"]
    cur = m5["close"].iloc[-1]
    bull = []
    bear = []
    d_hi = daily["high"].max()
    d_lo = daily["low"].min()
    d_mid = (d_hi + d_lo) / 2
    if cur > d_mid:
        bull.append("Above Daily 50%")
    else:
        bear.append("Below Daily 50%")
    adr = (daily.tail(30)["high"] - daily.tail(30)["low"]).mean()
    if h4.iloc[-1]["close"] > h4["high"].iloc[-12:-1].max():
        bull.append("4H BOS UP")
    if h4.iloc[-1]["close"] < h4["low"].iloc[-12:-1].min():
        bear.append("4H BOS DN")
    if h1.iloc[-1]["close"] > h1["high"].iloc[-15:-1].max():
        bull.append("1H MSS UP")
    if h1.iloc[-1]["close"] < h1["low"].iloc[-15:-1].min():
        bear.append("1H MSS DN")
    if m15.iloc[-1]["close"] > m15["high"].iloc[-10:-1].max():
        bull.append("15M MSS UP")
    if m15.iloc[-1]["close"] < m15["low"].iloc[-10:-1].min():
        bear.append("15M MSS DN")
    c1_m5 = m5.iloc[-1]
    c2_m5 = m5.iloc[-2]
    body_m5 = abs(c1_m5["close"] - c1_m5["open"])
    if c1_m5["close"] > c1_m5["open"] and body_m5 > adr * 0.05:
        bull.append("5M Bull Candle")
    if c1_m5["close"] < c1_m5["open"] and body_m5 > adr * 0.05:
        bear.append("5M Bear Candle")
    if c2_m5["close"] < c2_m5["open"] and c1_m5["close"] > c1_m5["open"] and c1_m5["close"] > c2_m5["open"]:
        bull.append("5M Bull Engulf")
    if c2_m5["close"] > c2_m5["open"] and c1_m5["close"] < c1_m5["open"] and c1_m5["close"] < c2_m5["open"]:
        bear.append("5M Bear Engulf")
    fvgs = find_fvg(m15)[-10:]
    nb = [f for f in fvgs if f["t"] == "B" and abs(cur - f["ce"]) < adr * 0.25]
    ns = [f for f in fvgs if f["t"] == "S" and abs(cur - f["ce"]) < adr * 0.25]
    if nb:
        bull.append("Bull FVG")
    if ns:
        bear.append("Bear FVG")
    b_ob, s_ob = find_ob(h1)
    if b_ob and b_ob["bot"] - 5 <= cur <= b_ob["top"] + 5:
        bull.append("At Bull OB")
    if s_ob and s_ob["bot"] - 5 <= cur <= s_ob["top"] + 5:
        bear.append("At Bear OB")
    H, L = swings(h1)
    bsl = sorted(H, reverse=True)[:5]
    ssl = sorted(L)[:5]
    nB = next((p for p in bsl if p > cur), None)
    nS = next((p for p in ssl if p < cur), None)
    if nB and nB - cur < adr * 0.3:
        bear.append("Near BSL")
    if nS and cur - nS < adr * 0.3:
        bull.append("Near SSL")
    if len(L) > 1 and abs(L[-1] - L[-2]) < 5:
        bull.append("Equal Lows")
    if len(H) > 1 and abs(H[-1] - H[-2]) < 5:
        bear.append("Equal Highs")
    closes = h1["close"].tolist()
    e50 = ema(closes, 50)
    e200 = ema(closes, 200)
    if cur > e50 and e50 > e200:
        bull.append("EMA50>200 UP")
    if cur < e50 and e50 < e200:
        bear.append("EMA50<200 DN")
    if cur > e200:
        bull.append("Above EMA200")
    else:
        bear.append("Below EMA200")
    r = rsi(closes)
    if r < 30:
        bull.append("RSI Oversold")
    if r > 70:
        bear.append("RSI Overbought")
    if 50 < r < 70:
        bull.append("RSI Bullish")
    if 30 < r < 50:
        bear.append("RSI Bearish")
    m_now = ema(closes[-50:], 12) - ema(closes[-50:], 26)
    m_prev = ema(closes[-51:-1], 12) - ema(closes[-51:-1], 26)
    if m_now > 0 and m_prev <= 0:
        bull.append("MACD Cross UP")
    if m_now < 0 and m_prev >= 0:
        bear.append("MACD Cross DN")
    if m_now > 0:
        bull.append("MACD Positive")
    else:
        bear.append("MACD Negative")
    pdh = daily["high"].iloc[-2]
    pdl = daily["low"].iloc[-2]
    if abs(cur - pdh) < adr * 0.25:
        bear.append("Near PDH")
    if abs(cur - pdl) < adr * 0.25:
        bull.append("Near PDL")
    rn = round(cur / 50) * 50
    if abs(cur - rn) < adr * 0.1:
        if cur > rn:
            bear.append("Above Round " + str(rn))
        else:
            bull.append("Below Round " + str(rn))
    dow = datetime.now(timezone.utc).weekday()
    if dow == 0 and len(daily) > 1:
        fri_close = daily["close"].iloc[-2]
        mon_open = daily["open"].iloc[-1]
        gap = abs(mon_open - fri_close)
        if gap > adr * 0.3:
            if mon_open > fri_close:
                bull.append("Monday Gap UP")
            else:
                bear.append("Monday Gap DOWN")
    today = m5["dt"].iloc[-1].date()
    asian = m5[(m5["dt"].dt.date == today) & (m5["dt"].dt.hour < 7)]
    aH = asian["high"].max() if len(asian) else 0
    aL = asian["low"].min() if len(asian) else 0
    if aH and cur > aH:
        bull.append("Above Asian High")
    if aL and cur < aL:
        bear.append("Below Asian Low")
    london = m5[(m5["dt"].dt.date == today) & (m5["dt"].dt.hour >= 7) & (m5["dt"].dt.hour < 12)]
    lH = london["high"].max() if len(london) else 0
    lL = london["low"].min() if len(london) else 0
    ny = m5[(m5["dt"].dt.date == today) & (m5["dt"].dt.hour >= 12) & (m5["dt"].dt.hour < 21)]
    nH = ny["high"].max() if len(ny) else 0
    nL = ny["low"].min() if len(ny) else 0
    c3 = h1.iloc[-1]
    c2 = h1.iloc[-2]
    body = abs(c3["close"] - c3["open"])
    uw = c3["high"] - max(c3["close"], c3["open"])
    dw = min(c3["close"], c3["open"]) - c3["low"]
    if dw > 2 * body and uw < body:
        bull.append("1H Bull Pin")
    if uw > 2 * body and dw < body:
        bear.append("1H Bear Pin")
    if c2["close"] < c2["open"] and c3["close"] > c3["open"] and c3["close"] > c2["open"]:
        bull.append("1H Bull Engulf")
    if c2["close"] > c2["open"] and c3["close"] < c3["open"] and c3["close"] < c2["open"]:
        bear.append("1H Bear Engulf")
    bS = len(bull)
    sS = len(bear)
    conf = max(bS, sS)
    if conf < 6:
        print("Conf " + str(conf) + " skip")
        return
    if bS > sS:
        action = "LONG"
        reasons = bull
    else:
        action = "SHORT"
        reasons = bear
    entry = cur
    if action == "LONG":
        sl = cur - 20
        tp1 = cur + 20
        tp2 = cur + 30
        tp3 = cur + 40
    else:
        sl = cur + 20
        tp1 = cur - 20
        tp2 = cur - 30
        tp3 = cur - 40
    sl_pips = abs(entry - sl) * 10
    rr = abs(tp1 - entry) / abs(entry - sl)
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    text = "GOLD SMC " + action + " - " + session
    text = text + "\nTime: " + now
    text = text + "\nPrice: " + str(round(cur, 2))
    text = text + "\nEntry: " + str(round(entry, 2))
    text = text + "\nSL: " + str(round(sl, 2)) + " (" + str(round(sl_pips)) + " pips)"
    text = text + "\nTP1: " + str(round(tp1, 2))
    text = text + "\nTP2: " + str(round(tp2, 2))
    text = text + "\nTP3: " + str(round(tp3, 2))
    text = text + "\nRR: 1:1 / 1:1.5 / 1:2"
    text = text + "\nConf: " + str(conf) + "/24"
    text = text + "\nSession Levels:"
    text = text + "\nAsian: " + str(round(aL, 2)) + " -> " + str(round(aH, 2))
    if lH:
        text = text + "\nLondon: " + str(round(lL, 2)) + " -> " + str(round(lH, 2))
    if nH:
        text = text + "\nNY: " + str(round(nL, 2)) + " -> " + str(round(nH, 2))
    text = text + "\nPDH: " + str(round(pdh, 2)) + " | PDL: " + str(round(pdl, 2))
    text = text + "\nReasons:\n" + "\n".join(reasons[:12])
    requests.post("https://api.telegram.org/bot" + TG + "/sendMessage",
                  data={"chat_id": CI, "text": text}, timeout=30)
    print("Sent: " + action + " Conf " + str(conf))

if __name__ == "__main__":
    run()
