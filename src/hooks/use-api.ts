/**
 * React Hooks for Haven Health Passport API
 * 
 * This module provides React hooks for seamless integration with the
 * Haven Health Passport API, including state management, caching,
 * and error handling.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useQuery, useMutation, useQueryClient, UseQueryResult } from '@tanstack/react-query';
import { 
  apiClient,
  Patient,
  PatientCreateRequest,
  PatientUpdateRequest,
  HealthRecord,
  HealthRecordCreateRequest,
  User,
  LoginCredentials,
  RegisterRequest,
  PaginatedResponse,
  ApiError,
  AuthenticationError,
  AuthorizationError,
  ValidationError,
} from '@/lib/api-client';

// Query Keys
export const queryKeys = {
  patients: ['patients'] as const,
  patient: (id: string) => ['patients', id] as const,
  healthRecords: ['health-records'] as const,
  healthRecord: (id: string) => ['health-records', id] as const,
  user: ['user'] as const,
  notifications: ['notifications'] as const,
  analytics: ['analytics'] as const,
  organizations: ['organizations'] as const,
};

// Hook Types
interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: ApiError | null;
}

interface UsePaginatedApiState<T> extends UseApiState<PaginatedResponse<T>> {
  hasNextPage: boolean;
  hasPrevPage: boolean;
  currentPage: number;
  totalPages: number;
}

// Authentication Hooks
export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState(apiClient.isAuthenticated());
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const queryClient = useQueryClient();

  const login = useCallback(async (credentials: LoginCredentials) => {
    setLoading(true);
    setError(null);
    try {
      await apiClient.login(credentials);
      const userData = await apiClient.getCurrentUser();
      setUser(userData);
      setIsAuthenticated(true);
      queryClient.invalidateQueries();
      return userData;
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError);
      throw apiError;
    } finally {
      setLoading(false);
    }
  }, [queryClient]);

  const register = useCallback(async (userData: RegisterRequest) => {
    setLoading(true);
    setError(null);
    try {
      const newUser = await apiClient.register(userData);
      return newUser;
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError);
      throw apiError;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    setLoading(true);
    try {
      await apiClient.logout();
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      setUser(null);
      setIsAuthenticated(false);
      setLoading(false);
      queryClient.clear();
    }
  }, [queryClient]);

  const getCurrentUser = useCallback(async () => {
    if (!isAuthenticated) return null;
    
    setLoading(true);
    setError(null);
    try {
      const userData = await apiClient.getCurrentUser();
      setUser(userData);
      return userData;
    } catch (err) {
      const apiError = err as ApiError;
      if (apiError.status === 401) {
        setIsAuthenticated(false);
        setUser(null);
        queryClient.clear();
      }
      setError(apiError);
      throw apiError;
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, queryClient]);

  // Initialize user data on mount
  useEffect(() => {
    if (isAuthenticated && !user) {
      getCurrentUser().catch(() => {
        // Error is already handled in getCurrentUser
      });
    }
  }, [isAuthenticated, user, getCurrentUser]);

  return {
    isAuthenticated,
    user,
    loading,
    error,
    login,
    register,
    logout,
    getCurrentUser,
  };
}

// Patient Hooks
export function usePatients(params?: {
  page?: number;
  page_size?: number;
  search?: string;
  active?: boolean;
  verification_status?: string;
}) {
  return useQuery({
    queryKey: [...queryKeys.patients, params],
    queryFn: () => apiClient.getPatients(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: (failureCount, error) => {
      if (error instanceof AuthenticationError || error instanceof AuthorizationError) {
        return false;
      }
      return failureCount < 3;
    },
  });
}

export function usePatient(id: string) {
  return useQuery({
    queryKey: queryKeys.patient(id),
    queryFn: () => apiClient.getPatient(id),
    enabled: !!id,
    staleTime: 10 * 60 * 1000, // 10 minutes
    retry: (failureCount, error) => {
      if (error instanceof AuthenticationError || error instanceof AuthorizationError) {
        return false;
      }
      return failureCount < 3;
    },
  });
}

export function useCreatePatient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (patientData: PatientCreateRequest) => apiClient.createPatient(patientData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.patients });
    },
  });
}

export function useUpdatePatient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: PatientUpdateRequest }) =>
      apiClient.updatePatient(id, data),
    onSuccess: (updatedPatient) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.patients });
      queryClient.setQueryData(queryKeys.patient(updatedPatient.id), updatedPatient);
    },
  });
}

export function useDeletePatient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => apiClient.deletePatient(id),
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.patients });
      queryClient.removeQueries({ queryKey: queryKeys.patient(deletedId) });
    },
  });
}

// Health Records Hooks
export function useHealthRecords(params?: {
  patient_id?: string;
  resource_type?: string;
  record_status?: string;
  page?: number;
  page_size?: number;
  start_date?: string;
  end_date?: string;
}) {
  return useQuery({
    queryKey: [...queryKeys.healthRecords, params],
    queryFn: () => apiClient.getHealthRecords(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: (failureCount, error) => {
      if (error instanceof AuthenticationError || error instanceof AuthorizationError) {
        return false;
      }
      return failureCount < 3;
    },
  });
}

export function useHealthRecord(id: string) {
  return useQuery({
    queryKey: queryKeys.healthRecord(id),
    queryFn: () => apiClient.getHealthRecord(id),
    enabled: !!id,
    staleTime: 10 * 60 * 1000, // 10 minutes
    retry: (failureCount, error) => {
      if (error instanceof AuthenticationError || error instanceof AuthorizationError) {
        return false;
      }
      return failureCount < 3;
    },
  });
}

export function useCreateHealthRecord() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (recordData: HealthRecordCreateRequest) => apiClient.createHealthRecord(recordData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.healthRecords });
    },
  });
}

export function useUpdateHealthRecord() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<HealthRecordCreateRequest> }) =>
      apiClient.updateHealthRecord(id, data),
    onSuccess: (updatedRecord) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.healthRecords });
      queryClient.setQueryData(queryKeys.healthRecord(updatedRecord.id), updatedRecord);
    },
  });
}

export function useDeleteHealthRecord() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => apiClient.deleteHealthRecord(id),
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.healthRecords });
      queryClient.removeQueries({ queryKey: queryKeys.healthRecord(deletedId) });
    },
  });
}

// File Upload Hook
export function useFileUpload() {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<ApiError | null>(null);

  const upload = useCallback(async (
    file: File,
    metadata?: Record<string, any>,
    onProgress?: (progress: number) => void
  ) => {
    setUploading(true);
    setError(null);
    setUploadProgress(0);

    try {
      // For now, we'll simulate progress since the basic fetch API doesn't support progress
      // In a production environment, you might want to use XMLHttpRequest or a library like axios
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => {
          const next = prev + Math.random() * 20;
          if (next >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          onProgress?.(next);
          return next;
        });
      }, 200);

      const result = await apiClient.uploadFile(file, metadata);
      
      clearInterval(progressInterval);
      setUploadProgress(100);
      onProgress?.(100);
      
      return result;
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError);
      throw apiError;
    } finally {
      setUploading(false);
      setTimeout(() => setUploadProgress(0), 1000);
    }
  }, []);

  return {
    upload,
    uploading,
    uploadProgress,
    error,
  };
}

// Analytics Hooks
export function useDashboardStats() {
  return useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: () => apiClient.getDashboardStats(),
    staleTime: 60 * 1000, // 1 minute
    refetchInterval: 60 * 1000, // Refresh every minute
  });
}

export function useAnalytics(params?: {
  start_date?: string;
  end_date?: string;
  metrics?: string[];
}) {
  return useQuery({
    queryKey: [...queryKeys.analytics, params],
    queryFn: () => apiClient.getAnalytics(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Notifications Hook
export function useNotifications(params?: {
  page?: number;
  page_size?: number;
  unread_only?: boolean;
}) {
  return useQuery({
    queryKey: [...queryKeys.notifications, params],
    queryFn: () => apiClient.getNotifications(params),
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 30 * 1000, // Refresh every 30 seconds
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => apiClient.markNotificationRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications });
    },
  });
}

// Organizations Hook
export function useOrganizations() {
  return useQuery({
    queryKey: queryKeys.organizations,
    queryFn: () => apiClient.getOrganizations(),
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

// Generic API Hook
export function useApi<T>(
  apiCall: () => Promise<T>,
  dependencies: any[] = []
): UseApiState<T> {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: false,
    error: null,
  });

  const mountedRef = useRef(true);

  const execute = useCallback(async () => {
    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const result = await apiCall();
      if (mountedRef.current) {
        setState({ data: result, loading: false, error: null });
      }
    } catch (err) {
      if (mountedRef.current) {
        setState(prev => ({
          ...prev,
          loading: false,
          error: err as ApiError,
        }));
      }
    }
  }, dependencies);

  useEffect(() => {
    execute();
  }, [execute]);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  return state;
}

// Real-time updates hook (for WebSocket connections)
export function useRealTimeUpdates() {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (!apiClient.isAuthenticated()) {
      setError('Must be authenticated to connect to real-time updates');
      return;
    }

    try {
      // This would be the WebSocket endpoint for real-time updates
      const wsUrl = `${process.env.VITE_WS_URL || 'ws://localhost:8000'}/ws/updates`;
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        setConnected(true);
        setError(null);
      };

      wsRef.current.onmessage = (event) => {
        try {
          const update = JSON.parse(event.data);
          
          // Invalidate relevant queries based on the update type
          switch (update.type) {
            case 'patient_updated':
              queryClient.invalidateQueries({ queryKey: queryKeys.patients });
              if (update.patient_id) {
                queryClient.invalidateQueries({ queryKey: queryKeys.patient(update.patient_id) });
              }
              break;
            case 'health_record_updated':
              queryClient.invalidateQueries({ queryKey: queryKeys.healthRecords });
              if (update.record_id) {
                queryClient.invalidateQueries({ queryKey: queryKeys.healthRecord(update.record_id) });
              }
              break;
            case 'notification':
              queryClient.invalidateQueries({ queryKey: queryKeys.notifications });
              break;
          }
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };

      wsRef.current.onerror = () => {
        setError('WebSocket connection error');
      };

      wsRef.current.onclose = () => {
        setConnected(false);
      };
    } catch (err) {
      setError('Failed to connect to real-time updates');
    }
  }, [queryClient]);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, []);

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    connected,
    error,
    connect,
    disconnect,
  };
}

// Health Check Hook
export function useHealthCheck() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiClient.healthCheck(),
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 60 * 1000, // Check every minute
    retry: false, // Don't retry health checks
  });
}

// Export all error types for easy access
export {
  ApiError,
  AuthenticationError,
  AuthorizationError,
  ValidationError,
}; 