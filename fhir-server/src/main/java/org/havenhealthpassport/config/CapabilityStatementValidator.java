package org.havenhealthpassport.config;

import org.hl7.fhir.r4.model.CapabilityStatement;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.*;

/**
 * Validator to ensure the CapabilityStatement is properly configured
 */
@Component
public class CapabilityStatementValidator {

    private static final Logger logger = LoggerFactory.getLogger(CapabilityStatementValidator.class);

    /**
     * Validate the capability statement configuration
     */
    public boolean validateCapabilityStatement(CapabilityStatement cs) {
        List<String> validationErrors = new ArrayList<>();

        // Validate basic metadata
        if (!cs.hasName()) {
            validationErrors.add("CapabilityStatement must have a name");
        }
        if (!cs.hasStatus()) {
            validationErrors.add("CapabilityStatement must have a status");
        }
        if (!cs.hasFhirVersion()) {
            validationErrors.add("CapabilityStatement must have a FHIR version");
        }
        if (!cs.hasKind()) {
            validationErrors.add("CapabilityStatement must have a kind");
        }

        // Validate implementation details
        if (!cs.hasImplementation()) {
            validationErrors.add("CapabilityStatement must have implementation details");
        }

        // Validate software details
        if (!cs.hasSoftware()) {
            validationErrors.add("CapabilityStatement must have software details");
        }

        // Validate REST component
        if (cs.getRest().isEmpty()) {
            validationErrors.add("CapabilityStatement must have at least one REST component");
        }
