#!/usr/bin/env node

/**
 * Configure Heartbeat Interval for Raft Consensus
 * Haven Health Passport - Blockchain Configuration
 */

import { heartbeatManager } from '../src/consensus/heartbeat-interval-manager';
import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';

// Command line arguments
const args = process.argv.slice(2);
const apply = args.includes('--apply');
const validate = args.includes('--validate');

async function main() {
  console.log('Haven Health Passport - Heartbeat Interval Configuration');
  console.log('=====================================================\n');

  try {
    // Get current configuration
    const config = heartbeatManager.getConfig();
    const metrics = heartbeatManager.getMetrics();

    // Validate configuration
    const validation = heartbeatManager.validateConfig();

    if (!validation.valid) {
      console.error('❌ Configuration validation failed:');
      validation.errors.forEach(err => console.error(`   - ${err}`));
      process.exit(1);
    }

    console.log('✅ Heartbeat configuration validated successfully\n');

    // Display configuration
    console.log('Current Configuration:');
    console.log(`- Base Interval: ${config.interval}ms`);
    console.log(`- Jitter Enabled: ${config.jitterEnabled}`);
    console.log(`- Jitter Range: ±${config.jitterRange}ms`);
    console.log(`- Adaptive: ${config.adaptiveEnabled}`);
    console.log(`- Min Interval: ${config.minInterval}ms`);
    console.log(`- Max Interval: ${config.maxInterval}ms`);

    // Calculate timeouts
    const followerTimeout = heartbeatManager.getFollowerTimeout();
    console.log(`\nCalculated Timeouts:`);
    console.log(`- Follower Timeout: ${followerTimeout}ms`);
    console.log(`- Election Trigger: ~${followerTimeout + 500}ms`);

    // Generate configuration file
    await generateConfigFile(config, followerTimeout);

    if (apply) {
      await applyConfiguration();
    }

  } catch (error) {
    console.error('❌ Error:', error);
    process.exit(1);
  }
}
