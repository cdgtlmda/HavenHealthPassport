/**
 * Election Parameters Manager
 * Haven Health Passport - Blockchain Consensus
 */

import { ElectionParametersConfig } from './election-parameters';
import * as fs from 'fs';
import * as path from 'path';

export class ElectionParametersManager {
  private config: ElectionParametersConfig;

  constructor() {
    this.config = this.initializeDefaultConfig();
  }

  /**
   * Initialize default election parameters optimized for 5-node cluster
   */
  private initializeDefaultConfig(): ElectionParametersConfig {
    return {
      metadata: {
        name: 'haven-health-election-params',
        description: 'Raft election parameters for Haven Health Passport ordering service',
        version: '1.0.0',
        lastUpdated: new Date().toISOString()
      },
      timing: {
        election: {
          baseTimeout: 5000,
          randomRange: 2500,
          minTimeout: 3000,
          maxTimeout: 10000
        },
        heartbeat: {
          interval: 500,
          timeoutMultiplier: 10
        },
        requestVote: {
          timeout: 3000,
          maxRetries: 2
        }
      },
      leaderElection: this.createLeaderElectionPolicy(),
      optimization: this.createOptimizationConfig(),
      splitBrainPrevention: this.createSplitBrainConfig(),
      monitoring: this.createMonitoringConfig()
    };
  }
  /**
   * Create leader election policy with node priorities
   */
  private createLeaderElectionPolicy() {
    return {
      preVote: {
        enabled: true,
        timeout: 2000
      },
      priorityElection: {
        enabled: true,
        priorities: {
          'orderer0.havenhealthpassport.com': 100,
          'orderer1.havenhealthpassport.com': 80,
          'orderer2.havenhealthpassport.com': 60,
          'orderer3.havenhealthpassport.com': 60,
          'orderer4.havenhealthpassport.com': 40
        },
        priorityDelay: 1000
      },
      checkQuorum: {
        enabled: true,
        interval: 2500
      },
      leaderLease: {
        enabled: true,
        duration: 10000,
        renewalThreshold: 0.75
      }
    };
  }

  /**
   * Create optimization configuration for adaptive behavior
   */
  private createOptimizationConfig() {
    return {
      adaptiveTimeout: {
        enabled: true,
        failureMultiplier: 1.5,
        successDivisor: 1.1,
        minAdaptiveTimeout: 3000,
        maxAdaptiveTimeout: 15000
      },
      fastElection: {
        enabled: true,
        timeout: 1000,
        gracefulOnly: true
      }
    };
  }
  /**
   * Create split brain prevention configuration
   */
  private createSplitBrainConfig() {
    return {
      requireMajority: true,
      partitionDetection: {
        enabled: true,
        detectionTimeout: 30000,
        onPartition: 'stepdown' as const
      },
      witness: {
        enabled: false,
        nodes: []
      }
    };
  }

  /**
   * Create monitoring configuration with metrics and alerts
   */
  private createMonitoringConfig() {
    return {
      metrics: [
        {
          name: 'election_duration_ms',
          type: 'histogram' as const,
          description: 'Time taken to complete leader election',
          buckets: [100, 500, 1000, 2000, 5000, 10000]
        },
        {
          name: 'election_attempts_total',
          type: 'counter' as const,
          description: 'Total number of election attempts'
        },
        {
          name: 'current_leader',
          type: 'gauge' as const,
          description: 'ID of current Raft leader'
        },
        {
          name: 'term_changes_total',
          type: 'counter' as const,
          description: 'Total number of term changes'
        }
      ],
      alerts: [
        {
          name: 'FrequentElections',
          condition: 'rate(election_attempts_total[5m]) > 0.5',
          severity: 'warning' as const,
          description: 'More than 3 elections in 5 minutes'
        },
        {
          name: 'SlowElection',
          condition: 'election_duration_ms > 5000',
          severity: 'warning' as const,
          description: 'Election took longer than 5 seconds'
        },
        {
          name: 'NoLeader',
          condition: 'current_leader == -1 for 30s',
          severity: 'critical' as const,
          description: 'No leader elected for 30 seconds'
        }
      ]
    };
  }
  /**
   * Validate election parameters
   */
  public validateParameters(): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    // Validate timing parameters
    if (this.config.timing.heartbeat.interval >= this.config.timing.election.baseTimeout) {
      errors.push('Heartbeat interval must be less than election timeout');
    }

    if (this.config.timing.election.minTimeout >= this.config.timing.election.maxTimeout) {
      errors.push('Min timeout must be less than max timeout');
    }

    // Validate priorities sum to reasonable value
    const priorities = Object.values(this.config.leaderElection.priorityElection.priorities);
    if (priorities.length !== 5) {
      errors.push('Must have exactly 5 node priorities defined');
    }

    // Validate monitoring configuration
    if (this.config.monitoring.metrics.length === 0) {
      errors.push('At least one metric must be defined');
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }

  /**
   * Export configuration to file
   */
  public async exportConfig(outputPath: string): Promise<void> {
    const validation = this.validateParameters();
    if (!validation.valid) {
      throw new Error(`Invalid configuration: ${validation.errors.join(', ')}`);
    }

    const json = JSON.stringify(this.config, null, 2);
    await fs.promises.writeFile(outputPath, json);
  }

  /**
   * Get current configuration
   */
  public getConfig(): ElectionParametersConfig {
    return this.config;
  }

  /**
   * Update specific timing parameter
   */
  public updateTiming(param: keyof ElectionParametersConfig['timing'], value: any): void {
    this.config.timing = {
      ...this.config.timing,
      [param]: value
    };
  }
}

// Export singleton instance
export const electionParametersManager = new ElectionParametersManager();
