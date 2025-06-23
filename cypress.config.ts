/**
 * Cypress E2E Testing Configuration
 * CRITICAL: Configure end-to-end testing for healthcare workflows
 * Must test critical patient journeys in refugee camp scenarios
 */

import { defineConfig } from 'cypress';

export default defineConfig({
  e2e: {
    baseUrl: 'http://localhost:3000',
    supportFile: 'cypress/support/e2e.ts',
    specPattern: 'cypress/e2e/**/*.cy.{js,jsx,ts,tsx}',

    // Healthcare-specific timeouts for slow connections
    defaultCommandTimeout: 10000,
    requestTimeout: 15000,
    responseTimeout: 15000,

    // Viewport for testing on typical refugee camp devices
    viewportWidth: 1280,
    viewportHeight: 720,

    // Video recording for audit trail
    video: true,
    videosFolder: 'cypress/videos',
    videoCompression: 32,

    // Screenshots for test evidence
    screenshotsFolder: 'cypress/screenshots',

    // Retry configuration for flaky connections
    retries: {
      runMode: 2,
      openMode: 0,
    },

    // Environment variables for test data
    env: {
      API_URL: 'http://localhost:3001',
      TEST_USER_EMAIL: 'test@havenhealthpassport.org',
      TEST_USER_PASSWORD: process.env.TEST_USER_PASSWORD || 'ChangeThisPassword123!',
    },

    setupNodeEvents(on, config) {
      // Task for database seeding
      on('task', {
        seedDatabase() {
          // Database seeding logic
          return null;
        },
        clearDatabase() {
          // Database cleanup logic
          return null;
        },
      });

      // Code coverage
      require('@cypress/code-coverage/task')(on, config);

      return config;
    },
  },

  component: {
    devServer: {
      framework: 'react',
      bundler: 'webpack',
    },
    specPattern: 'src/**/*.cy.{js,jsx,ts,tsx}',
  },
});
