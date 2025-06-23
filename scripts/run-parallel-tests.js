#!/usr/bin/env node

/**
 * Parallel test runner for Haven Health Passport
 * Distributes tests across multiple processes for faster execution
 */

const { spawn } = require('child_process');
const os = require('os');
const path = require('path');

// Configuration
const MAX_WORKERS = process.env.MAX_WORKERS || os.cpus().length;
const TEST_PROJECTS = ['web', 'mobile']; // packages/shared-ui doesn't have tests yet

/**
 * Run tests for a specific project
 */
function runProjectTests(project, workerIndex) {
  return new Promise((resolve, reject) => {
    console.log(`🚀 Starting tests for ${project} (Worker ${workerIndex})`);
    
    const env = {
      ...process.env,
      JEST_WORKER_ID: workerIndex,
      NODE_OPTIONS: '--max-old-space-size=4096'
    };
    
    const args = [
      'run',
      'test',
      '--',
      '--maxWorkers=2',
      '--runInBand',
      '--no-coverage'
    ];
    
    const testProcess = spawn('npm', args, {
      cwd: path.join(process.cwd(), project),
      env,
      stdio: 'inherit'
    });
    
    testProcess.on('close', (code) => {
      if (code === 0) {
        console.log(`✅ ${project} tests completed successfully`);
        resolve({ project, success: true });
      } else {
        console.error(`❌ ${project} tests failed with code ${code}`);
        resolve({ project, success: false, code });
      }
    });
    
    testProcess.on('error', (error) => {
      console.error(`❌ Error running ${project} tests:`, error);
      reject(error);
    });
  });
}

/**
 * Run all tests in parallel
 */
async function runParallelTests() {
  console.log(`🧪 Running tests in parallel with ${MAX_WORKERS} workers`);
  console.log(`📦 Testing projects: ${TEST_PROJECTS.join(', ')}`);
  
  const startTime = Date.now();
  
  try {
    // Run all project tests in parallel
    const results = await Promise.all(
      TEST_PROJECTS.map((project, index) => 
        runProjectTests(project, index + 1)
      )
    );
    
    // Calculate statistics
    const duration = (Date.now() - startTime) / 1000;
    const failed = results.filter(r => !r.success);
    
    console.log('\n📊 Test Results:');
    console.log(`⏱️  Total duration: ${duration.toFixed(2)}s`);
    console.log(`✅ Passed: ${results.length - failed.length}`);
    console.log(`❌ Failed: ${failed.length}`);
    
    if (failed.length > 0) {
      console.error('\n❌ Failed projects:', failed.map(f => f.project).join(', '));
      process.exit(1);
    } else {
      console.log('\n✅ All tests passed!');
      process.exit(0);
    }
  } catch (error) {
    console.error('❌ Error running parallel tests:', error);
    process.exit(1);
  }
}

// Run tests if this script is executed directly
if (require.main === module) {
  runParallelTests();
}

module.exports = { runParallelTests, runProjectTests };
