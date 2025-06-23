package main

import (
    "log"

    "github.com/haven-health-passport/chaincode/health-records/contracts"
    "github.com/hyperledger/fabric-contract-api-go/contractapi"
)

func main() {
    // Create a new chaincode instance
    healthRecordContract := new(contracts.HealthRecordContract)
    verificationContract := new(contracts.VerificationContract)
    accessControlContract := new(contracts.AccessControlContract)

    // Create the chaincode with multiple contracts
    chaincode, err := contractapi.NewChaincode(
        healthRecordContract,
        verificationContract,
        accessControlContract,
    )

    if err != nil {
        log.Panicf("Error creating Haven Health Passport chaincode: %v", err)
    }

    // Start the chaincode
    if err := chaincode.Start(); err != nil {
        log.Panicf("Error starting Haven Health Passport chaincode: %v", err)
    }
}
