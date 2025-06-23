package utils

import (
    "fmt"
    "regexp"
    "strings"

    "github.com/haven-health-passport/chaincode/health-records/models"
)

// Validation constants
const (
    MaxDataSize     = 10 * 1024 * 1024 // 10MB
    MinPasswordLen  = 8
    MaxMetadataSize = 1024 * 1024 // 1MB
)

// Regular expressions for validation
var (
    emailRegex    = regexp.MustCompile(`^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`)
    uuidRegex     = regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`)
    alphaNumRegex = regexp.MustCompile(`^[a-zA-Z0-9]+$`)
)

// ValidateHealthRecord validates a health record
func ValidateHealthRecord(record *models.HealthRecord) error {
    // Check required fields
    if record.PatientID == "" {
        return fmt.Errorf("patient ID is required")
    }
    if record.ProviderID == "" {
        return fmt.Errorf("provider ID is required")
    }
    if record.RecordType == "" {
        return fmt.Errorf("record type is required")
    }
    if record.DataHash == "" {
        return fmt.Errorf("data hash is required")
    }

    // Validate record type
    validTypes := []string{
        models.RecordTypeMedicalHistory,
        models.RecordTypePrescription,
        models.RecordTypeLabResult,
        models.RecordTypeImaging,
        models.RecordTypeVaccination,
        models.RecordTypeConsultation,
    }
    if !contains(validTypes, record.RecordType) {
        return fmt.Errorf("invalid record type: %s", record.RecordType)
    }

    // Validate data size
    if len(record.EncryptedData) > MaxDataSize {
        return fmt.Errorf("encrypted data exceeds maximum size of %d bytes", MaxDataSize)
    }

    // Validate status
    validStatuses := []string{
        models.StatusActive,
        models.StatusArchived,
        models.StatusDeleted,
    }
    if record.Status != "" && !contains(validStatuses, record.Status) {
        return fmt.Errorf("invalid status: %s", record.Status)
    }

    return nil
}

// ValidateAccessGrant validates an access grant
func ValidateAccessGrant(grant *models.AccessGrant) error {
    // Check required fields
    if grant.ResourceID == "" {
        return fmt.Errorf("resource ID is required")
    }
    if grant.GrantorID == "" {
        return fmt.Errorf("grantor ID is required")
    }
    if grant.GranteeID == "" {
        return fmt.Errorf("grantee ID is required")
    }
    if len(grant.Permissions) == 0 {
        return fmt.Errorf("at least one permission is required")
    }

    // Validate permissions
    validPermissions := []string{
        models.PermissionRead,
        models.PermissionWrite,
        models.PermissionDelete,
        models.PermissionGrant,
        models.PermissionRevoke,
        models.PermissionVerify,
        models.PermissionReadOwn,
        models.PermissionWriteOwn,
        models.PermissionGrantOwn,
        models.PermissionRevokeOwn,
    }
    for _, perm := range grant.Permissions {
        if !contains(validPermissions, perm) {
            return fmt.Errorf("invalid permission: %s", perm)
        }
    }

    // Validate expiration
    if grant.ExpiresAt.Before(grant.GrantedAt) {
        return fmt.Errorf("expiration time cannot be before granted time")
    }

    return nil
}

// ValidateVerificationRequest validates a verification request
func ValidateVerificationRequest(request *models.VerificationRequest) error {
    if request.RecordID == "" {
        return fmt.Errorf("record ID is required")
    }
    if request.RequesterID == "" {
        return fmt.Errorf("requester ID is required")
    }
    if request.VerifierID == "" {
        return fmt.Errorf("verifier ID is required")
    }
    return nil
}

// ValidateEmail validates an email address
func ValidateEmail(email string) bool {
    return emailRegex.MatchString(email)
}

// ValidateUUID validates a UUID string
func ValidateUUID(uuid string) bool {
    return uuidRegex.MatchString(uuid)
}

// contains checks if a string is in a slice
func contains(slice []string, item string) bool {
    for _, s := range slice {
        if s == item {
            return true
        }
    }
    return false
}

// SanitizeString removes potentially harmful characters
func SanitizeString(input string) string {
    // Remove control characters
    input = strings.TrimSpace(input)
    // Additional sanitization can be added here
    return input
}
