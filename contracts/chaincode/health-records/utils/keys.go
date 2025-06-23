package utils

import (
    "fmt"
    "strings"
)

// Key prefixes for different object types
const (
    PrefixRecord         = "RECORD"
    PrefixVerification   = "VERIFY"
    PrefixAccess         = "ACCESS"
    PrefixPolicy         = "POLICY"
    PrefixPatientRecords = "PATIENT~RECORDS"
    PrefixProviderRecords = "PROVIDER~RECORDS"
    PrefixRecordVerifications = "RECORD~VERIFICATIONS"
    PrefixUserGrants     = "USER~GRANTS"
)

// CreateRecordKey creates a composite key for a health record
func CreateRecordKey(recordType, patientID, recordID string) string {
    return fmt.Sprintf("%s~%s~%s~%s", PrefixRecord, recordType, patientID, recordID)
}

// CreateVerificationKey creates a composite key for a verification
func CreateVerificationKey(recordID, verificationID string) string {
    return fmt.Sprintf("%s~%s~%s", PrefixVerification, recordID, verificationID)
}

// CreateAccessKey creates a composite key for an access grant
func CreateAccessKey(resourceID, granteeID, grantID string) string {
    return fmt.Sprintf("%s~%s~%s~%s", PrefixAccess, resourceID, granteeID, grantID)
}

// CreatePolicyKey creates a composite key for an access policy
func CreatePolicyKey(resourceType, policyID string) string {
    return fmt.Sprintf("%s~%s~%s", PrefixPolicy, resourceType, policyID)
}

// CreatePatientRecordsKey creates a composite key for patient records index
func CreatePatientRecordsKey(patientID string) string {
    return fmt.Sprintf("%s~%s", PrefixPatientRecords, patientID)
}

// CreateProviderRecordsKey creates a composite key for provider records index
func CreateProviderRecordsKey(providerID string) string {
    return fmt.Sprintf("%s~%s", PrefixProviderRecords, providerID)
}

// CreateRecordVerificationsKey creates a composite key for record verifications index
func CreateRecordVerificationsKey(recordID string) string {
    return fmt.Sprintf("%s~%s", PrefixRecordVerifications, recordID)
}

// CreateUserGrantsKey creates a composite key for user grants index
func CreateUserGrantsKey(userID string) string {
    return fmt.Sprintf("%s~%s", PrefixUserGrants, userID)
}

// ParseRecordKey parses a record composite key
func ParseRecordKey(compositeKey string) (recordType, patientID, recordID string, err error) {
    parts := strings.Split(compositeKey, "~")
    if len(parts) != 4 || parts[0] != PrefixRecord {
        return "", "", "", fmt.Errorf("invalid record key format: %s", compositeKey)
    }
    return parts[1], parts[2], parts[3], nil
}

// ParseVerificationKey parses a verification composite key
func ParseVerificationKey(compositeKey string) (recordID, verificationID string, err error) {
    parts := strings.Split(compositeKey, "~")
    if len(parts) != 3 || parts[0] != PrefixVerification {
        return "", "", fmt.Errorf("invalid verification key format: %s", compositeKey)
    }
    return parts[1], parts[2], nil
}
