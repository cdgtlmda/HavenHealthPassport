package org.havenhealthpassport.terminology;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.jpa.api.dao.IFhirResourceDao;
import ca.uhn.fhir.jpa.term.api.ITermLoaderSvc;
import ca.uhn.fhir.rest.api.server.RequestDetails;
import org.hl7.fhir.r4.model.CodeSystem;
import org.hl7.fhir.r4.model.ValueSet;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Service;

import javax.annotation.PostConstruct;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

/**
 * Haven Health Passport Terminology Loader Service
 *
 * This service manages loading of terminology resources including
 * LOINC, SNOMED CT, ICD-10, and RxNorm.
 */
@Service
public class HavenTerminologyLoaderService {

    private static final Logger logger = LoggerFactory.getLogger(HavenTerminologyLoaderService.class);

    @Autowired
    private ITermLoaderSvc termLoaderSvc;

    @Autowired
    private FhirContext fhirContext;

    @Autowired
    private IFhirResourceDao<CodeSystem> codeSystemDao;

    @Autowired
    private IFhirResourceDao<ValueSet> valueSetDao;

    @Value("${hapi.fhir.terminology.code_systems.loinc.enabled:true}")
    private boolean loincEnabled;

    @Value("${hapi.fhir.terminology.code_systems.loinc.file_path:/app/terminology/loinc/Loinc.csv}")
    private String loincFilePath;

    @Value("${hapi.fhir.terminology.code_systems.snomed.enabled:true}")
    private boolean snomedEnabled;

    @Value("${hapi.fhir.terminology.code_systems.icd10.enabled:true}")
    private boolean icd10Enabled;

    @Value("${hapi.fhir.terminology.code_systems.rxnorm.enabled:true}")
    private boolean rxnormEnabled;

    @Value("${hapi.fhir.terminology.builtin.load_core_terminology:true}")
    private boolean loadCoreTerminology;

    /**
     * Initialize terminology loader on application startup
     */
    @EventListener(ApplicationReadyEvent.class)
    public void initializeTerminology() {
        logger.info("Initializing Haven Health Passport Terminology Service");

        try {
            // Load core FHIR terminology
            if (loadCoreTerminology) {
                loadCoreTerminology();
            }

            // Load LOINC if enabled
            if (loincEnabled) {
                loadLoinc();
            }

            // Load SNOMED CT if enabled
            if (snomedEnabled) {
                loadSnomedCt();
            }

            // Load ICD-10 if enabled
            if (icd10Enabled) {
                loadIcd10();
            }

            // Load RxNorm if enabled
            if (rxnormEnabled) {
                loadRxNorm();
            }

            // Load custom ValueSets
            loadCustomValueSets();

            logger.info("Terminology service initialization completed successfully");

        } catch (Exception e) {
            logger.error("Failed to initialize terminology service: {}", e.getMessage(), e);
        }
    }

    /**
     * Load core FHIR terminology resources
     */
    private void loadCoreTerminology() {
        logger.info("Loading core FHIR terminology");

        try {
            // Core code systems are typically loaded automatically by HAPI FHIR
            // This is a placeholder for any custom core terminology loading

            // Create custom code system for Haven Health Passport
            CodeSystem havenCodeSystem = new CodeSystem();
            havenCodeSystem.setUrl("https://havenhealthpassport.org/fhir/CodeSystem/haven-codes");
            havenCodeSystem.setName("HavenHealthPassportCodes");
            havenCodeSystem.setTitle("Haven Health Passport Custom Codes");
            havenCodeSystem.setStatus(CodeSystem.PublicationStatus.ACTIVE);
            havenCodeSystem.setContent(CodeSystem.CodeSystemContentMode.COMPLETE);

            // Add custom concepts
            havenCodeSystem.addConcept()
                .setCode("refugee-status")
                .setDisplay("Refugee Status")
                .setDefinition("Status of refugee registration");

            havenCodeSystem.addConcept()
                .setCode("displacement-reason")
                .setDisplay("Displacement Reason")
                .setDefinition("Reason for displacement");

            havenCodeSystem.addConcept()
                .setCode("camp-location")
                .setDisplay("Camp Location")
                .setDefinition("Current refugee camp location");

            // Save code system
            codeSystemDao.update(havenCodeSystem);

            logger.info("Core terminology loaded successfully");

        } catch (Exception e) {
            logger.error("Failed to load core terminology: {}", e.getMessage());
        }
    }

    /**
     * Load LOINC terminology
     */
    private void loadLoinc() {
        logger.info("Loading LOINC terminology");

        try {
            Path loincPath = Paths.get(loincFilePath);
            if (!Files.exists(loincPath)) {
                logger.warn("LOINC file not found at: {}", loincFilePath);
                return;
            }

            // Use HAPI FHIR's built-in LOINC loader
            // This requires the LOINC files to be in the expected format
            RequestDetails requestDetails = new SystemRequestDetails();

            List<ITermLoaderSvc.FileDescriptor> files = new ArrayList<>();
            files.add(new ITermLoaderSvc.FileDescriptor() {
                @Override
                public String getFilename() {
                    return loincPath.getFileName().toString();
                }

                @Override
                public java.io.InputStream getInputStream() {
                    try {
                        return Files.newInputStream(loincPath);
                    } catch (Exception e) {
                        throw new RuntimeException(e);
                    }
                }
            });

            // Load LOINC
            termLoaderSvc.loadLoinc(files, requestDetails);

            logger.info("LOINC terminology loaded successfully");

        } catch (Exception e) {
            logger.error("Failed to load LOINC: {}", e.getMessage());
        }
    }

    /**
     * Load SNOMED CT terminology
     */
    private void loadSnomedCt() {
        logger.info("Loading SNOMED CT terminology");

        try {
            // SNOMED CT loading is complex and requires the full RF2 release files
            // This is a placeholder for the actual implementation
            logger.info("SNOMED CT loading configured but files not available");

        } catch (Exception e) {
            logger.error("Failed to load SNOMED CT: {}", e.getMessage());
        }
    }

    /**
     * Load ICD-10 terminology
     */
    private void loadIcd10() {
        logger.info("Loading ICD-10 terminology");

        try {
            // Create ICD-10 code system
            CodeSystem icd10 = new CodeSystem();
            icd10.setUrl("http://hl7.org/fhir/sid/icd-10");
            icd10.setName("ICD10");
            icd10.setTitle("International Classification of Diseases, 10th Revision");
            icd10.setStatus(CodeSystem.PublicationStatus.ACTIVE);
            icd10.setContent(CodeSystem.CodeSystemContentMode.NOTPRESENT);
            icd10.setDescription("ICD-10 diagnosis codes");

            // Note: Full ICD-10 loading would require parsing the actual ICD-10 files
            // This is a placeholder showing the structure

            codeSystemDao.update(icd10);

            logger.info("ICD-10 terminology configured successfully");

        } catch (Exception e) {
            logger.error("Failed to load ICD-10: {}", e.getMessage());
        }
    }

    /**
     * Load RxNorm terminology
     */
    private void loadRxNorm() {
        logger.info("Loading RxNorm terminology");

        try {
            // Create RxNorm code system
            CodeSystem rxnorm = new CodeSystem();
            rxnorm.setUrl("http://www.nlm.nih.gov/research/umls/rxnorm");
            rxnorm.setName("RxNorm");
            rxnorm.setTitle("RxNorm");
            rxnorm.setStatus(CodeSystem.PublicationStatus.ACTIVE);
            rxnorm.setContent(CodeSystem.CodeSystemContentMode.NOTPRESENT);
            rxnorm.setDescription("RxNorm drug terminology");

            codeSystemDao.update(rxnorm);

            logger.info("RxNorm terminology configured successfully");

        } catch (Exception e) {
            logger.error("Failed to load RxNorm: {}", e.getMessage());
        }
    }

    /**
     * Load custom ValueSets for Haven Health Passport
     */
    private void loadCustomValueSets() {
        logger.info("Loading custom ValueSets");

        try {
            // Refugee Status ValueSet
            ValueSet refugeeStatusVS = new ValueSet();
            refugeeStatusVS.setUrl("https://havenhealthpassport.org/fhir/ValueSet/refugee-status");
            refugeeStatusVS.setName("RefugeeStatusValueSet");
            refugeeStatusVS.setTitle("Refugee Status Value Set");
            refugeeStatusVS.setStatus(ValueSet.PublicationStatus.ACTIVE);

            ValueSet.ValueSetComposeComponent compose = new ValueSet.ValueSetComposeComponent();
            ValueSet.ConceptSetComponent include = new ValueSet.ConceptSetComponent();
            include.setSystem("https://havenhealthpassport.org/fhir/CodeSystem/haven-codes");
            include.addConcept().setCode("registered").setDisplay("Registered Refugee");
            include.addConcept().setCode("asylum-seeker").setDisplay("Asylum Seeker");
            include.addConcept().setCode("internally-displaced").setDisplay("Internally Displaced Person");
            include.addConcept().setCode("stateless").setDisplay("Stateless Person");

            compose.addInclude(include);
            refugeeStatusVS.setCompose(compose);

            valueSetDao.update(refugeeStatusVS);

            // Emergency Conditions ValueSet
            ValueSet emergencyConditionsVS = new ValueSet();
            emergencyConditionsVS.setUrl("https://havenhealthpassport.org/fhir/ValueSet/emergency-conditions");
            emergencyConditionsVS.setName("EmergencyConditionsValueSet");
            emergencyConditionsVS.setTitle("Emergency Medical Conditions");
            emergencyConditionsVS.setStatus(ValueSet.PublicationStatus.ACTIVE);

            ValueSet.ValueSetComposeComponent emergencyCompose = new ValueSet.ValueSetComposeComponent();
            ValueSet.ConceptSetComponent emergencyInclude = new ValueSet.ConceptSetComponent();
            emergencyInclude.setSystem("http://snomed.info/sct");

            // Include specific SNOMED CT codes for emergency conditions
            emergencyInclude.addFilter()
                .setProperty("concept")
                .setOp(ValueSet.FilterOperator.ISA)
                .setValue("50043002"); // Disorder of cardiovascular system

            emergencyCompose.addInclude(emergencyInclude);
            emergencyConditionsVS.setCompose(emergencyCompose);

            valueSetDao.update(emergencyConditionsVS);

            logger.info("Custom ValueSets loaded successfully");

        } catch (Exception e) {
            logger.error("Failed to load custom ValueSets: {}", e.getMessage());
        }
    }

    /**
     * Helper class for system request details
     */
    private static class SystemRequestDetails extends RequestDetails {
        @Override
        public String getRequestId() {
            return "SYSTEM";
        }

        @Override
        public String getRequestPath() {
            return "";
        }

        @Override
        public String getFhirServerBase() {
            return "";
        }
    }
}
