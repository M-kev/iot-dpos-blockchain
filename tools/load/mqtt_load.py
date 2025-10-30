import argparse, time, json, random, threading
from paho.mqtt import client as mqtt


def publisher(args, topic, payload_gen):
    client_id = f"load-{topic}-{random.randint(1,1_000_000)}"
    try:
        # Try new paho-mqtt 2.x API (Python 3.13+)
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=client_id)
    except (AttributeError, TypeError):
        # Fallback to old API (paho-mqtt 1.x)
        c = mqtt.Client(client_id=client_id)
    
    if args.username:
        c.username_pw_set(args.username, args.password)
    
    try:
        c.connect(args.host, args.port, keepalive=60)
        c.loop_start()  # Start network loop in background thread
    except Exception as e:
        print(f"[ERROR] Failed to connect to {args.host}:{args.port} - {e}")
        return
    
    interval = 1.0 / args.rate if args.rate > 0 else 0
    end_time = time.time() + args.duration
    next_t = time.time()
    
    try:
        while time.time() < end_time:
            payload = payload_gen()
            result = c.publish(topic, json.dumps(payload), qos=args.qos)
            if result.rc != 0:
                print(f"[WARN] Publish failed with rc={result.rc}")
            if interval == 0:
                continue
            next_t += interval
            time.sleep(max(0, next_t - time.time()))
    except Exception as e:
        print(f"[ERROR] Publisher thread error: {e}")
    finally:
        c.loop_stop()
        c.disconnect()


def metrics_payload(node_id):
    t = time.time()
    return {
        "node_id": node_id,
        "timestamp": t,
        "cpu_percent": random.uniform(0.2, 30.0),
        "memory_percent": random.uniform(5.0, 40.0),
        "temperature": random.uniform(35.0, 65.0),
        "power_usage": random.uniform(0.4, 2.5),
        "block_count": 0,
        "pending_transactions": 0,
        "current_stake": 1000
    }


def tx_payload():
    t = time.time()
    return {"type": "transfer", "sender": "bench", "recipient": "sink", "amount": 1, "timestamp": t}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", required=True)
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--username", default="")
    p.add_argument("--password", default="")
    p.add_argument("--metrics_topic", required=True)
    p.add_argument("--tx_topic", required=True)
    p.add_argument("--nodes", type=int, default=10)
    p.add_argument("--rate", type=float, default=10)
    p.add_argument("--qos", type=int, default=1)
    p.add_argument("--duration", type=int, default=300)
    args = p.parse_args()

    print(f"[MQTT Load] Starting {args.nodes} metric publishers + 1 transaction publisher")
    print(f"[MQTT Load] Target: {args.host}:{args.port} (auth: {bool(args.username)})")
    print(f"[MQTT Load] Rate: {args.rate} msg/sec, Duration: {args.duration}s")
    print(f"[MQTT Load] Topics: metrics={args.metrics_topic}, tx={args.tx_topic}")

    threads = []
    for i in range(args.nodes):
        nid = f"sim_node_{i+1}"
        threads.append(threading.Thread(target=publisher, args=(args, args.metrics_topic, lambda nid=nid: metrics_payload(nid))))

    threads.append(threading.Thread(target=publisher, args=(args, args.tx_topic, tx_payload)))

    print(f"[MQTT Load] Starting {len(threads)} publisher threads...")
    [t.start() for t in threads]
    
    print(f"[MQTT Load] All threads started. Publishing for {args.duration} seconds...")
    [t.join() for t in threads]
    
    print("[MQTT Load] All publisher threads completed.")


