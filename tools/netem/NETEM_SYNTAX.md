# TC Netem Syntax Reference

## What is Jitter?

**Jitter** is the variation in network latency over time. It represents how much the delay fluctuates around the average.

### Real-World Example:
- **No jitter**: Every packet takes exactly 10ms (10ms, 10ms, 10ms, ...)
- **With 2ms jitter**: Packets take 8-12ms (9ms, 11ms, 10ms, 12ms, 8ms, ...)

### Why It Matters for IoT Blockchain:
- WiFi networks have natural jitter due to interference and contention
- Jitter affects block propagation consistency
- High jitter can cause consensus disagreements if blocks arrive out of order

## Correct TC Netem Syntax

### Format:
```bash
tc qdisc add dev <interface> root netem delay <TIME> [JITTER] [distribution <DIST>] [loss <PERCENT>] [duplicate <PERCENT>] [reorder <PERCENT> <CORRELATION>]
```

### Key Rules:
1. **Jitter comes directly after delay** - no "jitter" keyword
2. **Distribution is optional** but recommended for realistic behavior
3. **Order matters** - delay must come before loss/duplicate/reorder

### Examples:

#### ✓ Correct:
```bash
# 10ms delay with 2ms jitter
tc qdisc replace dev eth0 root netem delay 10ms 2ms loss 0.1%

# 80ms delay with 20ms jitter, normal distribution
tc qdisc replace dev eth0 root netem delay 80ms 20ms distribution normal loss 1%

# 200ms delay with 50ms jitter, 5% packet loss
tc qdisc replace dev eth0 root netem delay 200ms 50ms distribution normal loss 5%
```

#### ✗ Incorrect:
```bash
# DON'T use "jitter" keyword
tc qdisc replace dev eth0 root netem delay 10ms jitter 2ms  # ❌ ERROR

# DON'T put loss before delay
tc qdisc replace dev eth0 root netem loss 1% delay 10ms 2ms  # ❌ Wrong order
```

## Distribution Types

When you specify jitter, you can also specify how the jitter is distributed:

| Distribution | Behavior | Use Case |
|--------------|----------|----------|
| `uniform` | Equal probability across the range | Simple testing |
| `normal` (Gaussian) | Bell curve, most values near average | **Realistic WiFi/LTE** |
| `pareto` | Long tail, occasional high spikes | Congested networks |
| `paretonormal` | Mix of normal and pareto | Very realistic |

### Example with Distribution:
```bash
# 80ms ± 20ms with normal distribution (most packets will be 60-100ms)
tc qdisc replace dev eth0 root netem delay 80ms 20ms distribution normal
```

## Our Blockchain Profiles

### Baseline (Good WiFi)
```bash
delay 10ms 2ms loss 0.1%
```
- **Average latency**: 10ms
- **Jitter range**: 8-12ms (±2ms)
- **Packet loss**: 0.1% (1 in 1000 packets)
- **Simulates**: Good quality home/office WiFi

### Moderate (Congested Network)
```bash
delay 80ms 20ms distribution normal loss 1% reorder 1% 50%
```
- **Average latency**: 80ms
- **Jitter range**: 40-120ms (±40ms with normal distribution)
- **Packet loss**: 1% (1 in 100 packets)
- **Reordering**: 1% of packets arrive out of order
- **Simulates**: Cellular 4G or congested WiFi

### Harsh (Satellite/Remote)
```bash
delay 200ms 50ms distribution normal loss 5% duplicate 0.5%
```
- **Average latency**: 200ms
- **Jitter range**: 100-300ms (±100ms with normal distribution)
- **Packet loss**: 5% (1 in 20 packets)
- **Duplication**: 0.5% packets duplicated (simulates retransmissions)
- **Simulates**: Satellite links, very poor 3G, or IoT over LoRaWAN

## Calculating Effective Latency Range

For **normal distribution** with jitter:

```
Typical range ≈ delay ± (2 × jitter)
```

Examples:
- `delay 10ms 2ms` → Typical range: 6-14ms
- `delay 80ms 20ms` → Typical range: 40-120ms
- `delay 200ms 50ms` → Typical range: 100-300ms

## Verifying Applied Settings

To check what's currently applied:

```bash
tc qdisc show dev eth0
```

Output example:
```
qdisc netem 8001: root refcnt 2 limit 1000 delay 10ms 2ms loss 0.1%
```

## Clearing Settings

To remove all netem impairments:

```bash
sudo tc qdisc del dev eth0 root 2>/dev/null
```

## Common Errors

### 1. "What is jitter?" error
**Cause**: Using `jitter` keyword instead of directly specifying value  
**Fix**: Remove `jitter` keyword → `delay 10ms 2ms` not `delay 10ms jitter 2ms`

### 2. "Cannot find device" error
**Cause**: Wrong network interface name  
**Fix**: Check interface name with `ip link show` or `ifconfig`  
Common names: `eth0`, `wlan0`, `enp0s3`, `wlp3s0`

### 3. "Operation not permitted"
**Cause**: Need root privileges  
**Fix**: Add `sudo` before the command

### 4. Settings don't seem to apply
**Cause**: Using `add` instead of `replace` when rules already exist  
**Fix**: Use `tc qdisc replace` or clear first with `tc qdisc del`

## Testing Impact on Blockchain

After applying netem settings, test the impact:

1. **Check MQTT latency**: 
   ```bash
   mosquitto_sub -h BROKER_IP -t 'blockchain/blocks' -v
   ```

2. **Measure block propagation**:
   - Check dashboard block intervals
   - Compare timestamps between nodes

3. **Monitor consensus time**:
   - Should increase with higher latency
   - Watch for validator disagreements in harsh profiles

## References

- [Linux tc-netem man page](https://man7.org/linux/man-pages/man8/tc-netem.8.html)
- [NetEm Wiki](https://wiki.linuxfoundation.org/networking/netem)

