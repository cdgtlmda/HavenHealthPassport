#!/usr/bin/env node

/**
 * Test sharding script for distributed test execution
 * Splits tests across multiple machines for CI/CD pipelines
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// Get shard configuration from environment
const SHARD_INDEX = parseInt(process.env.SHARD_INDEX || '1');
const TOTAL_SHARDS = parseInt(process.env.TOTAL_SHARDS || '1');

/**
 * Get all test files
 */
function getTestFiles() {
  try {
    const output = execSync('npm run test:all -- --listTests', {
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'ignore']
    });
    
    return output
      .split('\n')
      .filter(line => line.includes('.test.') || line.includes('.spec.'))
      .filter(Boolean);
  } catch (error) {
    console.error('Error getting test files:', error.message);
    return [];
  }
}

/**
 * Distribute tests across shards
 */
function getShardedTests(allTests, shardIndex, totalShards) {
  const testsPerShard = Math.ceil(allTests.length / totalShards);
  const startIndex = (shardIndex - 1) * testsPerShard;
  const endIndex = Math.min(startIndex + testsPerShard, allTests.length);
  
  return allTests.slice(startIndex, endIndex);
}

/**
 * Run sharded tests
 */
function runShardedTests() {
  console.log(`🧪 Running test shard ${SHARD_INDEX} of ${TOTAL_SHARDS}`);
  
  if (TOTAL_SHARDS === 1) {
    console.log('ℹ️  No sharding configured, running all tests');
    execSync('npm run test:ci', { stdio: 'inherit' });
    return;
  }
  
  // Get all test files
  const allTests = getTestFiles();
  console.log(`📁 Found ${allTests.length} test files`);
  
  // Get tests for this shard
  const shardTests = getShardedTests(allTests, SHARD_INDEX, TOTAL_SHARDS);
  console.log(`📦 Running ${shardTests.length} tests in shard ${SHARD_INDEX}`);
  
  if (shardTests.length === 0) {
    console.log('⚠️  No tests to run in this shard');
    process.exit(0);
  }
  
  // Create temporary file with test paths
  const testListFile = path.join(process.cwd(), `.shard-${SHARD_INDEX}-tests.json`);
  fs.writeFileSync(testListFile, JSON.stringify(shardTests, null, 2));
  
  try {
    // Run tests with Jest shard option
    const jestCommand = `JEST_SHARD="${SHARD_INDEX}/${TOTAL_SHARDS}" npm run test:all -- ${shardTests.map(t => `"${t}"`).join(' ')}`;
    
    console.log(`🚀 Executing: ${jestCommand}`);
    execSync(jestCommand, { 
      stdio: 'inherit',
      env: {
        ...process.env,
        JEST_SHARD: `${SHARD_INDEX}/${TOTAL_SHARDS}`,
        CI: 'true'
      }
    });
    
    console.log(`✅ Shard ${SHARD_INDEX} completed successfully`);
  } catch (error) {
    console.error(`❌ Shard ${SHARD_INDEX} failed`);
    process.exit(1);
  } finally {
    // Clean up temporary file
    if (fs.existsSync(testListFile)) {
      fs.unlinkSync(testListFile);
    }
  }
}

/**
 * Generate shard matrix for CI
 */
function generateShardMatrix() {
  const matrix = [];
  for (let i = 1; i <= TOTAL_SHARDS; i++) {
    matrix.push({
      shard: i,
      total: TOTAL_SHARDS,
      name: `shard-${i}-of-${TOTAL_SHARDS}`
    });
  }
  
  console.log(JSON.stringify({ include: matrix }));
}

// Handle command line arguments
const command = process.argv[2];

if (command === 'matrix') {
  generateShardMatrix();
} else {
  runShardedTests();
}

module.exports = { getTestFiles, getShardedTests, runShardedTests };
