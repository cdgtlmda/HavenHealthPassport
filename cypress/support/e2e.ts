/**
 * Cypress E2E Support File
 * CRITICAL: Configure E2E test helpers for healthcare workflows
 */

// Import commands
import './commands';

// Healthcare-specific test setup
beforeEach(() => {
  // Clear any cached patient data
  cy.window().then((win) => {
    win.localStorage.clear();
    win.sessionStorage.clear();
  });
  
  // Reset IndexedDB
  cy.window().then((win) => {
    if (win.indexedDB) {
      win.indexedDB.deleteDatabase('HavenHealthPassport');
    }
  });
});

// Global error handling
Cypress.on('uncaught:exception', (err, runnable) => {
  // Prevent Cypress from failing tests on known React errors
  if (err.message.includes('ResizeObserver loop limit exceeded')) {
    return false;
  }
  
  // Log healthcare-critical errors
  if (err.message.includes('patient') || err.message.includes('medical')) {
    console.error('CRITICAL HEALTHCARE ERROR:', err);
  }
  
  return true;
});