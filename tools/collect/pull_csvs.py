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

    success_count = 0
    fail_count = 0
    
    for n in cfg["nodes"]:
        node_id = n['id']
        base = f"http://{n['ip']}:{n['dashboard_port']}/api/export"
        
        try:
            print(f"[CSV] Fetching from {node_id} ({n['ip']}:{n['dashboard_port']})...")
            bm = fetch(f"{base}/block-metrics.csv")
            tl = fetch(f"{base}/transaction-lifecycle.csv")
            open(os.path.join(a.out, f"{node_id}-block-metrics.csv"), "w").write(bm)
            open(os.path.join(a.out, f"{node_id}-tx-lifecycle.csv"), "w").write(tl)
            print(f"[CSV] ✓ {node_id} - Success")
            success_count += 1
        except requests.exceptions.ConnectionError as e:
            print(f"[CSV] ✗ {node_id} - Connection refused (dashboard not running or unreachable)")
            fail_count += 1
        except requests.exceptions.Timeout as e:
            print(f"[CSV] ✗ {node_id} - Timeout (node may be slow or unresponsive)")
            fail_count += 1
        except Exception as e:
            print(f"[CSV] ✗ {node_id} - Error: {e}")
            fail_count += 1
    
    print(f"\n[CSV] Collection complete: {success_count} successful, {fail_count} failed")
    
    if fail_count > 0:
        print(f"\n[CSV] WARNING: Some nodes could not be reached.")
        print(f"[CSV] Make sure blockchain-node service is running on all Raspberry Pis:")
        print(f"[CSV]   ssh node@NODE_IP 'sudo systemctl status blockchain-node'")


