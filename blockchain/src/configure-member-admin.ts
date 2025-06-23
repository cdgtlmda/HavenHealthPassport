#!/usr/bin/env node

import { MemberAdminManager } from './memberAdminManager';
import { Command } from 'commander';
import * as dotenv from 'dotenv';

// Load environment variables
dotenv.config();

const program = new Command();

program
  .name('configure-member-admin')
  .description('Configure admin user for AWS Managed Blockchain member')
  .version('1.0.0');

program
  .command('configure')
  .description('Configure admin user for blockchain member')
  .requiredOption('-n, --network-id <networkId>', 'AWS Managed Blockchain network ID')
  .option('-m, --member-id <memberId>', 'Existing member ID to update')
  .option('-r, --region <region>', 'AWS region', 'us-east-1')
  .action(async (options) => {
    try {
      console.log('Initializing Member Admin Manager...');
      const manager = new MemberAdminManager(options.region);

      console.log(`Configuring admin for network: ${options.networkId}`);
      await manager.configureMemberAdmin(options.networkId, options.memberId);

      console.log('✅ Member admin configuration completed successfully');
    } catch (error) {
      console.error('❌ Failed to configure member admin:', error);
      process.exit(1);
    }
  });

program
  .command('validate')
  .description('Validate member admin configuration')
  .option('-r, --region <region>', 'AWS region', 'us-east-1')
  .action(async (options) => {
    try {
      console.log('Validating configuration...');
      const manager = new MemberAdminManager(options.region);
      const config = await manager.loadConfig();

      console.log('✅ Configuration is valid');
      console.log(`Admin username: ${config.username}`);
      console.log(`Organization: ${config.certificate.subject.organization}`);
    } catch (error) {
      console.error('❌ Configuration validation failed:', error);
      process.exit(1);
    }
  });

program.parse();
