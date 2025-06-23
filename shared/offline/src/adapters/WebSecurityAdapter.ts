import { CryptoAdapter } from '../types';

/**
 * Web platform security adapter using the Web Crypto API
 * for browser-based encryption and secure key management
 */
export class WebSecurityAdapter implements CryptoAdapter {
  private static readonly KEY_PREFIX = 'haven_security_';
  private static readonly MASTER_KEY_NAME = 'haven_master_key';
  private static readonly SALT_LENGTH = 16;
  private static readonly IV_LENGTH = 12;
  private static readonly TAG_LENGTH = 16;
  
  private crypto: SubtleCrypto;
  private textEncoder: TextEncoder;
  private textDecoder: TextDecoder;
  private masterKey?: CryptoKey;
  private isInitialized = false;

  constructor() {
    if (!window.crypto || !window.crypto.subtle) {
      throw new Error('Web Crypto API is not available. Ensure you are using HTTPS.');
    }
    
    this.crypto = window.crypto.subtle;
    this.textEncoder = new TextEncoder();
    this.textDecoder = new TextDecoder();
  }

  /**
   * Initialize the security adapter
   */
  async initialize(): Promise<void> {
    if (this.isInitialized) return;

    try {
      // Try to retrieve existing master key
      const existingKey = await this.retrieveMasterKey();
      if (existingKey) {
        this.masterKey = existingKey;
      } else {
        // Generate and store new master key
        this.masterKey = await this.generateAndStoreMasterKey();
      }

      this.isInitialized = true;
    } catch (error) {
      console.error('WebSecurityAdapter: Initialization failed', error);
      throw new Error('Failed to initialize security adapter');
    }  }

  /**
   * Encrypt data using AES-GCM
   */
  async encrypt(data: string, key?: string): Promise<string> {
    if (!this.isInitialized) await this.initialize();

    try {
      const cryptoKey = key ? await this.deriveKeyFromString(key) : this.masterKey;
      if (!cryptoKey) {
        throw new Error('No encryption key available');
      }

      // Generate random IV
      const iv = window.crypto.getRandomValues(new Uint8Array(this.IV_LENGTH));
      
      // Encrypt the data
      const encodedData = this.textEncoder.encode(data);
      const encryptedData = await this.crypto.encrypt(
        {
          name: 'AES-GCM',
          iv: iv,
          tagLength: this.TAG_LENGTH * 8
        },
        cryptoKey,
        encodedData
      );

      // Combine IV and encrypted data
      const combined = new Uint8Array(iv.length + encryptedData.byteLength);
      combined.set(iv);
      combined.set(new Uint8Array(encryptedData), iv.length);

      // Convert to base64 for storage
      return btoa(String.fromCharCode(...combined));
    } catch (error) {
      console.error('WebSecurityAdapter: Encryption failed', error);
      throw new Error('Encryption failed');
    }
  }

  /**
   * Decrypt data using AES-GCM
   */
  async decrypt(data: string, key?: string): Promise<string> {
    if (!this.isInitialized) await this.initialize();

    try {
      const cryptoKey = key ? await this.deriveKeyFromString(key) : this.masterKey;
      if (!cryptoKey) {
        throw new Error('No decryption key available');
      }

      // Convert from base64
      const combined = Uint8Array.from(atob(data), c => c.charCodeAt(0));
      
      // Extract IV and encrypted data
      const iv = combined.slice(0, this.IV_LENGTH);
      const encryptedData = combined.slice(this.IV_LENGTH);

      // Decrypt the data
      const decryptedData = await this.crypto.decrypt(
        {
          name: 'AES-GCM',
          iv: iv,
          tagLength: this.TAG_LENGTH * 8
        },
        cryptoKey,
        encryptedData
      );

      return this.textDecoder.decode(decryptedData);
    } catch (error) {
      console.error('WebSecurityAdapter: Decryption failed', error);
      throw new Error('Decryption failed');
    }
  }

  /**
   * Generate SHA-256 hash
   */
  async hash(data: string): Promise<string> {
    try {
      const encoded = this.textEncoder.encode(data);
      const hashBuffer = await this.crypto.digest('SHA-256', encoded);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    } catch (error) {
      console.error('WebSecurityAdapter: Hashing failed', error);
      throw new Error('Hashing failed');
    }  }

  /**
   * Generate a secure random key
   */
  async generateSecureKey(length: number = 32): Promise<string> {
    try {
      const randomBytes = window.crypto.getRandomValues(new Uint8Array(length));
      return Array.from(randomBytes)
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');
    } catch (error) {
      console.error('WebSecurityAdapter: Key generation failed', error);
      throw new Error('Key generation failed');
    }
  }

  /**
   * Store encrypted data in IndexedDB
   */
  async storeSecureData(key: string, value: string): Promise<void> {
    try {
      const encryptedValue = await this.encrypt(value);
      const db = await this.openSecureDB();
      const transaction = db.transaction(['secure_store'], 'readwrite');
      const store = transaction.objectStore('secure_store');
      
      await new Promise<void>((resolve, reject) => {
        const request = store.put({
          key: this.KEY_PREFIX + key,
          value: encryptedValue,
          timestamp: Date.now()
        });
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      });

      db.close();
    } catch (error) {
      console.error('WebSecurityAdapter: Secure storage failed', error);
      throw new Error('Failed to store secure data');
    }
  }

  /**
   * Retrieve and decrypt data from IndexedDB
   */
  async getSecureData(key: string): Promise<string | null> {
    try {
      const db = await this.openSecureDB();
      const transaction = db.transaction(['secure_store'], 'readonly');
      const store = transaction.objectStore('secure_store');
      
      const result = await new Promise<any>((resolve, reject) => {
        const request = store.get(this.KEY_PREFIX + key);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });

      db.close();

      if (result && result.value) {
        return await this.decrypt(result.value);
      }
      return null;
    } catch (error) {
      console.error('WebSecurityAdapter: Secure retrieval failed', error);
      return null;
    }
  }

  /**
   * Delete secure data from IndexedDB
   */
  async deleteSecureData(key: string): Promise<void> {
    try {
      const db = await this.openSecureDB();
      const transaction = db.transaction(['secure_store'], 'readwrite');
      const store = transaction.objectStore('secure_store');
      
      await new Promise<void>((resolve, reject) => {
        const request = store.delete(this.KEY_PREFIX + key);
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      });

      db.close();
    } catch (error) {
      console.error('WebSecurityAdapter: Secure deletion failed', error);
      throw new Error('Failed to delete secure data');
    }
  }

  /**
   * Enable WebAuthn for enhanced security
   */
  async enableWebAuthn(): Promise<boolean> {
    try {
      if (!window.PublicKeyCredential) {
        console.warn('WebAuthn is not supported on this browser');
        return false;
      }

      // Check if platform authenticator is available
      const available = await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
      if (!available) {
        console.warn('No platform authenticator available');
        return false;
      }

      // Create credential options
      const createOptions: CredentialCreationOptions = {
        publicKey: {
          challenge: window.crypto.getRandomValues(new Uint8Array(32)),
          rp: {
            name: 'Haven Health Passport',
            id: window.location.hostname
          },
          user: {
            id: window.crypto.getRandomValues(new Uint8Array(16)),
            name: 'haven_user',
            displayName: 'Haven User'
          },
          pubKeyCredParams: [
            { alg: -7, type: 'public-key' },  // ES256
            { alg: -257, type: 'public-key' } // RS256
          ],
          authenticatorSelection: {
            authenticatorAttachment: 'platform',
            userVerification: 'required'
          },
          timeout: 60000,
          attestation: 'none'
        }
      };

      const credential = await navigator.credentials.create(createOptions);
      if (credential) {
        // Store credential ID for future authentication
        await this.storeSecureData('webauthn_credential_id', credential.id);
        return true;
      }

      return false;
    } catch (error) {
      console.error('WebSecurityAdapter: WebAuthn setup failed', error);
      return false;    }
  }

  /**
   * Authenticate using WebAuthn
   */
  async authenticateWithWebAuthn(): Promise<boolean> {
    try {
      const credentialId = await this.getSecureData('webauthn_credential_id');
      if (!credentialId) {
        return false;
      }

      const getOptions: CredentialRequestOptions = {
        publicKey: {
          challenge: window.crypto.getRandomValues(new Uint8Array(32)),
          allowCredentials: [{
            id: Uint8Array.from(atob(credentialId), c => c.charCodeAt(0)),
            type: 'public-key'
          }],
          userVerification: 'required',
          timeout: 60000
        }
      };

      const assertion = await navigator.credentials.get(getOptions);
      return !!assertion;
    } catch (error) {
      console.error('WebSecurityAdapter: WebAuthn authentication failed', error);
      return false;
    }
  }

  /**
   * Derive a key from password using PBKDF2
   */
  async deriveKeyFromPassword(password: string, salt?: string): Promise<string> {
    try {
      const saltBytes = salt 
        ? this.textEncoder.encode(salt)
        : window.crypto.getRandomValues(new Uint8Array(this.SALT_LENGTH));
      
      const passwordKey = await this.crypto.importKey(
        'raw',
        this.textEncoder.encode(password),
        'PBKDF2',
        false,
        ['deriveBits', 'deriveKey']
      );

      const derivedBits = await this.crypto.deriveBits(        {
          name: 'PBKDF2',
          salt: saltBytes,
          iterations: 100000,
          hash: 'SHA-256'
        },
        passwordKey,
        256
      );

      const derivedArray = Array.from(new Uint8Array(derivedBits));
      return derivedArray.map(b => b.toString(16).padStart(2, '0')).join('');
    } catch (error) {
      console.error('WebSecurityAdapter: Key derivation failed', error);
      throw new Error('Key derivation failed');
    }
  }

  /**
   * Check browser security features
   */
  async getBrowserSecurityStatus(): Promise<{
    isSecureContext: boolean;
    hasWebCrypto: boolean;
    hasWebAuthn: boolean;
    hasCredentialManagement: boolean;
    hasStorageAccess: boolean;
    securityLevel: 'high' | 'medium' | 'low';
  }> {
    try {
      const isSecureContext = window.isSecureContext;
      const hasWebCrypto = !!(window.crypto && window.crypto.subtle);
      const hasWebAuthn = !!window.PublicKeyCredential;
      const hasCredentialManagement = !!navigator.credentials;
      const hasStorageAccess = 'storage' in navigator && 'persist' in navigator.storage;

      // Check if storage is persistent
      let isPersistent = false;
      if (hasStorageAccess) {
        isPersistent = await navigator.storage.persist();
      }

      // Determine security level
      let securityLevel: 'high' | 'medium' | 'low' = 'low';
      if (isSecureContext && hasWebCrypto && hasWebAuthn && isPersistent) {
        securityLevel = 'high';
      } else if (isSecureContext && hasWebCrypto) {
        securityLevel = 'medium';
      }
      return {
        isSecureContext,
        hasWebCrypto,
        hasWebAuthn,
        hasCredentialManagement,
        hasStorageAccess,
        securityLevel
      };
    } catch (error) {
      console.error('WebSecurityAdapter: Security check failed', error);
      return {
        isSecureContext: false,
        hasWebCrypto: false,
        hasWebAuthn: false,
        hasCredentialManagement: false,
        hasStorageAccess: false,
        securityLevel: 'low'
      };
    }
  }

  /**
   * Request storage persistence
   */
  async requestPersistentStorage(): Promise<boolean> {
    try {
      if ('storage' in navigator && 'persist' in navigator.storage) {
        const isPersisted = await navigator.storage.persist();
        return isPersisted;
      }
      return false;
    } catch (error) {
      console.error('WebSecurityAdapter: Persistent storage request failed', error);
      return false;
    }
  }

  /**
   * Clear all secure data
   */
  async clearAllSecureData(): Promise<void> {
    try {
      const db = await this.openSecureDB();
      const transaction = db.transaction(['secure_store'], 'readwrite');
      const store = transaction.objectStore('secure_store');
      
      await new Promise<void>((resolve, reject) => {
        const request = store.clear();
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);      });

      db.close();
      
      // Clear master key
      this.masterKey = undefined;
      this.isInitialized = false;
    } catch (error) {
      console.error('WebSecurityAdapter: Clear data failed', error);
      throw new Error('Failed to clear secure data');
    }
  }

  // Private helper methods

  private async openSecureDB(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('HavenSecureDB', 1);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains('secure_store')) {
          const store = db.createObjectStore('secure_store', { keyPath: 'key' });
          store.createIndex('timestamp', 'timestamp', { unique: false });
        }
      };
    });
  }

  private async generateAndStoreMasterKey(): Promise<CryptoKey> {
    try {
      // Generate AES-GCM key
      const key = await this.crypto.generateKey(
        {
          name: 'AES-GCM',
          length: 256
        },
        true,
        ['encrypt', 'decrypt']
      );

      // Export and store the key
      const exportedKey = await this.crypto.exportKey('jwk', key);
      const keyString = JSON.stringify(exportedKey);
      
      // Store in IndexedDB (encrypted with a derived key from user authentication)      const db = await this.openSecureDB();
      const transaction = db.transaction(['secure_store'], 'readwrite');
      const store = transaction.objectStore('secure_store');
      
      await new Promise<void>((resolve, reject) => {
        const request = store.put({
          key: this.MASTER_KEY_NAME,
          value: keyString,
          timestamp: Date.now()
        });
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      });

      db.close();
      return key;
    } catch (error) {
      console.error('WebSecurityAdapter: Master key generation failed', error);
      throw new Error('Failed to generate master key');
    }
  }

  private async retrieveMasterKey(): Promise<CryptoKey | null> {
    try {
      const db = await this.openSecureDB();
      const transaction = db.transaction(['secure_store'], 'readonly');
      const store = transaction.objectStore('secure_store');
      
      const result = await new Promise<any>((resolve, reject) => {
        const request = store.get(this.MASTER_KEY_NAME);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });

      db.close();

      if (result && result.value) {
        const keyData = JSON.parse(result.value);
        return await this.crypto.importKey(
          'jwk',
          keyData,
          {
            name: 'AES-GCM',
            length: 256
          },
          true,
          ['encrypt', 'decrypt']
        );
      }
      return null;
    } catch (error) {
      console.error('WebSecurityAdapter: Master key retrieval failed', error);
      return null;
    }
  }

  private async deriveKeyFromString(keyString: string): Promise<CryptoKey> {
    try {
      const keyMaterial = await this.crypto.importKey(
        'raw',
        this.textEncoder.encode(keyString),
        'PBKDF2',
        false,
        ['deriveBits', 'deriveKey']
      );

      return await this.crypto.deriveKey(
        {
          name: 'PBKDF2',
          salt: this.textEncoder.encode('haven_health_passport_salt'),
          iterations: 100000,
          hash: 'SHA-256'
        },
        keyMaterial,
        {
          name: 'AES-GCM',
          length: 256
        },
        true,
        ['encrypt', 'decrypt']
      );
    } catch (error) {
      console.error('WebSecurityAdapter: Key derivation failed', error);
      throw new Error('Failed to derive key from string');
    }
  }
}

export default WebSecurityAdapter;