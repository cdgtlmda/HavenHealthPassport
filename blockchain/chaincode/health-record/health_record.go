package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// HealthRecordContract manages health records on the blockchain
type HealthRecordContract struct {
	contractapi.Contract
}

// HealthRecord represents a health record stored on blockchain
type HealthRecord struct {
	RecordID         string            `json:"recordId"`
	PatientID        string            `json:"patientId"`
	RecordType       string            `json:"recordType"`
	Hash             string            `json:"hash"`
	Timestamp        string            `json:"timestamp"`
	VerifierOrg      string            `json:"verifierOrg"`
	Status           string            `json:"status"`
	Metadata         map[string]string `json:"metadata"`
	EncryptionType   string            `json:"encryptionType"`
	ComplianceFlags  []string          `json:"complianceFlags"`
}

// VerificationEntry represents a verification event
type VerificationEntry struct {
	TransactionID    string            `json:"transactionId"`
	RecordID         string            `json:"recordId"`
	VerifierID       string            `json:"verifierId"`
	VerifierOrg      string            `json:"verifierOrg"`
	Timestamp        string            `json:"timestamp"`
	Status           string            `json:"status"`
	Hash             string            `json:"hash"`
	VerificationType string            `json:"verificationType"`
	Metadata         map[string]string `json:"metadata"`
}

// InitLedger initializes the ledger with test data
func (s *HealthRecordContract) InitLedger(ctx contractapi.TransactionContextInterface) error {
	// Initialize with compliance check
	complianceCheck := map[string]string{
		"initialized": "true",
		"version":     "1.0",
		"compliance":  "HIPAA,GDPR",
		"timestamp":   time.Now().UTC().Format(time.RFC3339),
	}
	
	complianceJSON, err := json.Marshal(complianceCheck)
	if err != nil {
		return err
	}
	
	return ctx.GetStub().PutState("COMPLIANCE_CHECK", complianceJSON)
}

// CreateHealthRecord creates a new health record entry
func (s *HealthRecordContract) CreateHealthRecord(ctx contractapi.TransactionContextInterface, recordDataJSON string) error {
	var recordData map[string]interface{}
	err := json.Unmarshal([]byte(recordDataJSON), &recordData)
	if err != nil {
		return fmt.Errorf("failed to unmarshal record data: %v", err)
	}
	
	// Validate required fields
	recordID, ok := recordData["recordId"].(string)
	if !ok || recordID == "" {
		return fmt.Errorf("recordId is required")
	}
	
	hash, ok := recordData["hash"].(string)
	if !ok || hash == "" {
		return fmt.Errorf("hash is required")
	}
	
	// Create health record
	healthRecord := HealthRecord{
		RecordID:    recordID,
		PatientID:   getStringValue(recordData, "patientId"),
		RecordType:  getStringValue(recordData, "recordType"),
		Hash:        hash,
		Timestamp:   time.Now().UTC().Format(time.RFC3339),
		VerifierOrg: getStringValue(recordData, "verifierOrg"),
		Status:      "created",
		Metadata:    extractMetadata(recordData),
		EncryptionType: "AES-256",
		ComplianceFlags: []string{"HIPAA", "GDPR"},
	}
	
	// Check if record already exists
	existingRecord, err := ctx.GetStub().GetState(recordID)
	if err != nil {
		return fmt.Errorf("failed to check existing record: %v", err)
	}
	if existingRecord != nil {
		return fmt.Errorf("record %s already exists", recordID)
	}
	
	// Store the record
	recordJSON, err := json.Marshal(healthRecord)
	if err != nil {
		return err
	}
	
	err = ctx.GetStub().PutState(recordID, recordJSON)
	if err != nil {
		return fmt.Errorf("failed to store record: %v", err)
	}
	
	// Emit event for record creation
	eventPayload := map[string]string{
		"recordId":   recordID,
		"patientId":  healthRecord.PatientID,
		"action":     "created",
		"timestamp":  healthRecord.Timestamp,
	}
	eventJSON, _ := json.Marshal(eventPayload)
	ctx.GetStub().SetEvent("HealthRecordCreated", eventJSON)
	
	return nil
}

// QueryHealthRecord retrieves a health record by ID
func (s *HealthRecordContract) QueryHealthRecord(ctx contractapi.TransactionContextInterface, recordID string) (*HealthRecord, error) {
	if recordID == "" {
		return nil, fmt.Errorf("recordId cannot be empty")
	}
	
	recordJSON, err := ctx.GetStub().GetState(recordID)
	if err != nil {
		return nil, fmt.Errorf("failed to read record: %v", err)
	}
	if recordJSON == nil {
		return nil, fmt.Errorf("record %s does not exist", recordID)
	}
	
	var healthRecord HealthRecord
	err = json.Unmarshal(recordJSON, &healthRecord)
	if err != nil {
		return nil, err
	}
	
	return &healthRecord, nil
}

// RecordVerification records a verification attempt
func (s *HealthRecordContract) RecordVerification(ctx contractapi.TransactionContextInterface, 
	recordID string, hash string, verifierID string, status string, metadataJSON string) error {
	
	// Validate inputs
	if recordID == "" || hash == "" || verifierID == "" || status == "" {
		return fmt.Errorf("recordID, hash, verifierID, and status are required")
	}
	
	// Parse metadata
	var metadata map[string]string
	if metadataJSON != "" {
		err := json.Unmarshal([]byte(metadataJSON), &metadata)
		if err != nil {
			return fmt.Errorf("invalid metadata JSON: %v", err)
		}
	}
	
	// Create verification entry
	txID := ctx.GetStub().GetTxID()
	verification := VerificationEntry{
		TransactionID:    txID,
		RecordID:         recordID,
		VerifierID:       verifierID,
		VerifierOrg:      metadata["verifier_org"],
		Timestamp:        time.Now().UTC().Format(time.RFC3339),
		Status:           status,
		Hash:             hash,
		VerificationType: metadata["verification_type"],
		Metadata:         metadata,
	}
	
	// Store verification with composite key
	verificationKey, err := ctx.GetStub().CreateCompositeKey("verification", []string{recordID, txID})
	if err != nil {
		return fmt.Errorf("failed to create composite key: %v", err)
	}
	
	verificationJSON, err := json.Marshal(verification)
	if err != nil {
		return err
	}
	
	err = ctx.GetStub().PutState(verificationKey, verificationJSON)
	if err != nil {
		return fmt.Errorf("failed to store verification: %v", err)
	}
	
	// Update record status if verification successful
	if status == "verified" {
		record, err := s.QueryHealthRecord(ctx, recordID)
		if err == nil && record != nil {
			record.Status = "verified"
			recordJSON, _ := json.Marshal(record)
			ctx.GetStub().PutState(recordID, recordJSON)
		}
	}
	
	// Emit verification event
	eventPayload := map[string]string{
		"recordId":      recordID,
		"transactionId": txID,
		"status":        status,
		"timestamp":     verification.Timestamp,
	}
	eventJSON, _ := json.Marshal(eventPayload)
	ctx.GetStub().SetEvent("VerificationRecorded", eventJSON)
	
	return nil
}

// GetVerificationHistory retrieves all verifications for a record
func (s *HealthRecordContract) GetVerificationHistory(ctx contractapi.TransactionContextInterface, recordID string) ([]*VerificationEntry, error) {
	if recordID == "" {
		return nil, fmt.Errorf("recordId cannot be empty")
	}
	
	// Query all verifications for this record
	resultsIterator, err := ctx.GetStub().GetStateByPartialCompositeKey("verification", []string{recordID})
	if err != nil {
		return nil, fmt.Errorf("failed to get verification history: %v", err)
	}
	defer resultsIterator.Close()
	
	var verifications []*VerificationEntry
	for resultsIterator.HasNext() {
		queryResponse, err := resultsIterator.Next()
		if err != nil {
			return nil, err
		}
		
		var verification VerificationEntry
		err = json.Unmarshal(queryResponse.Value, &verification)
		if err != nil {
			return nil, err
		}
		
		verifications = append(verifications, &verification)
	}
	
	return verifications, nil
}

// UpdateHealthRecord updates an existing health record
func (s *HealthRecordContract) UpdateHealthRecord(ctx contractapi.TransactionContextInterface, 
	recordID string, updateDataJSON string) error {
	
	// Get existing record
	existingRecord, err := s.QueryHealthRecord(ctx, recordID)
	if err != nil {
		return err
	}
	
	// Parse update data
	var updateData map[string]interface{}
	err = json.Unmarshal([]byte(updateDataJSON), &updateData)
	if err != nil {
		return fmt.Errorf("failed to unmarshal update data: %v", err)
	}
	
	// Update allowed fields only
	if newHash, ok := updateData["hash"].(string); ok && newHash != "" {
		existingRecord.Hash = newHash
	}
	if newStatus, ok := updateData["status"].(string); ok && newStatus != "" {
		existingRecord.Status = newStatus
	}
	
	// Update metadata
	if newMetadata, ok := updateData["metadata"].(map[string]interface{}); ok {
		for k, v := range newMetadata {
			if strVal, ok := v.(string); ok {
				existingRecord.Metadata[k] = strVal
			}
		}
	}
	
	// Update timestamp
	existingRecord.Timestamp = time.Now().UTC().Format(time.RFC3339)
	
	// Store updated record
	recordJSON, err := json.Marshal(existingRecord)
	if err != nil {
		return err
	}
	
	return ctx.GetStub().PutState(recordID, recordJSON)
}

// Helper functions
func getStringValue(data map[string]interface{}, key string) string {
	if val, ok := data[key].(string); ok {
		return val
	}
	return ""
}

func extractMetadata(data map[string]interface{}) map[string]string {
	metadata := make(map[string]string)
	if meta, ok := data["metadata"].(map[string]interface{}); ok {
		for k, v := range meta {
			if strVal, ok := v.(string); ok {
				metadata[k] = strVal
			}
		}
	}
	return metadata
}

// CalculateHash generates SHA-256 hash of data
func CalculateHash(data string) string {
	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:])
}

func main() {
	chaincode, err := contractapi.NewChaincode(&HealthRecordContract{})
	if err != nil {
		fmt.Printf("Error creating health record chaincode: %v\n", err)
		return
	}

	if err := chaincode.Start(); err != nil {
		fmt.Printf("Error starting health record chaincode: %v\n", err)
	}
}
