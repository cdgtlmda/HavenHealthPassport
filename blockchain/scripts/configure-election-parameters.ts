#!/usr/bin/env node

/**
 * Apply Election Parameters to Blockchain Network
 * Haven Health Passport - Consensus Configuration
 */

import { electionParametersManager } from '../src/consensus/election-parameters-manager';
import * as path from 'path';
import * as fs from 'fs';
import * as yaml from 'js-yaml';
import { execSync } from 'child_process';

async function main() {
  console.log('Haven Health Passport - Election Parameters Configuration');
  console.log('======================================================\n');

  try {
    // Get and validate configuration
    const config = electionParametersManager.getConfig();
    const validation = electionParametersManager.validateParameters();

    if (!validation.valid) {
      console.error('❌ Configuration validation failed:');
      validation.errors.forEach(err => console.error(`   - ${err}`));
      process.exit(1);
    }

    console.log('✅ Configuration validated successfully');

    // Convert to YAML for Hyperledger Fabric
    const yamlConfig = yaml.dump(config, {
      indent: 2,
      lineWidth: 120,
      noRefs: true
    });

    // Save configuration
    const outputDir = path.join(__dirname, '../config/consensus');
    const outputPath = path.join(outputDir, 'election-parameters.yaml');

    fs.writeFileSync(outputPath, yamlConfig);
    console.log(`📄 Configuration saved to: ${outputPath}`);

    // Display configuration summary
    displayConfigSummary(config);

    // Apply to network if requested
    if (process.argv.includes('--apply')) {
      await applyToNetwork(config);
    }

  } catch (error) {
    console.error('❌ Error configuring election parameters:', error);
    process.exit(1);
  }
}
