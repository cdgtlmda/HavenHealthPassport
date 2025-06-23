/**
 * Lighthouse CI Configuration for Healthcare Application
 * Performance standards for medical data systems
 */

module.exports = {
  ci: {
    collect: {
      // Test against production build
      staticDistDir: './web/build',
      
      // Also test critical dynamic routes
      url: [
        'http://localhost:3000/',
        'http://localhost:3000/login',
        'http://localhost:3000/register',
        'http://localhost:3000/dashboard',
        'http://localhost:3000/patients',
        'http://localhost:3000/emergency-access'
      ],
      
      numberOfRuns: 3,
      
      settings: {
        preset: 'desktop',
        throttling: {
          cpuSlowdownMultiplier: 1,
          // Simulate real medical facility network conditions
          requestLatencyMs: 40,
          downloadThroughputKbps: 10240, // 10 Mbps
          uploadThroughputKbps: 5120 // 5 Mbps
        }
      }
    },
    
    assert: {
      assertions: {
        // Performance assertions for healthcare systems
        'categories:performance': ['error', { minScore: 0.9 }], // 90% minimum
        'categories:accessibility': ['error', { minScore: 0.95 }], // 95% for medical accessibility
        'categories:best-practices': ['error', { minScore: 0.95 }],
        'categories:seo': ['warn', { minScore: 0.8 }],
        
        // Critical metrics for medical applications
        'first-contentful-paint': ['error', { maxNumericValue: 1500 }], // 1.5s
        'interactive': ['error', { maxNumericValue: 3000 }], // 3s
        'speed-index': ['error', { maxNumericValue: 2000 }], // 2s
        'total-blocking-time': ['error', { maxNumericValue: 300 }], // 300ms
        'largest-contentful-paint': ['error', { maxNumericValue: 2500 }], // 2.5s
        'cumulative-layout-shift': ['error', { maxNumericValue: 0.1 }],
        
        // Security headers for healthcare
        'csp-xss': ['error', { minScore: 1 }],
        'no-vulnerable-libraries': ['error', { minScore: 1 }],
        'errors-in-console': ['error', { minScore: 1 }],
        
        // Accessibility requirements for medical systems
        'color-contrast': ['error', { minScore: 1 }],
        'aria-*': ['error', { minScore: 1 }],
        'image-alt': ['error', { minScore: 1 }],
        'label': ['error', { minScore: 1 }],
        
        // Network and caching
        'uses-text-compression': ['error', { minScore: 0.95 }],
        'uses-responsive-images': ['error', { minScore: 0.95 }],
        'efficient-animated-content': ['error', { minScore: 0.95 }],
        'duplicated-javascript': ['error', { minScore: 0.95 }],
        'legacy-javascript': ['error', { minScore: 1 }],
        
        // Medical app specific
        'offline-start-url': ['error', { minScore: 1 }], // Offline capability required
        'works-offline': ['warn', { minScore: 0.9 }],
        'installable-manifest': ['warn', { minScore: 0.9 }], // PWA for field use
      },
      
      // Budget for healthcare applications
      budgets: [
        {
          path: '/*',
          resourceSizes: [
            { resourceType: 'document', budget: 50 }, // 50KB HTML
            { resourceType: 'script', budget: 300 }, // 300KB JS
            { resourceType: 'stylesheet', budget: 100 }, // 100KB CSS
            { resourceType: 'image', budget: 500 }, // 500KB images
            { resourceType: 'font', budget: 100 }, // 100KB fonts
            { resourceType: 'total', budget: 1500 } // 1.5MB total
          ],
          resourceCounts: [
            { resourceType: 'third-party', budget: 10 }, // Limit third-party resources
          ]
        }
      ]
    },
    
    upload: {
      target: 'temporary-public-storage',
      
      // GitHub status check
      githubStatusContextSuffix: '/healthcare-performance',
      
      // Store reports for analysis
      outputDir: '.lighthouse-ci',
      reportFilenamePattern: '%%HOSTNAME%%-%%PATHNAME%%-%%DATETIME%%.%%EXTENSION%%'
    },
    
    server: {
      // Configuration for Lighthouse CI Server (if deployed)
      // storage: {
      //   storageMethod: 'sql',
      //   sqlDatabasePath: './lighthouse-ci.db',
      // }
    }
  }
};
