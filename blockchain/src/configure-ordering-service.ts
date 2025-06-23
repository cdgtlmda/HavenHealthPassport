#!/usr/bin/env node

import { OrderingServiceManager } from './orderingServiceManager';
import { Command } from 'commander';
import * as dotenv from 'dotenv';

// Load environment variables
dotenv.config();

const program = new Command();

program
  .name('configure-ordering-service')
  .description('Configure ordering service for AWS Managed Blockchain')
  .version('1.0.0');

program
  .command('configure')
  .description('Configure ordering service for blockchain network')
  .requiredOption('-n, --network-id <networkId>', 'AWS Managed Blockchain network ID')
  .option('-r, --region <region>', 'AWS region', 'us-east-1')
  .action(async (options) => {
    try {
      console.log('Initializing Ordering Service Manager...');
      const manager = new OrderingServiceManager(options.region);

      console.log(`Configuring ordering service for network: ${options.networkId}`);
      await manager.configureOrderingService(options.networkId);

      console.log('✅ Ordering service configuration completed successfully');
    } catch (error) {
      console.error('❌ Failed to configure ordering service:', error);
      process.exit(1);
    }
  });

program
  .command('validate')
  .description('Validate ordering service configuration')
  .option('-r, --region <region>', 'AWS region', 'us-east-1')
  .action(async (options) => {
    try {
      console.log('Validating configuration...');
      const manager = new OrderingServiceManager(options.region);
      const config = await manager.loadConfig();

      console.log('✅ Configuration is valid');
      console.log(`Service type: ${config.type}`);
      console.log(`Cluster size: ${config.raftConfig.cluster.nodeCount} nodes`);
    } catch (error) {
      console.error('❌ Configuration validation failed:', error);
      process.exit(1);
    }
  });

program.parse();
