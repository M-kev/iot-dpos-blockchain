import argparse, os, glob
import pandas as pd
from pathlib import Path


def load_concat(pattern: str, node_key: str) -> pd.DataFrame:
    frames = []
    for fn in glob.glob(pattern):
        try:
            df = pd.read_csv(fn)
            df[node_key] = Path(fn).name.split("-")[0]
            frames.append(df)
        except Exception:
            continue
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="indir", required=True)
    ap.add_argument("--out", dest="outdir", required=True)
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    merged_dir = os.path.join(a.outdir, "merged")
    os.makedirs(merged_dir, exist_ok=True)

    bm = load_concat(os.path.join(a.indir, "*-block-metrics.csv"), "node_id")
    tl = load_concat(os.path.join(a.indir, "*-tx-lifecycle.csv"), "node_id")

    kpis = {}
    if not bm.empty:
        kpis["blocks_total"] = int(bm["block_index"].nunique())
        kpis["block_interval_avg"] = float(bm["block_interval"].mean())
        kpis["block_interval_p95"] = float(bm["block_interval"].quantile(0.95))
        kpis["consensus_time_avg"] = float(bm["consensus_time"].mean())
        kpis["energy_cumulative"] = float(bm["power_usage"].sum())
        bm.to_csv(os.path.join(merged_dir, "block-metrics-merged.csv"), index=False)

    if not tl.empty and "included_timestamp" in tl.columns and "received_timestamp" in tl.columns:
        tl["latency"] = tl["included_timestamp"] - tl["received_timestamp"]
        kpis["tx_latency_avg"] = float(tl["latency"].dropna().mean())
        kpis["tx_latency_p95"] = float(tl["latency"].dropna().quantile(0.95))
        kpis["tx_pending"] = int(tl["included_timestamp"].isna().sum())
        kpis["tx_total"] = int(len(tl))
        tl.to_csv(os.path.join(merged_dir, "tx-lifecycle-merged.csv"), index=False)

    # Save KPIs
    pd.DataFrame([kpis]).to_csv(os.path.join(merged_dir, "kpis.csv"), index=False)

    # Minimal HTML report
    lines = ["<html><body><h2>Benchmark Report</h2><pre>"]
    for k, v in kpis.items():
        lines.append(f"{k}: {v}")
    lines.append("</pre></body></html>")
    with open(os.path.join(a.outdir, "report.html"), "w") as f:
        f.write("\n".join(lines))
    print("Report generated.")


