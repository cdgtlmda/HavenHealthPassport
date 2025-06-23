# Haven Health Passport Web Portal - Developer Documentation

## Table of Contents
1. [Getting Started](#getting-started)
2. [Architecture Overview](#architecture-overview)
3. [Project Structure](#project-structure)
4. [Key Components](#key-components)
5. [State Management](#state-management)
6. [API Integration](#api-integration)
7. [Authentication](#authentication)
8. [Offline Support](#offline-support)
9. [Testing](#testing)
10. [Deployment](#deployment)

## Getting Started

### Prerequisites
- Node.js 18.x or higher
- npm or yarn
- Git

### Installation
```bash
# Clone the repository
git clone https://github.com/haven-health-passport/web.git

# Navigate to web directory
cd HavenHealthPassport/web

# Install dependencies
npm install

# Set up environment variables
cp .env.example .env.local
# Edit .env.local with your configuration

# Start development server
npm start
```

### Available Scripts
- `npm start` - Start development server
- `npm build` - Build for production
- `npm test` - Run tests
- `npm run lint` - Run ESLint
- `npm run format` - Format code with Prettier

## Architecture Overview

The web portal follows a modern React architecture with TypeScript for type safety.

### Technology Stack
- **Frontend Framework**: React 18 with TypeScript
- **UI Components**: Material-UI (MUI) v5
- **Routing**: React Router v6
- **State Management**: React Context API
- **HTTP Client**: Axios
- **Form Handling**: React Hook Form
- **PWA**: Workbox
- **Offline Storage**: Dexie.js (IndexedDB wrapper)
- **Charts**: Recharts
- **Date Handling**: date-fns

### Design Patterns
- **Component-Based Architecture**: Reusable UI components
- **Container/Presentational Pattern**: Separation of logic and UI
- **Custom Hooks**: Reusable business logic
- **Service Layer**: API abstraction
- **Error Boundaries**: Graceful error handling

## Project Structure

```
web/
├── public/
│   ├── index.html
│   ├── manifest.json
│   └── icons/
├── src/
│   ├── components/       # Reusable UI components
│   │   ├── common/      # Generic components
│   │   ├── forms/       # Form components
│   │   └── offline/     # Offline-specific components
│   ├── context/         # React Context providers
│   ├── features/        # Feature-specific modules
│   ├── guards/          # Route guards
│   ├── hooks/           # Custom React hooks
│   ├── layouts/         # Page layouts
│   ├── pages/           # Page components
│   ├── services/        # API and business logic
│   ├── styles/          # Global styles
│   ├── types/           # TypeScript type definitions
│   ├── utils/           # Utility functions
│   ├── App.tsx          # Root component
│   └── index.tsx        # Entry point
├── .env.example         # Environment variables template
├── package.json         # Dependencies and scripts
└── tsconfig.json        # TypeScript configuration
```

## Key Components

### Authentication Components
- `LoginPage` - Handles user login with MFA support
- `MFASetup` - TOTP setup with QR code generation
- `AuthGuard` - Protects routes requiring authentication

### Dashboard Components
- `DashboardPage` - Main dashboard with statistics
- `StatWidget` - Reusable statistics widget
- `ActivityFeed` - Real-time activity updates

### Patient Management
- `PatientList` - Searchable, sortable patient table
- `PatientDetail` - Comprehensive patient view
- `PatientForm` - Add/edit patient information

### Bulk Operations
- `BulkImport` - CSV import with validation
- `BulkExport` - Multi-format export
- `BulkUpdate` - Mass update with preview

### Organization Features
- `TeamHierarchy` - Visual team structure
- `DepartmentStructure` - Department management
- `CostCenters` - Financial tracking
- `ResourceAllocation` - Resource planning
- `CrossOrganizationSharing` - Data sharing agreements
- `ApprovalWorkflows` - Workflow designer and management

### Offline Components
- `OfflineSyncManager` - Manages offline data sync
- `ConflictResolutionUI` - Handles sync conflicts
- `ServiceWorkerRegistration` - PWA setup

## State Management

The application uses React Context API for global state management:

### Contexts
- `AuthContext` - User authentication state
- `OrganizationContext` - Current organization data
- `ThemeContext` - Theme preferences
- `OfflineContext` - Offline status and sync state

### Usage Example
```typescript
import { useAuth } from '@context/AuthContext';

function MyComponent() {
  const { user, isAuthenticated } = useAuth();
  
  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }
  
  return <div>Welcome, {user.name}!</div>;
}
```

## API Integration

### API Client Setup
```typescript
// services/api/apiClient.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_URL,
  timeout: 10000,
});

// Request interceptor for auth
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default apiClient;
```

### Service Layer Example
```typescript
// services/api/patientService.ts
export const patientService = {
  async getPatients(params?: any) {
    const response = await apiClient.get('/patients', { params });
    return response.data;
  },
  
  async createPatient(data: PatientData) {
    const response = await apiClient.post('/patients', data);
    return response.data;
  },
};
```

## Authentication

### JWT Token Management
- Access tokens stored in memory
- Refresh tokens in secure httpOnly cookies
- Automatic token refresh on 401 responses

### Multi-Factor Authentication
- TOTP (Time-based One-Time Password) support
- QR code generation for authenticator apps
- Backup codes for account recovery

## Offline Support

### Progressive Web App Features
- Service worker for offline caching
- Background sync for data synchronization
- Push notifications support

### Offline Data Management
```typescript
// Using Dexie.js for IndexedDB
import Dexie from 'dexie';

class OfflineDatabase extends Dexie {
  patients: Dexie.Table<Patient, string>;
  pendingSync: Dexie.Table<SyncItem, string>;
  
  constructor() {
    super('HavenHealthDB');
    this.version(1).stores({
      patients: 'id, firstName, lastName, updatedAt',
      pendingSync: 'id, type, timestamp',
    });
  }
}
```

### Conflict Resolution
- Automatic conflict detection
- User-friendly conflict resolution UI
- Audit trail for all resolutions

## Testing

### Unit Testing
```typescript
// Example test with React Testing Library
import { render, screen } from '@testing-library/react';
import { PatientList } from '@pages/patients';

test('renders patient list', async () => {
  render(<PatientList />);
  
  const heading = screen.getByText(/Patients/i);
  expect(heading).toBeInTheDocument();
});
```

### Integration Testing
- API mocking with MSW (Mock Service Worker)
- Component integration tests
- User flow testing

### E2E Testing
- Cypress for end-to-end testing
- Critical user journey coverage

## Deployment

### Build Configuration
```bash
# Production build
npm run build

# Analyze bundle size
npm run analyze
```

### Environment Variables
```env
REACT_APP_API_URL=https://api.havenhealthpassport.org
REACT_APP_WS_URL=wss://ws.havenhealthpassport.org
REACT_APP_ENVIRONMENT=production
```

### Docker Deployment
```dockerfile
FROM node:18-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### CI/CD Pipeline
- GitHub Actions for automated testing
- Docker image building
- Automated deployment to AWS/Azure

## Best Practices

### Code Style
- ESLint configuration for code quality
- Prettier for consistent formatting
- Husky for pre-commit hooks

### Performance
- Code splitting with React.lazy()
- Virtual scrolling for large lists
- Image optimization
- Bundle size monitoring

### Security
- Content Security Policy headers
- XSS protection
- HTTPS enforcement
- Secure cookie handling

### Accessibility
- ARIA labels and roles
- Keyboard navigation
- Screen reader support
- Color contrast compliance

## Troubleshooting

### Common Issues

1. **Build Failures**
   - Clear node_modules and reinstall
   - Check Node.js version compatibility

2. **API Connection Issues**
   - Verify environment variables
   - Check CORS configuration

3. **Offline Sync Problems**
   - Clear IndexedDB data
   - Check service worker registration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit changes with conventional commits
4. Submit a pull request

## License

This project is licensed under the Apache License, Version 2.0.
