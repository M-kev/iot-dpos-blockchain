import argparse, os, requests, yaml


def fetch(url: str) -> str:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.text


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    with open(a.config, "r") as f:
        cfg = yaml.safe_load(f)

    for n in cfg["nodes"]:
        base = f"http://{n['ip']}:{n['dashboard_port']}/api/export"
        bm = fetch(f"{base}/block-metrics.csv")
        tl = fetch(f"{base}/transaction-lifecycle.csv")
        open(os.path.join(a.out, f"{n['id']}-block-metrics.csv"), "w").write(bm)
        open(os.path.join(a.out, f"{n['id']}-tx-lifecycle.csv"), "w").write(tl)
    print("CSV collection complete.")


