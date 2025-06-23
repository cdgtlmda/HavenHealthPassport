package org.havenhealthpassport.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.*;

/**
 * Configuration properties for FHIR Capability Statement
 * Maps to the conformance-config.yaml file
 */
@Component
@ConfigurationProperties(prefix = "hapi.fhir.capability-statement")
public class CapabilityStatementProperties {

    private Software software = new Software();
    private Implementation implementation = new Implementation();
    private String kind = "instance";
    private String fhirVersion = "4.0.1";
    private List<String> format = new ArrayList<>();
    private List<String> patchFormat = new ArrayList<>();
    private List<String> implementationGuide = new ArrayList<>();

    // Getters and setters
    public Software getSoftware() {
        return software;
    }

    public void setSoftware(Software software) {
        this.software = software;
    }

    public Implementation getImplementation() {
        return implementation;
    }

    public void setImplementation(Implementation implementation) {
        this.implementation = implementation;
    }

    public String getKind() {
        return kind;
    }

    public void setKind(String kind) {
        this.kind = kind;
    }

    public String getFhirVersion() {
        return fhirVersion;
    }
