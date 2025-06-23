/* Demo App for Haven Health Passport */

// Mock context providers needed by your components
const AuthContext = React.createContext({
  user: { id: 'demo-user', email: 'demo@havenhealth.org', token: 'demo-token' },
  logout: () => console.log('Logout clicked')
});

const useAuth = () => React.useContext(AuthContext);

// Mock hooks
const useOffline = () => ({ isOnline: true });
const useAutoSave = () => ({
  saveDraft: (data) => console.log('Saving draft', data),
  loadDraft: () => console.log('Loading draft'),
  deleteDraft: () => console.log('Deleting draft'),
  hasDraft: true
});

// Mock services
const notificationService = {
  success: (msg) => alert(`Success: ${msg}`),
  error: (msg) => alert(`Error: ${msg}`),
  info: (msg) => alert(`Info: ${msg}`),
  warn: (msg) => alert(`Warning: ${msg}`)
};

const auditLogger = {
  log: (data) => console.log('Audit log:', data)
};

const securityService = {
  logSecurityEvent: (type, data) => console.log('Security event:', type, data)
};

// Mock utilities
const generatePatientId = () => `P-${Math.floor(Math.random() * 100000)}`;
const validateUNHCRNumber = (num) => /^UNHCR-\d{4}-\d{5}$/.test(num);

// Create component wrappers
const ComponentWrapper = ({ title, description, children }) => {
  return (
    <div className="component-wrapper">
      <div className="component-header">
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
      <div className="component-content">
        {children}
      </div>
    </div>
  );
};

// Create mock implementations of your components for the demo
// (These will be replaced by the actual components if available)

// Mock PatientRegistration
const MockPatientRegistration = () => {
  const [formData, setFormData] = React.useState({
    firstName: '',
    lastName: '',
    dateOfBirth: '',
    gender: '',
    unhcrNumber: '',
    campLocation: '',
    tentNumber: '',
    primaryLanguage: 'en',
  });

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    alert('Patient registration submitted!');
  };

  return (
    <div className="patient-registration">
      <div className="offline-notice">
        <p>You are currently offline. Data will be saved locally and synced when connection is restored.</p>
      </div>
      
      <form onSubmit={handleSubmit}>
        <div className="form-section">
          <h2>Basic Information</h2>
          
          <div className="form-group">
            <label htmlFor="firstName">First Name <span>*</span></label>
            <input 
              type="text" 
              id="firstName" 
              name="firstName" 
              value={formData.firstName}
              onChange={handleChange}
              required
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="lastName">Last Name <span>*</span></label>
            <input 
              type="text" 
              id="lastName" 
              name="lastName" 
              value={formData.lastName}
              onChange={handleChange}
              required
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="dateOfBirth">Date of Birth <span>*</span></label>
            <input 
              type="date" 
              id="dateOfBirth" 
              name="dateOfBirth" 
              value={formData.dateOfBirth}
              onChange={handleChange}
              required
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="gender">Gender</label>
            <select 
              id="gender" 
              name="gender" 
              value={formData.gender}
              onChange={handleChange}
            >
              <option value="">Select...</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other</option>
            </select>
          </div>
          
          <div className="form-group">
            <label htmlFor="unhcrNumber">UNHCR Number</label>
            <input 
              type="text" 
              id="unhcrNumber" 
              name="unhcrNumber" 
              value={formData.unhcrNumber}
              onChange={handleChange}
              placeholder="UNHCR-YYYY-XXXXX"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="campLocation">Camp Location</label>
            <input 
              type="text" 
              id="campLocation" 
              name="campLocation" 
              value={formData.campLocation}
              onChange={handleChange}
              placeholder="e.g., Kakuma Refugee Camp"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="tentNumber">Tent/Shelter Number</label>
            <input 
              type="text" 
              id="tentNumber" 
              name="tentNumber" 
              value={formData.tentNumber}
              onChange={handleChange}
              placeholder="e.g., Block A, Tent 123"
            />
          </div>
        </div>
        
        <div className="form-actions">
          <button type="submit" className="btn-primary">Register Patient</button>
          <button type="button" className="btn-secondary">Cancel</button>
        </div>
      </form>
    </div>
  );
};

// Mock TOTPSetup
const MockTOTPSetup = () => {
  const [code, setCode] = React.useState('');
  
  return (
    <div className="totp-setup">
      <div className="qr-container">
        <div className="qr-code">
          <img src="https://via.placeholder.com/200x200?text=QR+Code" alt="QR Code" />
        </div>
      </div>
      
      <div className="secret-key">
        <p>Manual entry code:</p>
        <div className="secret-key-value">ABCD EFGH IJKL MNOP</div>
      </div>
      
      <div className="verification">
        <label htmlFor="verification-code">Enter the 6-digit code from your app:</label>
        <input 
          type="text" 
          id="verification-code" 
          value={code} 
          onChange={(e) => setCode(e.target.value)}
          maxLength={6}
          placeholder="000000"
        />
      </div>
      
      <button className="verify-button" onClick={() => alert('TOTP verified!')}>
        Verify
      </button>
    </div>
  );
};

// Mock BackupCodes
const MockBackupCodes = () => {
  const backupCodes = [
    'ABCD-EFGH-IJKL',
    'MNOP-QRST-UVWX',
    'YZAB-CDEF-GHIJ',
    'KLMN-OPQR-STUV',
    'WXYZ-1234-5678',
    'ABCD-EFGH-IJKL',
    'MNOP-QRST-UVWX',
    'YZAB-CDEF-GHIJ',
    'KLMN-OPQR-STUV',
    'WXYZ-1234-5678'
  ];
  
  return (
    <div className="backup-codes">
      <div className="backup-codes-warning">
        <p><strong>Important:</strong> Keep these backup codes in a safe place. Each code can only be used once.</p>
      </div>
      
      <div className="backup-codes-list">
        {backupCodes.map((code, index) => (
          <div key={index} className="backup-code">
            {code}
          </div>
        ))}
      </div>
      
      <div className="backup-codes-actions">
        <button className="print-button">Print Codes</button>
        <button className="download-button">Download</button>
      </div>
    </div>
  );
};

// Mock ConflictResolutionDialog
const MockConflictResolutionDialog = () => {
  return (
    <div className="conflict-resolution-dialog">
      <div className="conflict-message">
        <p>Changes were made to this patient record both online and offline. Please resolve the conflicts.</p>
      </div>
      
      <div className="conflict-item">
        <h3>Medication List</h3>
        
        <div className="conflict-versions">
          <div className="local-version">
            <h4>Local Version</h4>
            <ul>
              <li>Amoxicillin - 500mg</li>
              <li>Ibuprofen - 400mg</li>
              <li>Loratadine - 10mg</li>
            </ul>
          </div>
          
          <div className="server-version">
            <h4>Server Version</h4>
            <ul>
              <li>Amoxicillin - 500mg</li>
              <li>Ibuprofen - 400mg</li>
              <li>Cetirizine - 10mg</li>
            </ul>
          </div>
        </div>
        
        <div className="resolution-options">
          <div className="resolution-option">
            <input type="radio" id="local" name="resolution" />
            <label htmlFor="local">Use Local Version</label>
          </div>
          
          <div className="resolution-option">
            <input type="radio" id="server" name="resolution" />
            <label htmlFor="server">Use Server Version</label>
          </div>
          
          <div className="resolution-option">
            <input type="radio" id="merge" name="resolution" checked />
            <label htmlFor="merge">Merge (Keep All Medications)</label>
          </div>
        </div>
      </div>
      
      <div className="conflict-actions">
        <button className="cancel-button">Cancel</button>
        <button className="resolve-button">Apply Resolution</button>
      </div>
    </div>
  );
};

// Determine which components to use (either mocks or actual components)
const PatientRegistrationComponent = window.PatientRegistration || MockPatientRegistration;
const TOTPSetupComponent = window.TOTPSetup || MockTOTPSetup;
const BackupCodesComponent = window.BackupCodes || MockBackupCodes;
const ConflictResolutionDialogComponent = window.ConflictResolutionDialog || MockConflictResolutionDialog;

// Main Demo App
const DemoApp = () => {
  const [showConflict, setShowConflict] = React.useState(false);
  const [activeTab, setActiveTab] = React.useState('patient-registration');
  
  return (
    <AuthContext.Provider value={{ user: { id: 'demo-user', email: 'demo@havenhealth.org', token: 'demo-token' }, logout: () => {} }}>
      <div className="demo-container">
        <header className="demo-header">
          <div className="logo">
            <h1>Haven Health Passport</h1>
            <span className="badge">DEMO</span>
          </div>
          <div className="demo-controls">
            <button className="conflict-button" onClick={() => setShowConflict(true)}>
              Show Conflict Dialog
            </button>
          </div>
        </header>
        
        <div className="demo-body">
          <nav className="demo-nav">
            <ul>
              <li className={activeTab === 'patient-registration' ? 'active' : ''}>
                <button onClick={() => setActiveTab('patient-registration')}>
                  Patient Registration
                </button>
              </li>
              <li className={activeTab === 'totp-setup' ? 'active' : ''}>
                <button onClick={() => setActiveTab('totp-setup')}>
                  TOTP Setup
                </button>
              </li>
              <li className={activeTab === 'backup-codes' ? 'active' : ''}>
                <button onClick={() => setActiveTab('backup-codes')}>
                  Backup Codes
                </button>
              </li>
            </ul>
          </nav>
          
          <main className="demo-content">
            {activeTab === 'patient-registration' && (
              <ComponentWrapper
                title="Patient Registration Form"
                description="Register new patients with offline support for refugee camp environments"
              >
                <PatientRegistrationComponent />
              </ComponentWrapper>
            )}
            
            {activeTab === 'totp-setup' && (
              <ComponentWrapper
                title="Two-Factor Authentication Setup"
                description="Secure medical staff accounts with time-based one-time passwords"
              >
                <TOTPSetupComponent />
              </ComponentWrapper>
            )}
            
            {activeTab === 'backup-codes' && (
              <ComponentWrapper
                title="Backup Recovery Codes"
                description="Provide emergency access when primary authentication is unavailable"
              >
                <BackupCodesComponent />
              </ComponentWrapper>
            )}
          </main>
        </div>
        
        {showConflict && (
          <div className="modal-overlay">
            <div className="modal-container">
              <div className="modal-header">
                <h2>Resolve Sync Conflict</h2>
                <button className="close-button" onClick={() => setShowConflict(false)}>×</button>
              </div>
              <div className="modal-body">
                <ConflictResolutionDialogComponent />
              </div>
            </div>
          </div>
        )}
        
        <footer className="demo-footer">
          <p>Haven Health Passport Demo • All data is simulated</p>
        </footer>
      </div>
    </AuthContext.Provider>
  );
};

// Render the demo app
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<DemoApp />);
