"""Usage: python forecast.py TICKER [horizon_days=20] [model=small|base] [samples=10]"""
import sys, json, urllib.request, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from model import Kronos, KronosTokenizer, KronosPredictor

ticker = sys.argv[1].upper()
horizon = int(sys.argv[2]) if len(sys.argv) > 2 else 20
size = sys.argv[3] if len(sys.argv) > 3 else "small"
samples = int(sys.argv[4]) if len(sys.argv) > 4 else 10
lookback = 400

def fetch(t):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=5y&interval=1d"
    r = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})))["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({"timestamps": pd.to_datetime(r["timestamp"], unit="s").normalize(),
                       **{k: q[k] for k in ["open", "high", "low", "close", "volume"]}}).dropna()
    df["amount"] = df["volume"] * df[["open", "high", "low", "close"]].mean(axis=1)
    return df.reset_index(drop=True)

df = fetch(ticker)
tok = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
mdl = Kronos.from_pretrained(f"NeoQuasar/Kronos-{size}")
pred = KronosPredictor(mdl, tok, device="cpu", max_context=512)
cols = ["open", "high", "low", "close", "volume", "amount"]

def run(hist, future_ts):
    paths = [pred.predict(df=hist[cols], x_timestamp=hist["timestamps"], y_timestamp=pd.Series(future_ts),
                          pred_len=len(future_ts), T=1.0, top_p=0.9, sample_count=1, verbose=False)["close"].values
             for _ in range(samples)]
    return np.array(paths)

# 1) Backtest: hide the last `horizon` days and see how the forecast compares
bt_hist, bt_true = df.iloc[-lookback - horizon:-horizon], df.iloc[-horizon:]
bt = run(bt_hist, bt_true["timestamps"].values)
last = bt_hist["close"].iloc[-1]
mae = np.abs(np.median(bt, 0) - bt_true["close"].values).mean()
dir_ok = np.sign(np.median(bt, 0)[-1] - last) == np.sign(bt_true["close"].iloc[-1] - last)

# 2) Forward forecast
hist = df.iloc[-lookback:]
fut_ts = pd.bdate_range(hist["timestamps"].iloc[-1] + pd.Timedelta(days=1), periods=horizon)
fw = run(hist, fut_ts.values)
lo, med, hi = np.percentile(fw, [10, 50, 90], axis=0)

out = pd.DataFrame({"date": fut_ts.date, "p10": lo, "median": med, "p90": hi}).round(2)
out.to_csv(f"{ticker}_forecast.csv", index=False)
fig, ax = plt.subplots(1, 2, figsize=(14, 5))
ax[0].plot(bt_hist["timestamps"].iloc[-120:], bt_hist["close"].iloc[-120:], color="#444", label="history")
ax[0].plot(bt_true["timestamps"], bt_true["close"], color="#2a7", label="actual")
ax[0].plot(bt_true["timestamps"], np.median(bt, 0), color="#36c", label="Kronos median")
ax[0].set_title(f"{ticker} backtest (last {horizon} days hidden)"); ax[0].legend()
ax[1].plot(hist["timestamps"].iloc[-120:], hist["close"].iloc[-120:], color="#444", label="history")
ax[1].plot(fut_ts, med, color="#36c", label="median"); ax[1].fill_between(fut_ts, lo, hi, color="#36c", alpha=.2, label="10–90%")
ax[1].set_title(f"{ticker} {horizon}-day forecast (Kronos-{size}, {samples} paths)"); ax[1].legend()
fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(f"{ticker}_forecast.png", dpi=110)

print(f"Last close {hist['timestamps'].iloc[-1].date()}: {hist['close'].iloc[-1]:.2f}")
print(f"Backtest: MAE {mae:.2f} ({mae/last:.1%} of price), direction {'right' if dir_ok else 'wrong'}")
print(out.iloc[[0, horizon // 2, -1]].to_string(index=False))
