#!/usr/bin/env python3
"""纯 stdlib 技术指标计算（无需 pandas/numpy）。
输入: rows = [[date, open, close, high, low, volume], ...]（腾讯K线格式，前复权）
用法示例见 __main__：读取 ~/.hermes/stock_data/<code>_day.json 并打印最新指标。
"""
import json, math, os, sys


def ema(vals, n):
    k = 2.0 / (n + 1)
    out, prev = [], None
    for v in vals:
        prev = v if prev is None else v * k + prev * (1 - k)
        out.append(prev)
    return out


def sma_series(vals, n):
    out = []
    for i in range(len(vals)):
        out.append(None if i < n - 1 else sum(vals[i - n + 1:i + 1]) / n)
    return out


def rsi_wilder(closes, n=14):
    """Wilder 平滑 RSI。前 n 个值为 None。"""
    out = [None] * n
    avg_gain = avg_loss = None
    for i in range(n, len(closes)):
        gain = max(closes[i] - closes[i - 1], 0.0)
        loss = max(closes[i - 1] - closes[i], 0.0)
        if avg_gain is None:
            avg_gain, avg_loss = gain, loss
        else:
            avg_gain = (avg_gain * (n - 1) + gain) / n
            avg_loss = (avg_loss * (n - 1) + loss) / n
        out.append(100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss))
    return out


def kdj(highs, lows, closes, n=9):
    k = d = 50.0
    ks, ds, js = [], [], []
    for i in range(len(closes)):
        lo = min(lows[max(0, i - n + 1):i + 1])
        hi = max(highs[max(0, i - n + 1):i + 1])
        rsv = 50.0 if hi == lo else (closes[i] - lo) / (hi - lo) * 100.0
        k = k * 2.0 / 3.0 + rsv / 3.0
        d = d * 2.0 / 3.0 + k / 3.0
        ks.append(k); ds.append(d); js.append(3 * k - 2 * d)
    return ks, ds, js


def boll(closes, n=20, width=2.0):
    mid = sma_series(closes, n)
    up, lo = [], []
    for i in range(len(closes)):
        if mid[i] is None:
            up.append(None); lo.append(None)
        else:
            w = closes[i - n + 1:i + 1]
            sd = math.sqrt(sum((x - mid[i]) ** 2 for x in w) / n)
            up.append(mid[i] + width * sd); lo.append(mid[i] - width * sd)
    return up, mid, lo


def atr(highs, lows, closes, n=14):
    trs = []
    for i in range(len(closes)):
        if i == 0:
            trs.append(highs[i] - lows[i])
        else:
            trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    return sma_series(trs, n)


def macd(closes, fast=12, slow=26, signal=9):
    ef, es = ema(closes, fast), ema(closes, slow)
    dif = [a - b for a, b in zip(ef, es)]
    dea = ema(dif, signal)
    hist = [2 * (a - b) for a, b in zip(dif, dea)]
    return dif, dea, hist


def cross(prev_fast, prev_slow, fast, slow):
    """返回 'golden'/'death'/None（上一周期 vs 本周期）"""
    if prev_fast <= prev_slow and fast > slow:
        return "golden"
    if prev_fast >= prev_slow and fast < slow:
        return "death"
    return None


def analyze(rows):
    """rows: [[date, open, close, high, low, volume], ...] → 指标字典"""
    closes = [r[2] for r in rows]
    highs = [r[3] for r in rows]
    lows = [r[4] for r in rows]
    vols = [r[5] for r in rows]
    n = len(rows)
    ind = {"date": rows[-1][0], "close": closes[-1], "n": n}
    for ma in (5, 10, 20, 50, 120, 250):
        v = sma_series(closes, ma)[-1]
        ind[f"MA{ma}"] = round(v, 3) if v else None
    dif, dea, hist = macd(closes)
    ind.update(MACD_DIF=round(dif[-1], 3), MACD_DEA=round(dea[-1], 3),
               MACD_HIST=round(hist[-1], 3), MACD_HIST_PREV=round(hist[-2], 3))
    ind["RSI14"] = round(rsi_wilder(closes)[-1], 2)
    k, d, j = kdj(highs, lows, closes)
    ind.update(KDJ_K=round(k[-1], 2), KDJ_D=round(d[-1], 2), KDJ_J=round(j[-1], 2))
    bu, bm, bl = boll(closes)
    ind.update(BOLL_UP=round(bu[-1], 3), BOLL_MID=round(bm[-1], 3), BOLL_LOW=round(bl[-1], 3))
    a = atr(highs, lows, closes)[-1]
    ind["ATR14"] = round(a, 3)
    ind["ATR_PCT"] = round(a / closes[-1] * 100, 2) if closes[-1] else None
    v5 = sum(vols[-5:]) / 5
    v20 = sum(vols[-20:]) / 20
    ind.update(VOL_LAST=vols[-1], VOL_MA5=round(v5), VOL_MA20=round(v20),
               VOL_RATIO_5_20=round(v5 / v20, 2) if v20 else None)
    for w in (60, 120, 250):
        ind[f"HIGH_{w}"] = max(highs[-w:])
        ind[f"LOW_{w}"] = min(lows[-w:])
    return ind


if __name__ == "__main__":
    # 用法: python3 technicals.py <kline.json>
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.hermes/stock_data/01548_day.json")
    with open(path) as f:
        rows = json.load(f)
    ind = analyze(rows)
    print(json.dumps(ind, ensure_ascii=False, indent=1))
