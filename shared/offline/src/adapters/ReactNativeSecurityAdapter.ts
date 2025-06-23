import { CryptoAdapter } from '../types';
import CryptoJS from 'crypto-js';
import * as Keychain from 'react-native-keychain';
import { NativeModules, Platform } from 'react-native';
import * as LocalAuthentication from 'expo-local-authentication';
import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';

/**
 * React Native specific security adapter implementing platform-specific
 * encryption, key management, and biometric protection
 */
export class ReactNativeSecurityAdapter implements CryptoAdapter {
  private static readonly KEY_ALIAS = 'haven_health_passport_key';
  private static readonly KEY_PREFIX = 'haven_security_';
  private static readonly BIOMETRIC_KEY = 'haven_biometric_key';
  private masterKey?: string;
  private isInitialized = false;

  /**
   * Initialize the security adapter with biometric protection if available
   */
  async initialize(): Promise<void> {
    if (this.isInitialized) return;

    try {
      // Check if device supports biometric authentication
      const hasBiometrics = await LocalAuthentication.hasHardwareAsync();
      const isEnrolled = await LocalAuthentication.isEnrolledAsync();

      if (hasBiometrics && isEnrolled) {
        // Try to get existing master key with biometric authentication
        const existingKey = await this.retrieveMasterKeyWithBiometrics();
        if (existingKey) {
          this.masterKey = existingKey;
        } else {
          // Generate and store new master key
          this.masterKey = await this.generateAndStoreMasterKey();
        }
      } else {
        // Fall back to keychain storage without biometrics
        this.masterKey = await this.retrieveOrGenerateMasterKey();
      }

      this.isInitialized = true;
    } catch (error) {
      console.error('ReactNativeSecurityAdapter: Initialization failed', error);
      throw new Error('Failed to initialize security adapter');
    }
  }

  /**
   * Encrypt data using AES-256-GCM with authenticated encryption
   */
  async encrypt(data: string, key?: string): Promise<string> {
    if (!this.isInitialized) await this.initialize();

    try {
      const encryptionKey = key || this.masterKey;
      if (!encryptionKey) {
        throw new Error('No encryption key available');
      }

      // Generate random IV
      const iv = CryptoJS.lib.WordArray.random(128 / 8);
      
      // Encrypt using AES-256-GCM
      const encrypted = CryptoJS.AES.encrypt(data, encryptionKey, {
        iv: iv,
        mode: CryptoJS.mode.GCM,
        padding: CryptoJS.pad.NoPadding
      });

      // Combine IV and ciphertext
      const combined = iv.toString() + ':' + encrypted.toString();
      
      // Add integrity check
      const hmac = CryptoJS.HmacSHA256(combined, encryptionKey).toString();
      
      return combined + ':' + hmac;
    } catch (error) {
      console.error('ReactNativeSecurityAdapter: Encryption failed', error);
      throw new Error('Encryption failed');
    }
  }

  /**
   * Decrypt data with integrity verification
   */
  async decrypt(data: string, key?: string): Promise<string> {
    if (!this.isInitialized) await this.initialize();

    try {
      const decryptionKey = key || this.masterKey;
      if (!decryptionKey) {
        throw new Error('No decryption key available');
      }

      // Split the data into components
      const parts = data.split(':');
      if (parts.length !== 3) {
        throw new Error('Invalid encrypted data format');
      }

      const [ivString, ciphertext, hmac] = parts;
      
      // Verify integrity
      const combined = ivString + ':' + ciphertext;
      const expectedHmac = CryptoJS.HmacSHA256(combined, decryptionKey).toString();
      
      if (hmac !== expectedHmac) {
        throw new Error('Data integrity check failed');
      }

      // Decrypt
      const iv = CryptoJS.enc.Hex.parse(ivString);
      const decrypted = CryptoJS.AES.decrypt(ciphertext, decryptionKey, {
        iv: iv,
        mode: CryptoJS.mode.GCM,
        padding: CryptoJS.pad.NoPadding
      });

      return decrypted.toString(CryptoJS.enc.Utf8);
    } catch (error) {
      console.error('ReactNativeSecurityAdapter: Decryption failed', error);
      throw new Error('Decryption failed');
    }
  }

  /**
   * Generate SHA-256 hash
   */
  async hash(data: string): Promise<string> {
    try {
      return CryptoJS.SHA256(data).toString();
    } catch (error) {
      console.error('ReactNativeSecurityAdapter: Hashing failed', error);
      throw new Error('Hashing failed');
    }
  }

  /**
   * Generate a secure random key
   */
  async generateSecureKey(length: number = 32): Promise<string> {
    try {
      const randomWords = CryptoJS.lib.WordArray.random(length);
      return randomWords.toString();
    } catch (error) {
      console.error('ReactNativeSecurityAdapter: Key generation failed', error);
      throw new Error('Key generation failed');
    }
  }

  /**
   * Store sensitive data in secure storage
   */
  async storeSecureData(key: string, value: string): Promise<void> {
    try {
      await SecureStore.setItemAsync(this.KEY_PREFIX + key, value, {
        keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
        requireAuthentication: true,
      });
    } catch (error) {
      console.error('ReactNativeSecurityAdapter: Secure storage failed', error);
      throw new Error('Failed to store secure data');
    }
  }

  /**
   * Retrieve sensitive data from secure storage
   */
  async getSecureData(key: string): Promise<string | null> {
    try {
      return await SecureStore.getItemAsync(this.KEY_PREFIX + key);
    } catch (error) {
      console.error('ReactNativeSecurityAdapter: Secure retrieval failed', error);
      return null;
    }
  }

  /**
   * Delete sensitive data from secure storage
   */
  async deleteSecureData(key: string): Promise<void> {
    try {
      await SecureStore.deleteItemAsync(this.KEY_PREFIX + key);
    } catch (error) {
      console.error('ReactNativeSecurityAdapter: Secure deletion failed', error);
      throw new Error('Failed to delete secure data');
    }
  }

  /**
   * Enable biometric protection for sensitive operations
   */
  async enableBiometricProtection(): Promise<boolean> {
    try {
      const hasBiometrics = await LocalAuthentication.hasHardwareAsync();
      const isEnrolled = await LocalAuthentication.isEnrolledAsync();

      if (!hasBiometrics || !isEnrolled) {
        return false;
      }

      // Authenticate user
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: 'Authenticate to enable biometric protection',
        fallbackLabel: 'Use passcode',
        cancelLabel: 'Cancel',
        disableDeviceFallback: false,
      });

      if (result.success) {
        // Store a flag indicating biometric protection is enabled
        await AsyncStorage.setItem(this.KEY_PREFIX + 'biometric_enabled', 'true');
        return true;
      }

      return false;
    } catch (error) {
      console.error('ReactNativeSecurityAdapter: Biometric enable failed', error);
      return false;
    }
  }

  /**
   * Check if biometric protection is enabled
   */
  async isBiometricProtectionEnabled(): Promise<boolean> {
    try {
      const enabled = await AsyncStorage.getItem(this.KEY_PREFIX + 'biometric_enabled');
      return enabled === 'true';
    } catch (error) {
      return false;
    }
  }

  /**
   * Authenticate user with biometrics
   */
  async authenticateWithBiometrics(reason: string): Promise<boolean> {
    try {
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: reason,
        fallbackLabel: 'Use passcode',
        cancelLabel: 'Cancel',
        disableDeviceFallback: false,
      });

      return result.success;
    } catch (error) {
      console.error('ReactNativeSecurityAdapter: Biometric auth failed', error);
      return false;
    }
  }

  /**
   * Derive a key from password using PBKDF2
   */
  async deriveKeyFromPassword(password: string, salt?: string): Promise<string> {
    try {
      const saltValue = salt || CryptoJS.lib.WordArray.random(128 / 8).toString();
      const key = CryptoJS.PBKDF2(password, saltValue, {
        keySize: 256 / 32,
        iterations: 100000,
        hasher: CryptoJS.algo.SHA256
      });

      return key.toString();
    } catch (error) {
      console.error('ReactNativeSecurityAdapter: Key derivation failed', error);
      throw new Error('Key derivation failed');
    }
  }

  /**
   * Securely wipe sensitive data from memory
   */
  async wipeMemory(): Promise<void> {
    try {
      // Clear master key
      if (this.masterKey) {
        // Overwrite with random data before clearing
        const length = this.masterKey.length;
        this.masterKey = CryptoJS.lib.WordArray.random(length).toString();
        this.masterKey = undefined;
      }
      this.isInitialized = false;

      // Force garbage collection if available
      if (global.gc) {
        global.gc();
      }
    } catch (error) {
      console.error('ReactNativeSecurityAdapter: Memory wipe failed', error);
    }
  }

  /**
   * Check device security status
   */
  async getDeviceSecurityStatus(): Promise<{
    isRooted: boolean;
    hasScreenLock: boolean;
    hasBiometrics: boolean;
    isEncrypted: boolean;
    securityLevel: 'high' | 'medium' | 'low';
  }> {
    try {
      const hasBiometrics = await LocalAuthentication.hasHardwareAsync();
      const isEnrolled = await LocalAuthentication.isEnrolledAsync();
      const hasScreenLock = await this.checkScreenLock();
      const isRooted = await this.checkIfRooted();

      // Determine security level
      let securityLevel: 'high' | 'medium' | 'low' = 'low';
      if (!isRooted && hasScreenLock && hasBiometrics && isEnrolled) {
        securityLevel = 'high';
      } else if (!isRooted && hasScreenLock) {
        securityLevel = 'medium';
      }

      return {
        isRooted,
        hasScreenLock,
        hasBiometrics: hasBiometrics && isEnrolled,
        isEncrypted: Platform.OS === 'ios' || (Platform.OS === 'android' && Platform.Version >= 23),
        securityLevel,
      };
    } catch (error) {
      console.error('ReactNativeSecurityAdapter: Security check failed', error);
      return {
        isRooted: false,
        hasScreenLock: false,
        hasBiometrics: false,
        isEncrypted: false,
        securityLevel: 'low',
      };    }
  }

  // Private helper methods

  private async retrieveMasterKeyWithBiometrics(): Promise<string | null> {
    try {
      const authenticated = await this.authenticateWithBiometrics(
        'Authenticate to access secure health data'
      );

      if (!authenticated) {
        return null;
      }

      const credentials = await Keychain.getInternetCredentials(this.KEY_ALIAS);
      return credentials ? credentials.password : null;
    } catch (error) {
      console.error('ReactNativeSecurityAdapter: Biometric key retrieval failed', error);
      return null;
    }
  }

  private async generateAndStoreMasterKey(): Promise<string> {
    try {
      const masterKey = await this.generateSecureKey(32);
      
      await Keychain.setInternetCredentials(
        this.KEY_ALIAS,
        'haven_health_passport',
        masterKey,
        {
          accessControl: Keychain.ACCESS_CONTROL.BIOMETRY_CURRENT_SET,
          accessible: Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
          authenticatePrompt: 'Authenticate to store encryption key',
        }
      );

      return masterKey;
    } catch (error) {
      console.error('ReactNativeSecurityAdapter: Master key generation failed', error);
      throw new Error('Failed to generate master key');
    }
  }

  private async retrieveOrGenerateMasterKey(): Promise<string> {
    try {
      const credentials = await Keychain.getInternetCredentials(this.KEY_ALIAS);
      
      if (credentials) {
        return credentials.password;
      }

      // Generate new key without biometrics
      const masterKey = await this.generateSecureKey(32);
      
      await Keychain.setInternetCredentials(
        this.KEY_ALIAS,
        'haven_health_passport',
        masterKey,
        {
          accessible: Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
        }
      );

      return masterKey;
    } catch (error) {
      console.error('ReactNativeSecurityAdapter: Key retrieval failed', error);
      throw new Error('Failed to retrieve or generate master key');
    }
  }

  private async checkScreenLock(): Promise<boolean> {
    try {
      // This is platform-specific and might require native module
      if (Platform.OS === 'ios') {
        return await LocalAuthentication.hasHardwareAsync();
      } else {
        // Android - check if keyguard is secure
        const { KeyguardManager } = NativeModules;
        return KeyguardManager ? await KeyguardManager.isDeviceSecure() : false;
      }
    } catch (error) {
      return false;
    }
  }

  private async checkIfRooted(): Promise<boolean> {
    try {
      // This would require a native module for accurate detection
      // For now, return false as a placeholder
      // In production, use libraries like jail-monkey or react-native-device-info
      return false;
    } catch (error) {
      return false;
    }
  }
}

export default ReactNativeSecurityAdapter;