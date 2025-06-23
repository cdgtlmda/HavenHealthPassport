/**
 * Raft Election Parameters Configuration
 * Haven Health Passport - Blockchain Consensus
 *
 * This module manages the election parameters for Raft consensus protocol
 */

export interface ElectionTiming {
  election: {
    baseTimeout: number;
    randomRange: number;
    minTimeout: number;
    maxTimeout: number;
  };
  heartbeat: {
    interval: number;
    timeoutMultiplier: number;
  };
  requestVote: {
    timeout: number;
    maxRetries: number;
  };
}

export interface LeaderElectionPolicy {
  preVote: {
    enabled: boolean;
    timeout: number;
  };
  priorityElection: {
    enabled: boolean;
    priorities: Record<string, number>;
    priorityDelay: number;
  };
  checkQuorum: {
    enabled: boolean;
    interval: number;
  };
  leaderLease: {
    enabled: boolean;
    duration: number;
    renewalThreshold: number;
  };
}
export interface ElectionOptimization {
  adaptiveTimeout: {
    enabled: boolean;
    failureMultiplier: number;
    successDivisor: number;
    minAdaptiveTimeout: number;
    maxAdaptiveTimeout: number;
  };
  fastElection: {
    enabled: boolean;
    timeout: number;
    gracefulOnly: boolean;
  };
}

export interface SplitBrainPrevention {
  requireMajority: boolean;
  partitionDetection: {
    enabled: boolean;
    detectionTimeout: number;
    onPartition: 'stepdown' | 'readonly' | 'continue';
  };
  witness: {
    enabled: boolean;
    nodes: string[];
  };
}

export interface ElectionMonitoring {
  metrics: Array<{
    name: string;
    type: 'histogram' | 'counter' | 'gauge';
    description: string;
    buckets?: number[];
  }>;
  alerts: Array<{
    name: string;
    condition: string;
    severity: 'warning' | 'critical';
    description: string;
  }>;
}

export interface ElectionParametersConfig {
  metadata: {
    name: string;
    description: string;
    version: string;
    lastUpdated: string;
  };
  timing: ElectionTiming;
  leaderElection: LeaderElectionPolicy;
  optimization: ElectionOptimization;
  splitBrainPrevention: SplitBrainPrevention;
  monitoring: ElectionMonitoring;
}
