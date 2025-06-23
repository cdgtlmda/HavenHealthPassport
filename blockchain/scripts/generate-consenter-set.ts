#!/usr/bin/env node

/**
 * CLI Script to Generate Consenter Set Configuration
 * Haven Health Passport - Blockchain Infrastructure
 */

import { consenterSetGenerator } from '../src/consensus/consenter-set-generator';
import * as path from 'path';
import * as fs from 'fs';
import * as yaml from 'js-yaml';

async function main() {
  console.log('Haven Health Passport - Consenter Set Configuration Generator');
  console.log('============================================================\n');

  try {
    // Get the configuration
    const config = consenterSetGenerator.getConfig();

    // Convert to YAML
    const yamlStr = yaml.dump(config, {
      indent: 2,
      lineWidth: 120,
      noRefs: true
    });

    // Ensure output directory exists
    const outputDir = path.join(__dirname, '../config/consensus');
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    // Write the configuration file
    const outputPath = path.join(outputDir, 'consenter-set.yaml');
    fs.writeFileSync(outputPath, yamlStr);

    console.log(`✅ Consenter set configuration generated successfully!`);
    console.log(`📄 Configuration saved to: ${outputPath}`);
    console.log(`\nConfiguration Summary:`);
    console.log(`- Total Consenters: ${config.consenters.length}`);
    console.log(`- Quorum Size: ${config.consensusPolicies.quorum}`);
    console.log(`- TLS Enabled: ${config.globalConfig.tls.enabled}`);
    console.log(`- Backup Enabled: ${config.disasterRecovery.backup.enabled}`);

    // Validate the configuration
    validateConsenterSet(config);

  } catch (error) {
    console.error('❌ Error generating consenter set configuration:', error);
    process.exit(1);
  }
}
