package contracts

import (
    "encoding/json"
    "fmt"
    "time"

    "github.com/haven-health-passport/chaincode/health-records/models"
    "github.com/haven-health-passport/chaincode/health-records/utils"
    "github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// HealthRecordContract provides functions for managing health records
type HealthRecordContract struct {
    contractapi.Contract
}

// InitLedger initializes the ledger with default data
func (hrc *HealthRecordContract) InitLedger(ctx contractapi.TransactionContextInterface) error {
    // Initialize default access policies
    policies := []models.AccessPolicy{
        {
            PolicyID:     "DEFAULT_PATIENT_POLICY",
            PolicyName:   "Default Patient Access Policy",
            ResourceType: "health_record",
            Rules: []models.AccessRule{
                {
                    RuleID:  "RULE001",
                    Role:    models.RolePatient,
                    Actions: []string{models.PermissionReadOwn, models.PermissionGrantOwn},
                },
                {
                    RuleID:  "RULE002",
                    Role:    models.RoleProvider,
                    Actions: []string{models.PermissionRead, models.PermissionWrite},
                },
            },
            CreatedBy: "SYSTEM",
            CreatedAt: time.Now(),
            Active:    true,
            ObjectType: "accessPolicy",
        },
        {
            PolicyID:     "EMERGENCY_ACCESS_POLICY",
            PolicyName:   "Emergency Access Policy",
            ResourceType: "health_record",
            Rules: []models.AccessRule{
                {
                    RuleID:   "EMRG001",
                    Role:     models.RoleEmergency,
                    Actions:  []string{models.PermissionRead},
                    Duration: "1h",
                },
            },
            CreatedBy: "SYSTEM",
            CreatedAt: time.Now(),
            Active:    true,
            ObjectType: "accessPolicy",
        },
    }

    // Store policies in the ledger
    for _, policy := range policies {
        policyKey := utils.CreatePolicyKey(policy.ResourceType, policy.PolicyID)
        policyJSON, err := json.Marshal(policy)
        if err != nil {
            return fmt.Errorf("failed to marshal policy: %v", err)
        }

        err = ctx.GetStub().PutState(policyKey, policyJSON)
        if err != nil {
            return fmt.Errorf("failed to put policy to world state: %v", err)
        }
    }

    return nil
}

// CreateRecord creates a new health record
func (hrc *HealthRecordContract) CreateRecord(
    ctx contractapi.TransactionContextInterface,
    patientID string,
    providerID string,
    recordType string,
    encryptedData string,
    dataHash string,
    metadata string,
) error {
    // Generate record ID
    recordID, err := utils.GenerateRecordID()
    if err != nil {
        return fmt.Errorf("failed to generate record ID: %v", err)
    }

    // Create new health record
    record := models.NewHealthRecord(patientID, providerID, recordType)
    record.RecordID = recordID
    record.EncryptedData = encryptedData
    record.DataHash = dataHash

    // Parse metadata if provided
    if metadata != "" {
        var metadataMap map[string]interface{}
        err = json.Unmarshal([]byte(metadata), &metadataMap)
        if err != nil {
            return fmt.Errorf("failed to parse metadata: %v", err)
        }
        record.Metadata = metadataMap
    }

    // Validate record
    err = utils.ValidateHealthRecord(record)
    if err != nil {
        return fmt.Errorf("validation failed: %v", err)
    }

    // Create composite key
    recordKey := utils.CreateRecordKey(recordType, patientID, recordID)

    // Marshal record to JSON
    recordJSON, err := json.Marshal(record)
    if err != nil {
        return fmt.Errorf("failed to marshal record: %v", err)
    }

    // Store record in world state
    err = ctx.GetStub().PutState(recordKey, recordJSON)
    if err != nil {
        return fmt.Errorf("failed to put record to world state: %v", err)
    }

    // Create indexes for efficient querying
    // Patient index
    patientIndexKey, err := ctx.GetStub().CreateCompositeKey(
        utils.PrefixPatientRecords,
        []string{patientID, recordID},
    )
    if err != nil {
        return fmt.Errorf("failed to create patient index: %v", err)
    }
    err = ctx.GetStub().PutState(patientIndexKey, []byte{0x00})
    if err != nil {
        return fmt.Errorf("failed to put patient index: %v", err)
    }

    // Provider index
    providerIndexKey, err := ctx.GetStub().CreateCompositeKey(
        utils.PrefixProviderRecords,
        []string{providerID, recordID},
    )
    if err != nil {
        return fmt.Errorf("failed to create provider index: %v", err)
    }
    err = ctx.GetStub().PutState(providerIndexKey, []byte{0x00})
    if err != nil {
        return fmt.Errorf("failed to put provider index: %v", err)
    }

    // Emit event
    event := map[string]interface{}{
        "eventType": "RECORD_CREATED",
        "recordId":  recordID,
        "patientId": patientID,
        "providerId": providerID,
        "recordType": recordType,
        "timestamp": time.Now().Format(time.RFC3339),
    }
    eventJSON, _ := json.Marshal(event)
    err = ctx.GetStub().SetEvent("RecordCreated", eventJSON)
    if err != nil {
        return fmt.Errorf("failed to emit event: %v", err)
    }

    return nil
}

// UpdateRecord updates an existing health record (creates new version)
func (hrc *HealthRecordContract) UpdateRecord(
    ctx contractapi.TransactionContextInterface,
    recordID string,
    patientID string,
    recordType string,
    updates string,
) error {
    // Get existing record
    existingRecord, err := hrc.ReadRecord(ctx, recordID, patientID, recordType)
    if err != nil {
        return fmt.Errorf("failed to read existing record: %v", err)
    }

    // Check if record is active
    if existingRecord.Status != models.StatusActive {
        return fmt.Errorf("cannot update record with status: %s", existingRecord.Status)
    }

    // Parse updates
    var updateMap map[string]interface{}
    err = json.Unmarshal([]byte(updates), &updateMap)
    if err != nil {
        return fmt.Errorf("failed to parse updates: %v", err)
    }

    // Create new version
    newRecord := *existingRecord
    newRecord.Version++
    newRecord.UpdatedAt = time.Now()

    // Apply updates
    if encData, ok := updateMap["encryptedData"].(string); ok {
        newRecord.EncryptedData = encData
    }
    if hash, ok := updateMap["dataHash"].(string); ok {
        newRecord.DataHash = hash
    }
    if meta, ok := updateMap["metadata"].(map[string]interface{}); ok {
        for k, v := range meta {
            newRecord.Metadata[k] = v
        }
    }

    // Validate updated record
    err = utils.ValidateHealthRecord(&newRecord)
    if err != nil {
        return fmt.Errorf("validation failed: %v", err)
    }

    // Store updated record
    recordKey := utils.CreateRecordKey(recordType, patientID, recordID)
    recordJSON, err := json.Marshal(newRecord)
    if err != nil {
        return fmt.Errorf("failed to marshal record: %v", err)
    }

    err = ctx.GetStub().PutState(recordKey, recordJSON)
    if err != nil {
        return fmt.Errorf("failed to update record: %v", err)
    }

    // Emit event
    event := map[string]interface{}{
        "eventType": "RECORD_UPDATED",
        "recordId":  recordID,
        "version":   newRecord.Version,
        "timestamp": time.Now().Format(time.RFC3339),
    }
    eventJSON, _ := json.Marshal(event)
    ctx.GetStub().SetEvent("RecordUpdated", eventJSON)

    return nil
}

// ReadRecord reads a health record from the ledger
func (hrc *HealthRecordContract) ReadRecord(
    ctx contractapi.TransactionContextInterface,
    recordID string,
    patientID string,
    recordType string,
) (*models.HealthRecord, error) {
    // Create composite key
    recordKey := utils.CreateRecordKey(recordType, patientID, recordID)

    // Get record from world state
    recordJSON, err := ctx.GetStub().GetState(recordKey)
    if err != nil {
        return nil, fmt.Errorf("failed to read record: %v", err)
    }
    if recordJSON == nil {
        return nil, fmt.Errorf("record not found: %s", recordID)
    }

    // Unmarshal record
    var record models.HealthRecord
    err = json.Unmarshal(recordJSON, &record)
    if err != nil {
        return nil, fmt.Errorf("failed to unmarshal record: %v", err)
    }

    // Log access event
    event := map[string]interface{}{
        "eventType": "RECORD_ACCESSED",
        "recordId":  recordID,
        "accessedBy": ctx.GetClientIdentity().GetID(),
        "timestamp": time.Now().Format(time.RFC3339),
    }
    eventJSON, _ := json.Marshal(event)
    ctx.GetStub().SetEvent("RecordAccessed", eventJSON)

    return &record, nil
}

// DeleteRecord soft deletes a health record
func (hrc *HealthRecordContract) DeleteRecord(
    ctx contractapi.TransactionContextInterface,
    recordID string,
    patientID string,
    recordType string,
    reason string,
) error {
    // Get existing record
    record, err := hrc.ReadRecord(ctx, recordID, patientID, recordType)
    if err != nil {
        return fmt.Errorf("failed to read record: %v", err)
    }

    // Check if already deleted
    if record.Status == models.StatusDeleted {
        return fmt.Errorf("record is already deleted")
    }

    // Update status to deleted
    record.Status = models.StatusDeleted
    record.UpdatedAt = time.Now()
    record.Metadata["deletionReason"] = reason
    record.Metadata["deletedAt"] = time.Now().Format(time.RFC3339)
    record.Metadata["deletedBy"] = ctx.GetClientIdentity().GetID()

    // Store updated record
    recordKey := utils.CreateRecordKey(recordType, patientID, recordID)
    recordJSON, err := json.Marshal(record)
    if err != nil {
        return fmt.Errorf("failed to marshal record: %v", err)
    }

    err = ctx.GetStub().PutState(recordKey, recordJSON)
    if err != nil {
        return fmt.Errorf("failed to update record: %v", err)
    }

    // Emit event
    event := map[string]interface{}{
        "eventType": "RECORD_DELETED",
        "recordId":  recordID,
        "reason":    reason,
        "timestamp": time.Now().Format(time.RFC3339),
    }
    eventJSON, _ := json.Marshal(event)
    ctx.GetStub().SetEvent("RecordDeleted", eventJSON)

    return nil
}

// QueryRecordsByPatient queries all records for a specific patient
func (hrc *HealthRecordContract) QueryRecordsByPatient(
    ctx contractapi.TransactionContextInterface,
    patientID string,
) ([]*models.HealthRecord, error) {
    // Create iterator for patient records
    resultsIterator, err := ctx.GetStub().GetStateByPartialCompositeKey(
        utils.PrefixPatientRecords,
        []string{patientID},
    )
    if err != nil {
        return nil, fmt.Errorf("failed to get patient records: %v", err)
    }
    defer resultsIterator.Close()

    var records []*models.HealthRecord

    // Iterate through results
    for resultsIterator.HasNext() {
        queryResponse, err := resultsIterator.Next()
        if err != nil {
            return nil, fmt.Errorf("failed to iterate: %v", err)
        }

        // Extract record ID from composite key
        _, compositeKeyParts, err := ctx.GetStub().SplitCompositeKey(queryResponse.Key)
        if err != nil {
            return nil, fmt.Errorf("failed to split composite key: %v", err)
        }

        if len(compositeKeyParts) >= 2 {
            recordID := compositeKeyParts[1]

            // Query each record type to find the record
            recordTypes := []string{
                models.RecordTypeMedicalHistory,
                models.RecordTypePrescription,
                models.RecordTypeLabResult,
                models.RecordTypeImaging,
                models.RecordTypeVaccination,
                models.RecordTypeConsultation,
            }

            for _, recordType := range recordTypes {
                record, err := hrc.ReadRecord(ctx, recordID, patientID, recordType)
                if err == nil && record.Status == models.StatusActive {
                    records = append(records, record)
                    break
                }
            }
        }
    }

    return records, nil
}

// QueryRecordsByProvider queries all records created by a specific provider
func (hrc *HealthRecordContract) QueryRecordsByProvider(
    ctx contractapi.TransactionContextInterface,
    providerID string,
) ([]*models.HealthRecord, error) {
    // Create iterator for provider records
    resultsIterator, err := ctx.GetStub().GetStateByPartialCompositeKey(
        utils.PrefixProviderRecords,
        []string{providerID},
    )
    if err != nil {
        return nil, fmt.Errorf("failed to get provider records: %v", err)
    }
    defer resultsIterator.Close()

    var records []*models.HealthRecord
    recordMap := make(map[string]bool) // To avoid duplicates

    // Iterate through results
    for resultsIterator.HasNext() {
        queryResponse, err := resultsIterator.Next()
        if err != nil {
            return nil, fmt.Errorf("failed to iterate: %v", err)
        }

        // Extract record ID from composite key
        _, compositeKeyParts, err := ctx.GetStub().SplitCompositeKey(queryResponse.Key)
        if err != nil {
            continue
        }

        if len(compositeKeyParts) >= 2 {
            recordID := compositeKeyParts[1]

            // Skip if already processed
            if recordMap[recordID] {
                continue
            }

            // Use rich query to find the record
            queryString := fmt.Sprintf(`{
                "selector": {
                    "recordId": "%s",
                    "providerId": "%s",
                    "objectType": "healthRecord"
                }
            }`, recordID, providerID)

            resultsIterator2, err := ctx.GetStub().GetQueryResult(queryString)
            if err != nil {
                continue
            }
            defer resultsIterator2.Close()

            if resultsIterator2.HasNext() {
                queryResponse2, err := resultsIterator2.Next()
                if err == nil {
                    var record models.HealthRecord
                    err = json.Unmarshal(queryResponse2.Value, &record)
                    if err == nil && record.Status == models.StatusActive {
                        records = append(records, &record)
                        recordMap[recordID] = true
                    }
                }
            }
        }
    }

    return records, nil
}

// QueryRecordHistory queries the history of a specific record
func (hrc *HealthRecordContract) QueryRecordHistory(
    ctx contractapi.TransactionContextInterface,
    recordID string,
    patientID string,
    recordType string,
) ([]*models.HistoryRecord, error) {
    recordKey := utils.CreateRecordKey(recordType, patientID, recordID)

    resultsIterator, err := ctx.GetStub().GetHistoryForKey(recordKey)
    if err != nil {
        return nil, fmt.Errorf("failed to get record history: %v", err)
    }
    defer resultsIterator.Close()

    var history []*models.HistoryRecord

    for resultsIterator.HasNext() {
        queryResponse, err := resultsIterator.Next()
        if err != nil {
            return nil, fmt.Errorf("failed to iterate history: %v", err)
        }

        var record models.HealthRecord
        if queryResponse.Value != nil {
            err = json.Unmarshal(queryResponse.Value, &record)
            if err != nil {
                return nil, fmt.Errorf("failed to unmarshal record: %v", err)
            }
        }

        historyRecord := &models.HistoryRecord{
            TxID:      queryResponse.TxId,
            Value:     record,
            Timestamp: time.Unix(queryResponse.Timestamp.Seconds, int64(queryResponse.Timestamp.Nanos)),
            IsDelete:  queryResponse.IsDelete,
        }

        history = append(history, historyRecord)
    }

    return history, nil
}

// CreateRecordsBatch creates multiple health records in a single transaction
func (hrc *HealthRecordContract) CreateRecordsBatch(
    ctx contractapi.TransactionContextInterface,
    recordsJSON string,
) error {
    var records []models.HealthRecord
    err := json.Unmarshal([]byte(recordsJSON), &records)
    if err != nil {
        return fmt.Errorf("failed to unmarshal records: %v", err)
    }

    for i, record := range records {
        // Generate record ID if not provided
        if record.RecordID == "" {
            recordID, err := utils.GenerateRecordID()
            if err != nil {
                return fmt.Errorf("failed to generate record ID for record %d: %v", i, err)
            }
            record.RecordID = recordID
        }

        // Validate record
        err = utils.ValidateHealthRecord(&record)
        if err != nil {
            return fmt.Errorf("validation failed for record %d: %v", i, err)
        }

        // Store record
        recordKey := utils.CreateRecordKey(record.RecordType, record.PatientID, record.RecordID)
        recordJSON, err := json.Marshal(record)
        if err != nil {
            return fmt.Errorf("failed to marshal record %d: %v", i, err)
        }

        err = ctx.GetStub().PutState(recordKey, recordJSON)
        if err != nil {
            return fmt.Errorf("failed to store record %d: %v", i, err)
        }

        // Create indexes
        patientIndexKey, _ := ctx.GetStub().CreateCompositeKey(
            utils.PrefixPatientRecords,
            []string{record.PatientID, record.RecordID},
        )
        ctx.GetStub().PutState(patientIndexKey, []byte{0x00})

        providerIndexKey, _ := ctx.GetStub().CreateCompositeKey(
            utils.PrefixProviderRecords,
            []string{record.ProviderID, record.RecordID},
        )
        ctx.GetStub().PutState(providerIndexKey, []byte{0x00})
    }

    // Emit batch event
    event := map[string]interface{}{
        "eventType": "RECORDS_BATCH_CREATED",
        "count":     len(records),
        "timestamp": time.Now().Format(time.RFC3339),
    }
    eventJSON, _ := json.Marshal(event)
    ctx.GetStub().SetEvent("RecordsBatchCreated", eventJSON)

    return nil
}
