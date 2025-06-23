/**
 * Haven Health Passport API Client
 * 
 * This module provides a secure, type-safe interface to the Haven Health Passport
 * backend API for managing refugee health records. It includes authentication,
 * error handling, and all necessary endpoints for the healthcare system.
 * 
 * CRITICAL: This is a healthcare system for displaced refugees - security and
 * data protection are paramount.
 */

import { z } from 'zod';

// Base API Configuration
const API_BASE_URL = process.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_VERSION = '/api/v2';

// TEMPORARY: Disable API calls for frontend-only review
const FRONTEND_ONLY_MODE = process.env.VITE_FRONTEND_ONLY === 'true' || process.env.NODE_ENV === 'development';

// Types and Schemas
export interface ApiResponse<T = any> {
  data: T;
  message?: string;
  status: 'success' | 'error';
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pages: number;
  per_page: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// Patient Types
export interface PatientIdentifier {
  system: string;
  value: string;
  type?: string;
}

export interface PatientName {
  given: string[];
  family: string;
  prefix?: string[];
  suffix?: string[];
  use?: string;
}

export interface PatientContact {
  system: string;
  value: string;
  use?: string;
}

export interface Address {
  line?: string[];
  city?: string;
  district?: string;
  state?: string;
  postalCode?: string;
  country?: string;
  use?: string;
  type?: string;
}

export interface EmergencyContact {
  name: PatientName;
  relationship: string;
  contact: PatientContact[];
}

export interface Patient {
  id: string;
  identifier: PatientIdentifier[];
  name: PatientName[];
  birthDate: string;
  gender: 'male' | 'female' | 'other' | 'unknown';
  contact?: PatientContact[];
  address?: Address[];
  language: string[];
  emergencyContact?: EmergencyContact[];
  active: boolean;
  createdAt: string;
  updatedAt: string;
  version: number;
  verificationStatus: string;
}

export interface PatientCreateRequest {
  identifier: PatientIdentifier[];
  name: PatientName[];
  birthDate: string;
  gender: 'male' | 'female' | 'other' | 'unknown';
  contact?: PatientContact[];
  address?: Address[];
  language?: string[];
  emergencyContact?: EmergencyContact[];
  active?: boolean;
}

export interface PatientUpdateRequest {
  name?: PatientName[];
  contact?: PatientContact[];
  address?: Address[];
  language?: string[];
  emergencyContact?: EmergencyContact[];
  active?: boolean;
}

// Health Record Types
export interface CodeableConcept {
  coding: { system: string; code: string; display?: string }[];
  text?: string;
}

export interface HealthRecord {
  id: string;
  resourceType: string;
  patientId: string;
  status: string;
  code: CodeableConcept;
  effectiveDateTime?: string;
  valueQuantity?: Record<string, any>;
  valueString?: string;
  valueBoolean?: boolean;
  note?: Record<string, string>[];
  category?: CodeableConcept[];
  createdAt: string;
  updatedAt: string;
  createdBy: string;
  version: number;
  verificationStatus: string;
  blockchainHash?: string;
  isEncrypted: boolean;
}

export interface HealthRecordCreateRequest {
  resourceType: string;
  patientId: string;
  status: string;
  code: CodeableConcept;
  effectiveDateTime?: string;
  valueQuantity?: Record<string, any>;
  valueString?: string;
  valueBoolean?: boolean;
  note?: Record<string, string>[];
  category?: CodeableConcept[];
}

// Authentication Types
export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  organization?: string;
  role?: string;
}

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  organization?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Error Types
export class ApiError extends Error {
  constructor(
    public status: number,
    public message: string,
    public details?: any
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export class AuthenticationError extends ApiError {
  constructor(message: string = 'Authentication failed') {
    super(401, message);
    this.name = 'AuthenticationError';
  }
}

export class AuthorizationError extends ApiError {
  constructor(message: string = 'Access denied') {
    super(403, message);
    this.name = 'AuthorizationError';
  }
}

export class ValidationError extends ApiError {
  constructor(message: string, details?: any) {
    super(422, message, details);
    this.name = 'ValidationError';
  }
}

// Token Management
class TokenManager {
  private static readonly ACCESS_TOKEN_KEY = 'haven_access_token';
  private static readonly REFRESH_TOKEN_KEY = 'haven_refresh_token';
  private static readonly TOKEN_EXPIRY_KEY = 'haven_token_expiry';

  static setTokens(tokens: AuthTokens): void {
    const expiryTime = Date.now() + (tokens.expires_in * 1000);
    
    localStorage.setItem(this.ACCESS_TOKEN_KEY, tokens.access_token);
    localStorage.setItem(this.REFRESH_TOKEN_KEY, tokens.refresh_token);
    localStorage.setItem(this.TOKEN_EXPIRY_KEY, expiryTime.toString());
  }

  static getAccessToken(): string | null {
    return localStorage.getItem(this.ACCESS_TOKEN_KEY);
  }

  static getRefreshToken(): string | null {
    return localStorage.getItem(this.REFRESH_TOKEN_KEY);
  }

  static isTokenExpired(): boolean {
    const expiry = localStorage.getItem(this.TOKEN_EXPIRY_KEY);
    if (!expiry) return true;
    
    return Date.now() > parseInt(expiry, 10);
  }

  static clearTokens(): void {
    localStorage.removeItem(this.ACCESS_TOKEN_KEY);
    localStorage.removeItem(this.REFRESH_TOKEN_KEY);
    localStorage.removeItem(this.TOKEN_EXPIRY_KEY);
  }
}

// HTTP Client
class HttpClient {
  private baseUrl: string;
  private defaultHeaders: Record<string, string>;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
    this.defaultHeaders = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    // TEMPORARY: Return mock data in frontend-only mode
    if (FRONTEND_ONLY_MODE) {
      console.log(`[FRONTEND-ONLY] Mocking API call: ${endpoint}`);
      return this.getMockResponse<T>(endpoint) as T;
    }

    const url = `${this.baseUrl}${endpoint}`;
    
    // Add authentication header if token exists
    const accessToken = TokenManager.getAccessToken();
    const headers = { ...this.defaultHeaders };
    
    if (accessToken && !TokenManager.isTokenExpired()) {
      headers.Authorization = `Bearer ${accessToken}`;
    }

    // Merge headers
    const finalOptions: RequestInit = {
      ...options,
      headers: {
        ...headers,
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, finalOptions);
      
      // Handle different response types
      if (response.status === 401) {
        // Try to refresh token
        const refreshed = await this.refreshToken();
        if (refreshed) {
          // Retry the request with new token
          headers.Authorization = `Bearer ${TokenManager.getAccessToken()}`;
          const retryResponse = await fetch(url, {
            ...finalOptions,
            headers: { ...headers, ...options.headers },
          });
          return this.handleResponse(retryResponse);
        } else {
          TokenManager.clearTokens();
          throw new AuthenticationError('Session expired. Please log in again.');
        }
      }

      return this.handleResponse<T>(response);
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      throw new ApiError(500, 'Network error occurred', error);
    }
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    const contentType = response.headers.get('content-type');
    
    if (response.status === 204) {
      return {} as T;
    }

    let data: any;
    if (contentType?.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    if (!response.ok) {
      const message = data?.detail || data?.message || `HTTP ${response.status}`;
      const details = data?.errors || data?.validation_errors;
      
      switch (response.status) {
        case 401:
          throw new AuthenticationError(message);
        case 403:
          throw new AuthorizationError(message);
        case 422:
          throw new ValidationError(message, details);
        default:
          throw new ApiError(response.status, message, details);
      }
    }

    return data;
  }

  private async refreshToken(): Promise<boolean> {
    const refreshToken = TokenManager.getRefreshToken();
    if (!refreshToken) return false;

    try {
      const response = await fetch(`${this.baseUrl}/api/v2/auth/refresh`, {
        method: 'POST',
        headers: this.defaultHeaders,
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (response.ok) {
        const tokens: AuthTokens = await response.json();
        TokenManager.setTokens(tokens);
        return true;
      }
    } catch (error) {
      console.error('Token refresh failed:', error);
    }

    return false;
  }

  private getMockResponse<T>(endpoint: string): any {
    console.log(`[MOCK] Handling endpoint: ${endpoint}`);
    
    // Return empty/default responses for frontend-only mode
    if (endpoint.includes('patients')) {
      const mockPatients = [{
        id: '1',
        identifier: [{ system: 'unhcr', value: 'UNHCR-123456' }],
        name: [{ given: ['John'], family: 'Doe' }],
        birthDate: '1990-01-01',
        gender: 'male' as const,
        contact: [{ system: 'phone', value: '+1234567890', use: 'mobile' }],
        address: [{ city: 'Damascus', country: 'Syria' }],
        language: ['Arabic', 'English'],
        active: true,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        version: 1,
        verificationStatus: 'verified'
      }];
      return { items: mockPatients, total: 1, page: 1, pages: 1, per_page: 10, has_next: false, has_prev: false };
    }
    if (endpoint.includes('health-records')) {
      return { items: [], total: 0, page: 1, pages: 0, per_page: 10, has_next: false, has_prev: false };
    }
    if (endpoint.includes('user') || endpoint.includes('login') || endpoint.includes('/auth/me')) {
      return { 
        id: '1', 
        email: 'demo@havenhealthpassport.com', 
        first_name: 'Demo', 
        last_name: 'User', 
        role: 'healthcare_worker',
        organization: 'Demo Clinic',
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      };
    }
    if (endpoint.includes('dashboard-stats')) {
      return { totalPatients: 1, verifiedRecords: 1, pendingVerifications: 0, recentActivity: [] };
    }
    if (endpoint.includes('health-check')) {
      return { status: 'ok', version: '1.0.0', timestamp: new Date().toISOString() };
    }
    console.log(`[MOCK] No handler for endpoint: ${endpoint}, returning empty object`);
    return {};
  }

  async get<T>(endpoint: string, params?: Record<string, any>): Promise<T> {
    const url = new URL(endpoint, this.baseUrl);
    if (params) {
      Object.keys(params).forEach(key => {
        if (params[key] !== undefined && params[key] !== null) {
          url.searchParams.append(key, params[key].toString());
        }
      });
    }

    return this.request<T>(url.pathname + url.search);
  }

  async post<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async put<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async patch<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'DELETE',
    });
  }

  async upload<T>(endpoint: string, formData: FormData): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: formData,
      headers: {
        // Don't set Content-Type, let browser set it with boundary
        'Accept': 'application/json',
      },
    });
  }
}

// API Client Class
export class HavenApiClient {
  private client: HttpClient;

  constructor(baseUrl: string = API_BASE_URL) {
    this.client = new HttpClient(baseUrl + API_VERSION);
  }

  // Authentication Methods
  async login(credentials: LoginCredentials): Promise<AuthTokens> {
    const tokens = await this.client.post<AuthTokens>('/auth/login', credentials);
    TokenManager.setTokens(tokens);
    return tokens;
  }

  async register(userData: RegisterRequest): Promise<User> {
    return this.client.post<User>('/auth/register', userData);
  }

  async logout(): Promise<void> {
    try {
      await this.client.post('/auth/logout');
    } finally {
      TokenManager.clearTokens();
    }
  }

  async getCurrentUser(): Promise<User> {
    return this.client.get<User>('/auth/me');
  }

  async refreshToken(): Promise<AuthTokens> {
    const refreshToken = TokenManager.getRefreshToken();
    if (!refreshToken) {
      throw new AuthenticationError('No refresh token available');
    }

    const tokens = await this.client.post<AuthTokens>('/auth/refresh', {
      refresh_token: refreshToken,
    });
    TokenManager.setTokens(tokens);
    return tokens;
  }

  // Patient Methods
  async getPatients(params?: {
    page?: number;
    page_size?: number;
    search?: string;
    active?: boolean;
    verification_status?: string;
  }): Promise<PaginatedResponse<Patient>> {
    return this.client.get<PaginatedResponse<Patient>>('/patients', params);
  }

  async getPatient(id: string): Promise<Patient> {
    return this.client.get<Patient>(`/patients/${id}`);
  }

  async createPatient(patientData: PatientCreateRequest): Promise<Patient> {
    return this.client.post<Patient>('/patients', patientData);
  }

  async updatePatient(id: string, updateData: PatientUpdateRequest): Promise<Patient> {
    return this.client.put<Patient>(`/patients/${id}`, updateData);
  }

  async deletePatient(id: string): Promise<void> {
    return this.client.delete<void>(`/patients/${id}`);
  }

  async exportPatients(params?: {
    export_format?: 'csv' | 'json';
    search?: string;
    patient_status?: string;
    nationality?: string;
    gender?: string;
    limit?: number;
  }): Promise<Blob> {
    const response = await fetch(`${API_BASE_URL}${API_VERSION}/patients/export`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${TokenManager.getAccessToken()}`,
      },
    });

    if (!response.ok) {
      throw new ApiError(response.status, 'Export failed');
    }

    return response.blob();
  }

  // Health Record Methods
  async getHealthRecords(params?: {
    patient_id?: string;
    resource_type?: string;
    record_status?: string;
    page?: number;
    page_size?: number;
    start_date?: string;
    end_date?: string;
  }): Promise<PaginatedResponse<HealthRecord>> {
    return this.client.get<PaginatedResponse<HealthRecord>>('/health-records', params);
  }

  async getHealthRecord(id: string): Promise<HealthRecord> {
    return this.client.get<HealthRecord>(`/health-records/${id}`);
  }

  async createHealthRecord(recordData: HealthRecordCreateRequest): Promise<HealthRecord> {
    return this.client.post<HealthRecord>('/health-records', recordData);
  }

  async updateHealthRecord(id: string, updateData: Partial<HealthRecordCreateRequest>): Promise<HealthRecord> {
    return this.client.put<HealthRecord>(`/health-records/${id}`, updateData);
  }

  async deleteHealthRecord(id: string): Promise<void> {
    return this.client.delete<void>(`/health-records/${id}`);
  }

  // File Upload Methods
  async uploadFile(file: File, metadata?: Record<string, any>): Promise<{ id: string; url: string }> {
    const formData = new FormData();
    formData.append('file', file);
    if (metadata) {
      formData.append('metadata', JSON.stringify(metadata));
    }

    return this.client.upload<{ id: string; url: string }>('/files/upload', formData);
  }

  // Analytics Methods
  async getDashboardStats(): Promise<{
    totalPatients: number;
    verifiedRecords: number;
    pendingVerifications: number;
    recentActivity: any[];
  }> {
    return this.client.get<any>('/dashboard/stats');
  }

  async getAnalytics(params?: {
    start_date?: string;
    end_date?: string;
    metrics?: string[];
  }): Promise<any> {
    return this.client.get<any>('/analytics', params);
  }

  // Organization Methods
  async getOrganizations(): Promise<any[]> {
    return this.client.get<any[]>('/organizations');
  }

  // Notification Methods
  async getNotifications(params?: {
    page?: number;
    page_size?: number;
    unread_only?: boolean;
  }): Promise<PaginatedResponse<any>> {
    return this.client.get<PaginatedResponse<any>>('/notifications', params);
  }

  async markNotificationRead(id: string): Promise<void> {
    return this.client.patch<void>(`/notifications/${id}/read`);
  }

  // Health Check
  async healthCheck(): Promise<{ status: string; version: string; timestamp: string }> {
    return this.client.get<{ status: string; version: string; timestamp: string }>('/health');
  }

  // Utility Methods
  isAuthenticated(): boolean {
    // In frontend-only mode, always return true for UI review
    if (FRONTEND_ONLY_MODE) {
      return true;
    }
    return TokenManager.getAccessToken() !== null && !TokenManager.isTokenExpired();
  }

  clearAuth(): void {
    TokenManager.clearTokens();
  }
}

// Export singleton instance
export const apiClient = new HavenApiClient();

// Export utility functions
export { TokenManager };

// Export all types
export type {
  Patient,
  PatientCreateRequest,
  PatientUpdateRequest,
  HealthRecord,
  HealthRecordCreateRequest,
  User,
  AuthTokens,
  LoginCredentials,
  RegisterRequest,
  PaginatedResponse,
  ApiResponse,
}; 