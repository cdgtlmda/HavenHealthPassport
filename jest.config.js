/**
 * Jest configuration for Haven Health Passport
 * Root-level configuration for coordinating tests across all workspaces
 */

module.exports = {
  // Display name for the test suite
  displayName: 'Haven Health Passport',
  
  // Test environment
  testEnvironment: 'node',
  
  // Projects configuration for monorepo
  projects: [
    {
      displayName: 'root',
      testMatch: ['<rootDir>/__tests__/**/*.{test,spec}.{js,ts}'],
      testEnvironment: 'node'
    },
    {
      displayName: 'web',
      testMatch: ['<rootDir>/web/**/*.{test,spec}.{js,jsx,ts,tsx}'],
      testEnvironment: 'jsdom',
      setupFilesAfterEnv: [
        '<rootDir>/web/src/setupTests.ts',
        '<rootDir>/test-setup/jest-setup.js'
      ],
      moduleNameMapper: {
        '^@components/(.*)$': '<rootDir>/web/src/components/$1',
        '^@pages/(.*)$': '<rootDir>/web/src/pages/$1',
        '^@services/(.*)$': '<rootDir>/web/src/services/$1',
        '^@hooks/(.*)$': '<rootDir>/web/src/hooks/$1',
        '^@utils/(.*)$': '<rootDir>/web/src/utils/$1',
        '^@types/(.*)$': '<rootDir>/web/src/types/$1',
        '^@context/(.*)$': '<rootDir>/web/src/context/$1',
        '^@styles/(.*)$': '<rootDir>/web/src/styles/$1',
        '^@i18n/(.*)$': '<rootDir>/web/src/i18n/$1',
        '^@constants$': '<rootDir>/web/src/constants.ts',
        '^@guards/(.*)$': '<rootDir>/web/src/guards/$1',
        '^@layouts/(.*)$': '<rootDir>/web/src/layouts/$1',
        '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
        '\\.(jpg|jpeg|png|gif|eot|otf|webp|svg|ttf|woff|woff2|mp4|webm|wav|mp3|m4a|aac|oga)$': '<rootDir>/__mocks__/fileMock.js'
      },
      transformIgnorePatterns: [
        'node_modules/(?!(@mui|@emotion|@aws-amplify|aws-amplify)/)'
      ]
    },
    {
      displayName: 'mobile',
      preset: 'react-native',
      testMatch: ['<rootDir>/mobile/**/*.{test,spec}.{js,jsx,ts,tsx}'],
      setupFilesAfterEnv: [
        '@testing-library/jest-native/extend-expect',
        '<rootDir>/mobile/jest.setup.js',
        '<rootDir>/test-setup/jest-setup.js'
      ],
      moduleNameMapper: {
        '^@/(.*)$': '<rootDir>/mobile/src/$1',
        '^@components/(.*)$': '<rootDir>/mobile/src/components/$1',
        '^@screens/(.*)$': '<rootDir>/mobile/src/screens/$1',
        '^@navigation/(.*)$': '<rootDir>/mobile/src/navigation/$1',
        '^@services/(.*)$': '<rootDir>/mobile/src/services/$1',
        '^@utils/(.*)$': '<rootDir>/mobile/src/utils/$1',
        '^@hooks/(.*)$': '<rootDir>/mobile/src/hooks/$1',
        '^@context/(.*)$': '<rootDir>/mobile/src/context/$1',
        '^@i18n/(.*)$': '<rootDir>/mobile/src/i18n/$1',
        '^@offline/(.*)$': '<rootDir>/mobile/src/offline/$1',
        '^@assets/(.*)$': '<rootDir>/mobile/assets/$1',
        '^@types/(.*)$': '<rootDir>/mobile/src/types/$1',
        '\\.svg$': '<rootDir>/__mocks__/svgMock.js'
      },
      transform: {
        '^.+\\.(js|jsx|ts|tsx)$': ['babel-jest', { configFile: './mobile/babel.config.js' }]
      },
      transformIgnorePatterns: [
        'node_modules/(?!(react-native|@react-native|@react-navigation|@expo|expo-*|@unimodules|unimodules|sentry-expo|native-base|react-native-svg)/)'
      ],
      testEnvironment: 'node'
    },
    {
      displayName: 'shared',
      testMatch: ['<rootDir>/packages/shared/**/*.{test,spec}.{js,ts}'],
      testEnvironment: 'node'
    }
  ],
  
  // Coverage configuration
  collectCoverage: false,
  coverageDirectory: '<rootDir>/coverage',
  collectCoverageFrom: [
    'web/src/**/*.{js,jsx,ts,tsx}',
    'mobile/src/**/*.{js,jsx,ts,tsx}',
    'packages/*/src/**/*.{js,ts}',
    '!**/*.d.ts',
    '!**/node_modules/**',
    '!**/vendor/**',
    '!**/__tests__/**',
    '!**/*.config.{js,ts}',
    '!**/coverage/**',
    '!**/dist/**',
    '!**/build/**'
  ],
  
  // Coverage thresholds
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80
    }
  },
  
  // Test timeout
  testTimeout: process.env.CI ? 20000 : 10000,
  
  // Parallel execution configuration
  // Import parallel config dynamically if available
  ...((() => {
    try {
      const parallelConfig = require('./test-setup/parallel/parallel-config');
      return {
        maxWorkers: parallelConfig.workerCount,
        maxConcurrency: 5,
        workerIdleMemoryLimit: parallelConfig.jestConfig.workerIdleMemoryLimit,
      };
    } catch (e) {
      // Fallback to default if parallel config not available
      return {
        maxWorkers: process.env.CI ? 2 : '50%',
        maxConcurrency: 5,
      };
    }
  })()),
  
  // Retry configuration for flaky tests
  testRetries: process.env.CI ? 2 : 0,
  
  // Bail on first test failure in CI
  bail: process.env.CI ? 1 : 0,
  
  // Error on deprecated APIs
  errorOnDeprecated: true,
  
  // Detect open handles
  detectOpenHandles: process.env.DETECT_OPEN_HANDLES === 'true',
  forceExit: process.env.CI ? true : false,
  
  // Test sequencer for optimal execution order
  testSequencer: '<rootDir>/test-setup/testSequencer.js',
  
  // Shard configuration (for distributed testing)
  ...(process.env.JEST_SHARD && {
    shard: process.env.JEST_SHARD
  }),
  
  // Performance tracking
  logHeapUsage: process.env.CI ? true : false,
  
  // Verbose output
  verbose: true,
  
  // Clear mocks automatically
  clearMocks: true,
  restoreMocks: true,
  resetMocks: true,
  
  // Global setup/teardown
  globalSetup: process.env.PARALLEL_TESTS 
    ? '<rootDir>/test-setup/parallel/global-setup.js'
    : '<rootDir>/test-setup/globalSetup.js',
  globalTeardown: process.env.PARALLEL_TESTS
    ? '<rootDir>/test-setup/parallel/global-teardown.js'
    : '<rootDir>/test-setup/globalTeardown.js',
  
  // Setup files for parallel execution
  ...(process.env.PARALLEL_TESTS && {
    setupFilesAfterEnv: [
      ...((module.exports.setupFilesAfterEnv || [])),
      '<rootDir>/test-setup/parallel/worker-setup.js'
    ]
  }),
  
  // Reporters
  reporters: [
    'default',
    ['jest-junit', {
      outputDirectory: './test-results',
      outputName: 'junit.xml',
      classNameTemplate: '{classname}',
      titleTemplate: '{title}',
      ancestorSeparator: ' › ',
      usePathForSuiteName: true
    }]
  ],
  
  // Watch plugins
  watchPlugins: [
    'jest-watch-typeahead/filename',
    'jest-watch-typeahead/testname'
  ]
};
