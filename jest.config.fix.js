/**
 * Simplified Jest configuration for fixing test issues
 * CRITICAL: Use this to run tests without database dependencies
 */

module.exports = {
  displayName: 'Haven Health Passport - Fix Mode',
  testEnvironment: 'jsdom',
  roots: ['<rootDir>/web/src'],
  testMatch: [
    '**/__tests__/**/*.{test,spec}.{ts,tsx,js,jsx}',
    '**/*.{test,spec}.{ts,tsx,js,jsx}'
  ],
  
  setupFilesAfterEnv: ['<rootDir>/web/src/setupTests.ts'],
  
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
  
  transform: {
    '^.+\\.(ts|tsx|js|jsx)$': 'babel-jest',
  },
  
  transformIgnorePatterns: [
    'node_modules/(?!(@mui|@emotion|@aws-amplify|aws-amplify)/)'
  ],
  
  testTimeout: 30000,
  
  clearMocks: true,
  restoreMocks: true,
  resetMocks: true,
  
  verbose: true
};