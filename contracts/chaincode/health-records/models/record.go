package models

import (
    "time"
)

// HealthRecord represents a health record on the blockchain
type HealthRecord struct {
    RecordID        string                 `json:"recordId"`
    PatientID       string                 `json:"patientId"`
    ProviderID      string                 `json:"providerId"`
    RecordType      string                 `json:"recordType"`
    CreatedAt       time.Time              `json:"createdAt"`
    UpdatedAt       time.Time              `json:"updatedAt"`
    Version         int                    `json:"version"`
    EncryptedData   string                 `json:"encryptedData"`
    DataHash        string                 `json:"dataHash"`
    Metadata        map[string]interface{} `json:"metadata"`
    VerificationIDs []string               `json:"verificationIds"`
    AccessGrants    []string               `json:"accessGrants"`
    Status          string                 `json:"status"`
    ObjectType      string                 `json:"objectType"`
}

// RecordType constants
const (
    RecordTypeMedicalHistory = "medical_history"
    RecordTypePrescription   = "prescription"
    RecordTypeLabResult      = "lab_result"
    RecordTypeImaging        = "imaging"
    RecordTypeVaccination    = "vaccination"
    RecordTypeConsultation   = "consultation"
)

// RecordStatus constants
const (
    StatusActive   = "active"
    StatusArchived = "archived"
    StatusDeleted  = "deleted"
)

// HistoryRecord represents a historical version of a health record
type HistoryRecord struct {
    TxID      string       `json:"txId"`
    Value     HealthRecord `json:"value"`
    Timestamp time.Time    `json:"timestamp"`
    IsDelete  bool         `json:"isDelete"`
}

// PaginatedQueryResult structure for paginated queries
type PaginatedQueryResult struct {
    Records      []*HealthRecord `json:"records"`
    Bookmark     string          `json:"bookmark"`
    FetchedCount int32           `json:"fetchedCount"`
}

// Validate validates the health record fields
func (hr *HealthRecord) Validate() error {
    // Implementation will be added in validation.go
    return nil
}

// NewHealthRecord creates a new health record instance
func NewHealthRecord(patientID, providerID, recordType string) *HealthRecord {
    return &HealthRecord{
        PatientID:       patientID,
        ProviderID:      providerID,
        RecordType:      recordType,
        CreatedAt:       time.Now(),
        UpdatedAt:       time.Now(),
        Version:         1,
        Status:          StatusActive,
        ObjectType:      "healthRecord",
        Metadata:        make(map[string]interface{}),
        VerificationIDs: []string{},
        AccessGrants:    []string{},
    }
}
