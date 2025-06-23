/**
 * Heartbeat and Consensus Integration
 * Haven Health Passport - Blockchain Infrastructure
 */

import { heartbeatManager } from './heartbeat-interval-manager';
import { electionParametersManager } from './election-parameters-manager';

export interface RaftTimingConfig {
  tickInterval: string;
  electionTick: number;
  heartbeatTick: number;
  maxInflightBlocks: number;
  snapshotIntervalSize: number;
}

export class ConsensusTimingIntegration {
  /**
   * Generate integrated Raft timing configuration
   */
  public generateRaftTiming(): RaftTimingConfig {
    const heartbeatConfig = heartbeatManager.getConfig();
    const electionConfig = electionParametersManager.getConfig();

    // Calculate ticks based on intervals
    const tickInterval = heartbeatConfig.interval;
    const electionTimeout = electionConfig.timing.election.baseTimeout;

    return {
      tickInterval: `${tickInterval}ms`,
      electionTick: Math.floor(electionTimeout / tickInterval),
      heartbeatTick: 1,  // Always 1 for heartbeat
      maxInflightBlocks: 5,
      snapshotIntervalSize: 20 * 1024 * 1024  // 20MB
    };
  }

  /**
   * Validate timing consistency
   */
  public validateTimingConsistency(): { valid: boolean; errors: string[] } {
    const errors: string[] = [];
    const heartbeatInterval = heartbeatManager.getConfig().interval;
    const electionTimeout = electionParametersManager.getConfig().timing.election.baseTimeout;

    if (heartbeatInterval >= electionTimeout) {
      errors.push('Heartbeat interval must be less than election timeout');
    }

    if (electionTimeout < heartbeatInterval * 5) {
      errors.push('Election timeout should be at least 5x heartbeat interval');
    }

    return { valid: errors.length === 0, errors };
  }
}

export const timingIntegration = new ConsensusTimingIntegration();
