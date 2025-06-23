# Election Parameters Configuration Documentation
# Haven Health Passport - Blockchain Consensus

## Overview

This document describes the Raft consensus election parameters configuration for the Haven Health Passport blockchain network. These parameters control how leader elections occur and ensure high availability.

## Key Election Parameters

### 1. Election Timing

- **Base Election Timeout**: 5000ms (5 seconds)
  - Time a follower waits before starting an election
  - Prevents unnecessary elections during normal operation

- **Random Range**: 2500ms
  - Adds randomness to prevent split votes
  - Actual timeout = 5000ms + random(0-2500ms)

- **Heartbeat Interval**: 500ms
  - Leader sends heartbeats every 500ms
  - Followers expect heartbeat within 5000ms (10x interval)

### 2. Leader Election Policies

#### Pre-Vote Mechanism
- **Enabled**: Yes
- **Timeout**: 2000ms
- **Purpose**: Prevents disruption from partitioned nodes

#### Priority-Based Election
- **Node Priorities**:
  - orderer0: 100 (Primary)
  - orderer1: 80 (Backup Primary)
  - orderer2: 60 (Secondary)
  - orderer3: 60 (Secondary)
  - orderer4: 40 (Arbiter)
- **Priority Delay**: 1000ms between priority levels

#### Check Quorum
- **Enabled**: Yes
- **Interval**: 2500ms
- **Purpose**: Ensures leader maintains majority support

### 3. Optimization Features

#### Adaptive Timeout
- Automatically adjusts election timeout based on network conditions
- Increases timeout by 1.5x on failure
- Decreases timeout by 1.1x on success
- Bounds: 3000ms - 15000ms

#### Fast Election
- For graceful leader transitions only
- Timeout: 1000ms
- Reduces downtime during planned maintenance
