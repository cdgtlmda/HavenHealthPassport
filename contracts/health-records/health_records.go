package main

import (
    "encoding/json"
    "fmt"
    "time"

    "github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// HealthRecordContract provides functions for managing health records
type HealthRecordContract struct {
    contractapi.Contract
}

// HealthRecord describes basic details of a health record
type HealthRecord struct {
    ID              string    `json:"id"`
    PatientID       string    `json:"patient_id"`
    RecordType      string    `json:"record_type"`
    RecordHash      string    `json:"record_hash"`
    ProviderID      string    `json:"provider_id"`
    ProviderName    string    `json:"provider_name"`
    Timestamp       time.Time `json:"timestamp"`
    EncryptedDataCID string   `json:"encrypted_data_cid"` // IPFS CID for encrypted data
    Verified        bool      `json:"verified"`
    AccessList      []string  `json:"access_list"`
}

// InitLedger adds base health records to the ledger
func (s *HealthRecordContract) InitLedger(ctx contractapi.TransactionContextInterface) error {
    // Initialize with empty ledger
    return nil
}

// CreateHealthRecord creates a new health record on the ledger
func (s *HealthRecordContract) CreateHealthRecord(ctx contractapi.TransactionContextInterface, id string, patientID string, recordType string, recordHash string, providerID string, providerName string, encryptedDataCID string) error {
    exists, err := s.HealthRecordExists(ctx, id)
    if err != nil {
        return err
    }
    if exists {
        return fmt.Errorf("the health record %s already exists", id)
    }

    record := HealthRecord{
        ID:               id,
        PatientID:        patientID,
        RecordType:       recordType,
        RecordHash:       recordHash,
        ProviderID:       providerID,
        ProviderName:     providerName,
        Timestamp:        time.Now(),
        EncryptedDataCID: encryptedDataCID,
        Verified:         true,
        AccessList:       []string{patientID, providerID},
    }

    recordJSON, err := json.Marshal(record)
    if err != nil {
        return err
    }

    return ctx.GetStub().PutState(id, recordJSON)
}

// ReadHealthRecord returns the health record stored in the ledger with given id
func (s *HealthRecordContract) ReadHealthRecord(ctx contractapi.TransactionContextInterface, id string) (*HealthRecord, error) {
    recordJSON, err := ctx.GetStub().GetState(id)
    if err != nil {
        return nil, fmt.Errorf("failed to read from world state: %v", err)
    }
    if recordJSON == nil {
        return nil, fmt.Errorf("the health record %s does not exist", id)
    }

    var record HealthRecord
    err = json.Unmarshal(recordJSON, &record)
    if err != nil {
        return nil, err
    }

    return &record, nil
}

// HealthRecordExists returns true when health record with given ID exists in world state
func (s *HealthRecordContract) HealthRecordExists(ctx contractapi.TransactionContextInterface, id string) (bool, error) {
    recordJSON, err := ctx.GetStub().GetState(id)
    if err != nil {
        return false, fmt.Errorf("failed to read from world state: %v", err)
    }

    return recordJSON != nil, nil
}

// GetHealthRecordsByPatient queries for health records based on patient ID
func (s *HealthRecordContract) GetHealthRecordsByPatient(ctx contractapi.TransactionContextInterface, patientID string) ([]*HealthRecord, error) {
    queryString := fmt.Sprintf(`{"selector":{"patient_id":"%s"}}`, patientID)
    return s.getQueryResultForQueryString(ctx, queryString)
}

// GrantAccess adds a user to the access list of a health record
func (s *HealthRecordContract) GrantAccess(ctx contractapi.TransactionContextInterface, recordID string, userID string) error {
    record, err := s.ReadHealthRecord(ctx, recordID)
    if err != nil {
        return err
    }

    // Check if user already has access
    for _, user := range record.AccessList {
        if user == userID {
            return fmt.Errorf("user %s already has access to record %s", userID, recordID)
        }
    }

    record.AccessList = append(record.AccessList, userID)

    recordJSON, err := json.Marshal(record)
    if err != nil {
        return err
    }

    return ctx.GetStub().PutState(recordID, recordJSON)
}

// RevokeAccess removes a user from the access list of a health record
func (s *HealthRecordContract) RevokeAccess(ctx contractapi.TransactionContextInterface, recordID string, userID string) error {
    record, err := s.ReadHealthRecord(ctx, recordID)
    if err != nil {
        return err
    }

    // Remove user from access list
    newAccessList := []string{}
    for _, user := range record.AccessList {
        if user != userID {
            newAccessList = append(newAccessList, user)
        }
    }

    // Patient cannot be removed from their own record
    if userID == record.PatientID {
        return fmt.Errorf("cannot revoke patient's access to their own record")
    }

    record.AccessList = newAccessList

    recordJSON, err := json.Marshal(record)
    if err != nil {
        return err
    }

    return ctx.GetStub().PutState(recordID, recordJSON)
}

// getQueryResultForQueryString executes the passed in query string
func (s *HealthRecordContract) getQueryResultForQueryString(ctx contractapi.TransactionContextInterface, queryString string) ([]*HealthRecord, error) {
    resultsIterator, err := ctx.GetStub().GetQueryResult(queryString)
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
            return nil, err
        }
        records = append(records, &record)
    }

    return records, nil
}

// GetHealthRecordHistory returns the chain of custody for a health record
func (s *HealthRecordContract) GetHealthRecordHistory(ctx contractapi.TransactionContextInterface, recordID string) ([]HealthRecord, error) {
    resultsIterator, err := ctx.GetStub().GetHistoryForKey(recordID)
    if err != nil {
        return nil, err
    }
    defer resultsIterator.Close()

    var records []HealthRecord
    for resultsIterator.HasNext() {
        queryResponse, err := resultsIterator.Next()
        if err != nil {
            return nil, err
        }

        var record HealthRecord
        err = json.Unmarshal(queryResponse.Value, &record)
        if err != nil {
            return nil, err
        }
        records = append(records, record)
    }

    return records, nil
}