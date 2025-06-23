/*
 * SPDX-License-Identifier: Apache-2.0
 * 
 * Haven Health Passport - Health Record Smart Contract
 * This chaincode manages health records verification on Hyperledger Fabric
 * for refugee and displaced populations healthcare data.
 */

'use strict';

const { Contract } = require('fabric-contract-api');

class HealthRecordContract extends Contract {

    async initLedger(ctx) {
        console.info('============= START : Initialize Ledger ===========');
        
        // Initialize with country public keys for cross-border verification
        const countryKeys = [
            {
                countryCode: 'US',
                publicKey: 'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...',
                organization: 'US Department of Health',
                validFrom: new Date().toISOString(),
                validUntil: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString()
            },
            {
                countryCode: 'CA',
                publicKey: 'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...',
                organization: 'Health Canada',
                validFrom: new Date().toISOString(),
                validUntil: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString()
            }
        ];

        for (const key of countryKeys) {
            await ctx.stub.putState(`COUNTRY_KEY_${key.countryCode}`, Buffer.from(JSON.stringify(key)));
        }
        
        console.info('============= END : Initialize Ledger ===========');
    }

    async createHealthRecord(ctx, recordDataJSON) {
        console.info('============= START : Create Health Record ===========');
        
        const recordData = JSON.parse(recordDataJSON);
        const recordId = recordData.recordId;
        
        // Validate required fields
        if (!recordId || !recordData.hash || !recordData.patientId) {
            throw new Error('Missing required fields: recordId, hash, or patientId');
        }
        
        // Check if record already exists
        const existingRecord = await ctx.stub.getState(recordId);
        if (existingRecord && existingRecord.length > 0) {
            throw new Error(`Health record ${recordId} already exists`);
        }
        
        // Create record with metadata
        const healthRecord = {
            docType: 'healthRecord',
            recordId: recordId,
            hash: recordData.hash,
            patientId: recordData.patientId,
            recordType: recordData.recordType || 'general',
            timestamp: recordData.timestamp,
            verifierOrg: recordData.verifierOrg,
            metadata: recordData.metadata || {},
            createdAt: new Date().toISOString(),
            lastModified: new Date().toISOString(),
            verificationCount: 0,
            crossBorderAccess: []
        };
        
        // Store record
        await ctx.stub.putState(recordId, Buffer.from(JSON.stringify(healthRecord)));
        
        // Create composite key for patient records
        const patientRecordKey = ctx.stub.createCompositeKey('patient~record', [recordData.patientId, recordId]);
        await ctx.stub.putState(patientRecordKey, Buffer.from('\u0000'));
        
        // Emit event
        ctx.stub.setEvent('HealthRecordCreated', Buffer.from(JSON.stringify({
            recordId: recordId,
            patientId: recordData.patientId,
            timestamp: new Date().toISOString()
        })));
        
        console.info('============= END : Create Health Record ===========');
        return ctx.stub.getTxID();
    }

    async queryHealthRecord(ctx, recordId) {
        const recordAsBytes = await ctx.stub.getState(recordId);
        if (!recordAsBytes || recordAsBytes.length === 0) {
            throw new Error(`Health record ${recordId} does not exist`);
        }
        return recordAsBytes.toString();
    }

    async recordVerification(ctx, recordId, verificationHash, verifierId, status, metadataJSON) {
        console.info('============= START : Record Verification ===========');
        
        // Get the record
        const recordAsBytes = await ctx.stub.getState(recordId);
        if (!recordAsBytes || recordAsBytes.length === 0) {
            throw new Error(`Health record ${recordId} does not exist`);
        }
        
        const healthRecord = JSON.parse(recordAsBytes.toString());
        const metadata = JSON.parse(metadataJSON);
        
        // Create verification entry
        const verification = {
            transactionId: ctx.stub.getTxID(),
            timestamp: new Date().toISOString(),
            verifierId: verifierId,
            verifierOrg: metadata.verifier_org,
            status: status,
            hash: verificationHash,
            verificationType: metadata.verification_type || 'health_record',
            metadata: metadata
        };
        
        // Store verification with composite key
        const verificationKey = ctx.stub.createCompositeKey('record~verification', [recordId, ctx.stub.getTxID()]);
        await ctx.stub.putState(verificationKey, Buffer.from(JSON.stringify(verification)));
        
        // Update record verification count
        healthRecord.verificationCount += 1;
        healthRecord.lastVerified = new Date().toISOString();
        healthRecord.lastModified = new Date().toISOString();
        
        await ctx.stub.putState(recordId, Buffer.from(JSON.stringify(healthRecord)));
        
        // Emit verification event
        ctx.stub.setEvent('VerificationRecorded', Buffer.from(JSON.stringify({
            recordId: recordId,
            verifierId: verifierId,
            status: status,
            timestamp: new Date().toISOString()
        })));
        
        console.info('============= END : Record Verification ===========');
        return ctx.stub.getTxID();
    }

    async getVerificationHistory(ctx, recordId) {
        console.info('============= START : Get Verification History ===========');
        
        // Check if record exists
        const recordAsBytes = await ctx.stub.getState(recordId);
        if (!recordAsBytes || recordAsBytes.length === 0) {
            throw new Error(`Health record ${recordId} does not exist`);
        }
        
        const verifications = [];
        
        // Get all verifications for this record
        const iterator = await ctx.stub.getStateByPartialCompositeKey('record~verification', [recordId]);
        
        try {
            while (true) {
                const result = await iterator.next();
                
                if (result.value && result.value.value.toString()) {
                    const verification = JSON.parse(result.value.value.toString());
                    verifications.push(verification);
                }
                
                if (result.done) {
                    await iterator.close();
                    break;
                }
            }
        } catch (err) {
            console.error(err);
            throw new Error('Error retrieving verification history');
        }
        
        console.info('============= END : Get Verification History ===========');
        return JSON.stringify(verifications);
    }

    async createCrossBorderVerification(ctx, verificationDataJSON) {
        console.info('============= START : Create Cross-Border Verification ===========');
        
        const verificationData = JSON.parse(verificationDataJSON);
        const verificationId = verificationData.verificationId;
        
        // Validate required fields
        if (!verificationId || !verificationData.patientId || !verificationData.destinationCountry) {
            throw new Error('Missing required fields for cross-border verification');
        }
        
        // Store cross-border verification
        const crossBorderVerification = {
            docType: 'crossBorderVerification',
            ...verificationData,
            createdAt: new Date().toISOString(),
            lastModified: new Date().toISOString(),
            accessLog: []
        };
        
        await ctx.stub.putState(verificationId, Buffer.from(JSON.stringify(crossBorderVerification)));
        
        // Create composite key for patient cross-border verifications
        const patientCBVKey = ctx.stub.createCompositeKey('patient~cbv', [verificationData.patientId, verificationId]);
        await ctx.stub.putState(patientCBVKey, Buffer.from('\u0000'));
        
        // Emit event
        ctx.stub.setEvent('CrossBorderVerificationCreated', Buffer.from(JSON.stringify({
            verificationId: verificationId,
            patientId: verificationData.patientId,
            destinationCountry: verificationData.destinationCountry,
            timestamp: new Date().toISOString()
        })));
        
        console.info('============= END : Create Cross-Border Verification ===========');
        return ctx.stub.getTxID();
    }

    async updateCrossBorderVerification(ctx, verificationId, updateDataJSON) {
        console.info('============= START : Update Cross-Border Verification ===========');
        
        // Get existing verification
        const verificationAsBytes = await ctx.stub.getState(verificationId);
        if (!verificationAsBytes || verificationAsBytes.length === 0) {
            throw new Error(`Cross-border verification ${verificationId} does not exist`);
        }
        
        const verification = JSON.parse(verificationAsBytes.toString());
        const updateData = JSON.parse(updateDataJSON);
        
        // Update fields
        Object.assign(verification, updateData);
        verification.lastModified = new Date().toISOString();
        
        // Store updated verification
        await ctx.stub.putState(verificationId, Buffer.from(JSON.stringify(verification)));
        
        console.info('============= END : Update Cross-Border Verification ===========');
        return ctx.stub.getTxID();
    }

    async getCrossBorderVerification(ctx, verificationId) {
        const verificationAsBytes = await ctx.stub.getState(verificationId);
        if (!verificationAsBytes || verificationAsBytes.length === 0) {
            throw new Error(`Cross-border verification ${verificationId} does not exist`);
        }
        return verificationAsBytes.toString();
    }

    async logCrossBorderAccess(ctx, verificationId, accessingCountry, timestamp) {
        console.info('============= START : Log Cross-Border Access ===========');
        
        // Get verification
        const verificationAsBytes = await ctx.stub.getState(verificationId);
        if (!verificationAsBytes || verificationAsBytes.length === 0) {
            throw new Error(`Cross-border verification ${verificationId} does not exist`);
        }
        
        const verification = JSON.parse(verificationAsBytes.toString());
        
        // Add access log entry
        verification.accessLog.push({
            accessingCountry: accessingCountry,
            timestamp: timestamp,
            txId: ctx.stub.getTxID()
        });
        
        verification.lastAccessed = timestamp;
        verification.lastModified = new Date().toISOString();
        
        // Store updated verification
        await ctx.stub.putState(verificationId, Buffer.from(JSON.stringify(verification)));
        
        // Emit access event
        ctx.stub.setEvent('CrossBorderAccess', Buffer.from(JSON.stringify({
            verificationId: verificationId,
            accessingCountry: accessingCountry,
            timestamp: timestamp
        })));
        
        console.info('============= END : Log Cross-Border Access ===========');
        return ctx.stub.getTxID();
    }

    async revokeCrossBorderVerification(ctx, verificationId, reason, timestamp) {
        console.info('============= START : Revoke Cross-Border Verification ===========');
        
        // Get verification
        const verificationAsBytes = await ctx.stub.getState(verificationId);
        if (!verificationAsBytes || verificationAsBytes.length === 0) {
            throw new Error(`Cross-border verification ${verificationId} does not exist`);
        }
        
        const verification = JSON.parse(verificationAsBytes.toString());
        
        // Update status
        verification.status = 'revoked';
        verification.revokedAt = timestamp;
        verification.revocationReason = reason;
        verification.lastModified = new Date().toISOString();
        
        // Store updated verification
        await ctx.stub.putState(verificationId, Buffer.from(JSON.stringify(verification)));
        
        // Emit revocation event
        ctx.stub.setEvent('CrossBorderVerificationRevoked', Buffer.from(JSON.stringify({
            verificationId: verificationId,
            reason: reason,
            timestamp: timestamp
        })));
        
        console.info('============= END : Revoke Cross-Border Verification ===========');
        return true;
    }

    async getCountryPublicKey(ctx, countryCode) {
        const keyAsBytes = await ctx.stub.getState(`COUNTRY_KEY_${countryCode}`);
        if (!keyAsBytes || keyAsBytes.length === 0) {
            throw new Error(`Public key for country ${countryCode} not found`);
        }
        return keyAsBytes.toString();
    }

    async updateCountryPublicKey(ctx, countryCode, publicKey, organization) {
        console.info('============= START : Update Country Public Key ===========');
        
        const keyData = {
            countryCode: countryCode,
            publicKey: publicKey,
            organization: organization,
            validFrom: new Date().toISOString(),
            validUntil: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString(),
            updatedAt: new Date().toISOString(),
            updatedBy: ctx.clientIdentity.getID()
        };
        
        await ctx.stub.putState(`COUNTRY_KEY_${countryCode}`, Buffer.from(JSON.stringify(keyData)));
        
        console.info('============= END : Update Country Public Key ===========');
        return true;
    }

    // Query functions for analytics and reporting
    async getPatientRecords(ctx, patientId) {
        console.info('============= START : Get Patient Records ===========');
        
        const records = [];
        const iterator = await ctx.stub.getStateByPartialCompositeKey('patient~record', [patientId]);
        
        try {
            while (true) {
                const result = await iterator.next();
                
                if (result.value && result.value.key) {
                    const compositeKey = ctx.stub.splitCompositeKey(result.value.key);
                    const recordId = compositeKey.attributes[1];
                    
                    const recordAsBytes = await ctx.stub.getState(recordId);
                    if (recordAsBytes && recordAsBytes.length > 0) {
                        records.push(JSON.parse(recordAsBytes.toString()));
                    }
                }
                
                if (result.done) {
                    await iterator.close();
                    break;
                }
            }
        } catch (err) {
            console.error(err);
            throw new Error('Error retrieving patient records');
        }
        
        console.info('============= END : Get Patient Records ===========');
        return JSON.stringify(records);
    }

    async getVerificationStats(ctx, startDate, endDate) {
        console.info('============= START : Get Verification Stats ===========');
        
        const stats = {
            totalRecords: 0,
            totalVerifications: 0,
            verificationsByStatus: {},
            verificationsByOrg: {},
            crossBorderVerifications: 0
        };
        
        // This would require more complex queries in production
        // For now, returning placeholder stats structure
        
        console.info('============= END : Get Verification Stats ===========');
        return JSON.stringify(stats);
    }
}

module.exports = HealthRecordContract;