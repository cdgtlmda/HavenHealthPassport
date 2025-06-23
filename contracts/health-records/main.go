package main

import (
    "log"

    "github.com/hyperledger/fabric-contract-api-go/contractapi"
)

func main() {
    healthRecordChaincode, err := contractapi.NewChaincode(&HealthRecordContract{})
    if err != nil {
        log.Panicf("Error creating health record chaincode: %v", err)
    }

    if err := healthRecordChaincode.Start(); err != nil {
        log.Panicf("Error starting health record chaincode: %v", err)
    }
}