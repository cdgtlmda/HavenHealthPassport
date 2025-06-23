// Haven Health Passport - Health Record Verification Chaincode
// This chaincode manages health record verification on the blockchain
// for refugee healthcare data integrity

package main

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// SmartContract provides functions for managing health records
type SmartContract struct {
	contractapi.Contract
}

// HealthRecord represents a health record on the blockchain
type HealthRecord struct {
	RecordID         string    `json:"recordId"`
	PatientID        string    `json:"patientId"`
	Hash             string    `json:"hash"`
	RecordType       string    `json:"recordType"`
	Timestamp        time.Time `json:"timestamp"`
	VerifierOrg      string    `json:"verifierOrg"`
	Encrypted        bool      `json:"encrypted"`
	Version          int       `json:"version"`
	RecordCategory   string    `json:"recordCategory"`
	MetadataHash     string    `json:"metadataHash"`
	PreviousRecordID string    `json:"previousRecordId,omitempty"`
}

// VerificationEntry represents a verification event
type VerificationEntry struct {
	TransactionID    string    `json:"transactionId"`
	RecordID         string    `json:"recordId"`
	VerifierID       string    `json:"verifierId"`
	VerifierOrg      string    `json:"verifierOrg"`
	Timestamp        time.Time `json:"timestamp"`
	Status           string    `json:"status"`
	Hash             string    `json:"hash"`
	VerificationType string    `json:"verificationType"`
	PatientConsent   bool      `json:"patientConsent"`
	Metadata         string    `json:"metadata"`
}

// CrossBorderVerification represents cross-border access verification
type CrossBorderVerification struct {
	VerificationID    string    `json:"verificationId"`
	PatientID         string    `json:"patientId"`
	OriginCountry     string    `json:"originCountry"`
	DestinationCountry string   `json:"destinationCountry"`
	HealthRecords     []string  `json:"healthRecords"`
	Purpose           string    `json:"purpose"`
	ValidFrom         time.Time `json:"validFrom"`
	ValidUntil        time.Time `json:"validUntil"`
	Status            string    `json:"status"`
	RequestingOrg     string    `json:"requestingOrg"`
	ConsentProvided   bool      `json:"consentProvided"`
	DataMinimization  bool      `json:"dataMinimization"`
	EncryptionType    string    `json:"encryptionType"`
	Metadata          string    `json:"metadata"`
}

// InitLedger adds base health record data to the ledger
func (s *SmartContract) InitLedger(ctx contractapi.TransactionContextInterface) error {
	// Initialize with system health check record
	systemRecord := HealthRecord{
		RecordID:       "SYSTEM-001",
		PatientID:      "SYSTEM",
		Hash:           "0x0000000000000000000000000000000000000000000000000000000000000000",
		RecordType:     "system_check",
		Timestamp:      time.Now(),
		VerifierOrg:    "HavenHealthOrg",
		Encrypted:      false,
		Version:        1,
		RecordCategory: "system",
		MetadataHash:   "0x0000000000000000000000000000000000000000000000000000000000000000",
	}

	systemRecordJSON, err := json.Marshal(systemRecord)
	if err != nil {
		return err
	}

	return ctx.GetStub().PutState(systemRecord.RecordID, systemRecordJSON)
}

// CreateHealthRecord creates a new health record on the blockchain
func (s *SmartContract) CreateHealthRecord(ctx contractapi.TransactionContextInterface, recordData string) (string, error) {
	var record HealthRecord
	err := json.Unmarshal([]byte(recordData), &record)
	if err != nil {
		return "", fmt.Errorf("failed to unmarshal record data: %v", err)
	}

	// Check if record already exists
	existingRecord, err := ctx.GetStub().GetState(record.RecordID)
	if err != nil {
		return "", fmt.Errorf("failed to read from world state: %v", err)
	}
	if existingRecord != nil {
		return "", fmt.Errorf("record %s already exists", record.RecordID)
	}

	// Set timestamp
	record.Timestamp = time.Now()

	// Create composite key for patient records
	patientIndexKey, err := ctx.GetStub().CreateCompositeKey("patient~record", []string{record.PatientID, record.RecordID})
	if err != nil {
		return "", fmt.Errorf("failed to create composite key: %v", err)
	}

	// Store record
	recordJSON, err := json.Marshal(record)
	if err != nil {
		return "", fmt.Errorf("failed to marshal record: %v", err)
	}

	err = ctx.GetStub().PutState(record.RecordID, recordJSON)
	if err != nil {
		return "", fmt.Errorf("failed to put record to world state: %v", err)
	}

	// Store index
	err = ctx.GetStub().PutState(patientIndexKey, []byte{0x00})
	if err != nil {
		return "", fmt.Errorf("failed to put index to world state: %v", err)
	}

	// Get transaction ID
	txID := ctx.GetStub().GetTxID()

	// Emit event
	eventPayload := fmt.Sprintf(`{"recordId":"%s","patientId":"%s","txId":"%s"}`, 
		record.RecordID, record.PatientID, txID)
	ctx.GetStub().SetEvent("HealthRecordCreated", []byte(eventPayload))

	return txID, nil
}

// QueryHealthRecord returns the health record with given ID
func (s *SmartContract) QueryHealthRecord(ctx contractapi.TransactionContextInterface, recordID string) (*HealthRecord, error) {
	recordJSON, err := ctx.GetStub().GetState(recordID)
	if err != nil {
		return nil, fmt.Errorf("failed to read from world state: %v", err)
	}
	if recordJSON == nil {
		return nil, fmt.Errorf("record %s does not exist", recordID)
	}

	var record HealthRecord
	err = json.Unmarshal(recordJSON, &record)
	if err != nil {
		return nil, err
	}

	return &record, nil
}

// RecordVerification records a verification event for a health record
func (s *SmartContract) RecordVerification(ctx contractapi.TransactionContextInterface,
	recordID, verificationHash, verifierID, status, metadata string) (string, error) {
	
	// Verify record exists
	recordJSON, err := ctx.GetStub().GetState(recordID)
	if err != nil {
		return "", fmt.Errorf("failed to read record: %v", err)
	}
	if recordJSON == nil {
		return "", fmt.Errorf("record %s does not exist", recordID)
	}

	// Parse metadata to get additional info
	var metadataMap map[string]interface{}
	err = json.Unmarshal([]byte(metadata), &metadataMap)
	if err != nil {
		return "", fmt.Errorf("failed to parse metadata: %v", err)
	}

	// Create verification entry
	verification := VerificationEntry{
		TransactionID:    ctx.GetStub().GetTxID(),
		RecordID:         recordID,
		VerifierID:       verifierID,
		VerifierOrg:      metadataMap["verifier_org"].(string),
		Timestamp:        time.Now(),
		Status:           status,
		Hash:             verificationHash,
		VerificationType: metadataMap["verification_type"].(string),
		PatientConsent:   metadataMap["patient_consent"].(bool),
		Metadata:         metadata,
	}

	// Store verification with composite key
	verificationKey := fmt.Sprintf("verification~%s~%s", recordID, verification.TransactionID)
	verificationJSON, err := json.Marshal(verification)
	if err != nil {
		return "", fmt.Errorf("failed to marshal verification: %v", err)
	}

	err = ctx.GetStub().PutState(verificationKey, verificationJSON)
	if err != nil {
		return "", fmt.Errorf("failed to store verification: %v", err)
	}

	// Emit event
	eventPayload := fmt.Sprintf(`{"recordId":"%s","status":"%s","txId":"%s"}`,
		recordID, status, verification.TransactionID)
	ctx.GetStub().SetEvent("VerificationRecorded", []byte(eventPayload))

	return verification.TransactionID, nil
}

// GetVerificationHistory returns all verification events for a record
func (s *SmartContract) GetVerificationHistory(ctx contractapi.TransactionContextInterface, recordID string) ([]*VerificationEntry, error) {
	// Query all verifications for this record
	startKey := fmt.Sprintf("verification~%s~", recordID)
	endKey := fmt.Sprintf("verification~%s~zzzzzzz", recordID)

	resultsIterator, err := ctx.GetStub().GetStateByRange(startKey, endKey)
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

// CreateCrossBorderVerification creates a cross-border access verification
func (s *SmartContract) CreateCrossBorderVerification(ctx contractapi.TransactionContextInterface, verificationData string) (string, error) {
	var verification CrossBorderVerification
	err := json.Unmarshal([]byte(verificationData), &verification)
	if err != nil {
		return "", fmt.Errorf("failed to unmarshal verification data: %v", err)
	}

	// Store cross-border verification
	verificationJSON, err := json.Marshal(verification)
	if err != nil {
		return "", fmt.Errorf("failed to marshal verification: %v", err)
	}

	err = ctx.GetStub().PutState(verification.VerificationID, verificationJSON)
	if err != nil {
		return "", fmt.Errorf("failed to store cross-border verification: %v", err)
	}

	// Create composite keys for queries
	patientKey, _ := ctx.GetStub().CreateCompositeKey("patient~cbv", []string{verification.PatientID, verification.VerificationID})
	countryKey, _ := ctx.GetStub().CreateCompositeKey("country~cbv", []string{verification.DestinationCountry, verification.VerificationID})

	ctx.GetStub().PutState(patientKey, []byte{0x00})
	ctx.GetStub().PutState(countryKey, []byte{0x00})

	// Emit event
	txID := ctx.GetStub().GetTxID()
	eventPayload := fmt.Sprintf(`{"verificationId":"%s","patientId":"%s","destination":"%s","txId":"%s"}`,
		verification.VerificationID, verification.PatientID, verification.DestinationCountry, txID)
	ctx.GetStub().SetEvent("CrossBorderVerificationCreated", []byte(eventPayload))

	return txID, nil
}

// GetPatientRecords returns all records for a patient
func (s *SmartContract) GetPatientRecords(ctx contractapi.TransactionContextInterface, patientID string) ([]*HealthRecord, error) {
	// Query using composite key
	resultsIterator, err := ctx.GetStub().GetStateByPartialCompositeKey("patient~record", []string{patientID})
	if err != nil {
		return nil, fmt.Errorf("failed to get patient records: %v", err)
	}
	defer resultsIterator.Close()

	var records []*HealthRecord
	for resultsIterator.HasNext() {
		queryResponse, err := resultsIterator.Next()
		if err != nil {
			return nil, err
		}

		// Extract record ID from composite key
		_, compositeKeyParts, err := ctx.GetStub().SplitCompositeKey(queryResponse.Key)
		if err != nil {
			return nil, err
		}

		if len(compositeKeyParts) >= 2 {
			recordID := compositeKeyParts[1]
			
			// Get the actual record
			record, err := s.QueryHealthRecord(ctx, recordID)
			if err != nil {
				continue // Skip if record not found
			}
			
			records = append(records, record)
		}
	}

	return records, nil
}

// UpdateRecordHash updates the hash of an existing record (for versioning)
func (s *SmartContract) UpdateRecordHash(ctx contractapi.TransactionContextInterface, 
	recordID, newHash, previousRecordID string) error {
	
	// Get existing record
	record, err := s.QueryHealthRecord(ctx, recordID)
	if err != nil {
		return err
	}

	// Create new version
	newRecord := *record
	newRecord.Hash = newHash
	newRecord.Version = record.Version + 1
	newRecord.PreviousRecordID = previousRecordID
	newRecord.Timestamp = time.Now()

	// Store updated record
	recordJSON, err := json.Marshal(newRecord)
	if err != nil {
		return fmt.Errorf("failed to marshal updated record: %v", err)
	}

	err = ctx.GetStub().PutState(recordID, recordJSON)
	if err != nil {
		return fmt.Errorf("failed to update record: %v", err)
	}

	// Emit event
	eventPayload := fmt.Sprintf(`{"recordId":"%s","version":%d,"previousId":"%s"}`,
		recordID, newRecord.Version, previousRecordID)
	ctx.GetStub().SetEvent("RecordUpdated", []byte(eventPayload))

	return nil
}

// GetRecordsByTimeRange returns records created within a time range
func (s *SmartContract) GetRecordsByTimeRange(ctx contractapi.TransactionContextInterface,
	startTime, endTime string) ([]*HealthRecord, error) {
	
	start, err := time.Parse(time.RFC3339, startTime)
	if err != nil {
		return nil, fmt.Errorf("invalid start time format: %v", err)
	}
	
	end, err := time.Parse(time.RFC3339, endTime)
	if err != nil {
		return nil, fmt.Errorf("invalid end time format: %v", err)
	}

	// This would need an index in production
	// For now, scan all records (not efficient for large datasets)
	resultsIterator, err := ctx.GetStub().GetStateByRange("", "")
	if err != nil {
		return nil, err
	}
	defer resultsIterator.Close()

	var records []*HealthRecord
	for resultsIterator.HasNext() {
		queryResponse, err := resultsIterator.Next()
		if err != nil {
			return nil, err
		}

		var record HealthRecord
		err = json.Unmarshal(queryResponse.Value, &record)
		if err != nil {
			continue // Skip non-record entries
		}

		// Check if record is within time range
		if record.Timestamp.After(start) && record.Timestamp.Before(end) {
			records = append(records, &record)
		}
	}

	return records, nil
}

// main function starts up the chaincode
func main() {
	chaincode, err := contractapi.NewChaincode(&SmartContract{})
	if err != nil {
		fmt.Printf("Error creating health record chaincode: %v", err)
		return
	}

	if err := chaincode.Start(); err != nil {
		fmt.Printf("Error starting health record chaincode: %v", err)
	}
}
