#!/usr/bin/env bash
set -euo pipefail

IFACE=${1:-eth0}
PROFILE=${2:-clear}

case "$PROFILE" in
  clear)
    sudo tc qdisc del dev $IFACE root 2>/dev/null || true
    ;;
  baseline)
    sudo tc qdisc replace dev $IFACE root netem delay 10ms 2ms loss 0.1%
    ;;
  moderate)
    sudo tc qdisc replace dev $IFACE root netem delay 80ms 20ms distribution normal loss 1% reorder 1% 50%
    ;;
  harsh)
    sudo tc qdisc replace dev $IFACE root netem delay 200ms 50ms distribution normal loss 5% duplicate 0.5%
    ;;
  *)
    echo "unknown profile"; exit 1;;
esac

echo "Applied netem profile: $PROFILE on $IFACE"

