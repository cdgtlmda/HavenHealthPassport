/**
 * Cypress Custom Commands
 * CRITICAL: Healthcare-specific test commands for refugee health passport
 */

// Login command for healthcare workers
Cypress.Commands.add('login', (email: string, password: string) => {
  cy.visit('/login');
  cy.get('[data-testid="email-input"]').type(email);
  cy.get('[data-testid="password-input"]').type(password);
  cy.get('[data-testid="login-button"]').click();
  cy.url().should('not.include', '/login');
});

// Register a test patient
Cypress.Commands.add('registerPatient', (patientData: any) => {
  cy.visit('/patients/register');
  cy.get('[data-testid="first-name"]').type(patientData.firstName);
  cy.get('[data-testid="last-name"]').type(patientData.lastName);
  cy.get('[data-testid="date-of-birth"]').type(patientData.dateOfBirth);
  if (patientData.unhcrNumber) {
    cy.get('[data-testid="unhcr-number"]').type(patientData.unhcrNumber);
  }
  cy.get('[data-testid="register-button"]').click();
});

// Simulate offline mode
Cypress.Commands.add('goOffline', () => {
  cy.window().then((win) => {
    cy.stub(win.navigator, 'onLine').value(false);
    win.dispatchEvent(new Event('offline'));
  });
});

// Simulate online mode
Cypress.Commands.add('goOnline', () => {
  cy.window().then((win) => {
    cy.stub(win.navigator, 'onLine').value(true);
    win.dispatchEvent(new Event('online'));
  });
});

// Verify HIPAA compliance headers
Cypress.Commands.add('verifyHIPAAHeaders', () => {
  cy.request('/').then((response) => {
    expect(response.headers).to.have.property('strict-transport-security');
    expect(response.headers).to.have.property('x-content-type-options', 'nosniff');
    expect(response.headers).to.have.property('x-frame-options');
  });
});

// TypeScript declarations
declare global {
  namespace Cypress {
    interface Chainable {
      login(email: string, password: string): Chainable<void>;
      registerPatient(patientData: any): Chainable<void>;
      goOffline(): Chainable<void>;
      goOnline(): Chainable<void>;
      verifyHIPAAHeaders(): Chainable<void>;
    }
  }
}

export {};