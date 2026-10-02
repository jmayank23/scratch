import sys, numpy as np, pandas as pd
sys.argv=['x', sys.argv[1]]
exec(open(__file__.replace("rolling_backtest.py","forecast.py")).read().split("tok = ")[0])
from model import Kronos, KronosTokenizer, KronosPredictor
tok = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
p = KronosPredictor(Kronos.from_pretrained("NeoQuasar/Kronos-small"), tok, device="cpu")
cols=["open","high","low","close","volume","amount"]; H=20
for lb in [400, 128]:
    k_err=[]; n_err=[]; hits=[]
    for end in range(len(df)-H, len(df)-H-12*H, -H):
        hist=df.iloc[end-lb:end]; true=df.iloc[end:end+H]
        f=p.predict(df=hist[cols], x_timestamp=hist.timestamps, y_timestamp=true.timestamps.reset_index(drop=True),
                    pred_len=H, sample_count=5, verbose=False)["close"].values
        last=hist.close.iloc[-1]
        k_err.append(abs(f[-1]-true.close.iloc[-1])/last); n_err.append(abs(last-true.close.iloc[-1])/last)
        hits.append(np.sign(f[-1]-last)==np.sign(true.close.iloc[-1]-last))
    print(f"lookback {lb}: 20d-ahead error Kronos {np.mean(k_err):.1%} vs flat {np.mean(n_err):.1%}, direction hit {np.mean(hits):.0%} over {len(hits)} windows")
