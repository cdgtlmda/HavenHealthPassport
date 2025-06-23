# Heartbeat Interval Documentation
# Haven Health Passport - Blockchain Consensus

## Overview

The heartbeat interval is a critical parameter in Raft consensus that determines how frequently the leader sends heartbeat messages to maintain its authority and prevent unnecessary elections.

## Configured Settings

### Primary Configuration
- **Heartbeat Interval**: 500ms
- **Heartbeat Tick**: 1 (in Raft tick units)
- **Tick Interval**: 500ms

### Timeout Settings
- **Follower Timeout**: 5000ms (10x heartbeat interval)
- **Grace Period**: 500ms additional buffer
- **Effective Timeout**: 5500ms before election starts

### Jitter Configuration
- **Enabled**: Yes
- **Range**: ±50ms
- **Purpose**: Prevents synchronized heartbeats (thundering herd)

## Rationale

### Why 500ms?
1. **Network Latency**: Accommodates typical cloud network latency (10-50ms)
2. **Failure Detection**: Detects leader failure within 5-5.5 seconds
3. **Network Overhead**: Balanced - not too frequent, not too sparse
4. **AWS Compatibility**: Optimized for AWS Managed Blockchain infrastructure

### Relationship to Election Timeout
- Election timeout: 5000ms (base)
- Heartbeat interval: 500ms
- Ratio: 1:10 (recommended for stability)

## Monitoring

### Key Metrics
1. **heartbeat_interval_current**: Current adaptive interval
2. **heartbeat_success_rate**: Percentage of successful heartbeats
3. **heartbeat_send_duration**: Time to reach all followers
4. **follower_last_heartbeat**: Time since last successful heartbeat

### Alert Thresholds
- **Warning**: Success rate < 95%
- **Warning**: Send duration > 250ms
- **Critical**: No heartbeat for 5 seconds

## Tuning Guide

### High Latency Networks
If experiencing high network latency:
- Increase interval to 750-1000ms
- Increase follower timeout multiplier to 12-15
- Enable larger jitter range (±100ms)

### Low Latency Networks
For optimal performance in low-latency environments:
- Decrease interval to 250-300ms
- Keep follower timeout multiplier at 10
- Reduce jitter range (±25ms)

### Load-Based Adjustment
Under high transaction load:
- Temporarily increase interval to reduce overhead
- Maximum adaptive interval: 5000ms
- Automatic adjustment when load decreases
