package org.havenhealthpassport.config;

import ca.uhn.fhir.rest.server.IResourceProvider;
import ca.uhn.fhir.rest.server.RestfulServer;
import ca.uhn.fhir.rest.server.provider.ServerCapabilityStatementProvider;
import org.hl7.fhir.r4.model.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.event.ContextRefreshedEvent;
import org.springframework.context.event.EventListener;

import javax.servlet.ServletContext;
import java.util.Date;
import java.util.List;

/**
 * Haven Health Passport Capability Statement Configuration
 *
 * Configures the server's CapabilityStatement to declare supported
 * resources, operations, and search parameters.
 */
@Configuration
public class HavenCapabilityStatementConfig {

    private static final Logger logger = LoggerFactory.getLogger(HavenCapabilityStatementConfig.class);

    /**
     * Configure capability statement after context refresh
     */
    @EventListener(ContextRefreshedEvent.class)
    public void configureCapabilityStatement(ContextRefreshedEvent event) {
        RestfulServer restfulServer = event.getApplicationContext().getBean(RestfulServer.class);

        if (restfulServer != null) {
            // Create custom capability statement provider
            HavenCapabilityStatementProvider provider = new HavenCapabilityStatementProvider(restfulServer);
            restfulServer.setServerConformanceProvider(provider);

            logger.info("Custom capability statement provider registered");
        }
    }

    /**
     * Custom capability statement provider
     */
    public static class HavenCapabilityStatementProvider extends ServerCapabilityStatementProvider {

        public HavenCapabilityStatementProvider(RestfulServer theServer) {
            super(theServer);
        }

        @Override
        public CapabilityStatement getServerConformance(javax.servlet.http.HttpServletRequest theRequest, RequestDetails theRequestDetails) {
            CapabilityStatement cs = super.getServerConformance(theRequest, theRequestDetails);

            // Customize the capability statement
            customizeCapabilityStatement(cs);

            return cs;
        }
        private void customizeCapabilityStatement(CapabilityStatement cs) {
            // Set implementation details
            cs.setName("HavenHealthPassportCapabilityStatement");
            cs.setTitle("Haven Health Passport FHIR Server Capability Statement");
            cs.setStatus(Enumerations.PublicationStatus.ACTIVE);
            cs.setDate(new Date());
            cs.setPublisher("Haven Health Passport");
            cs.setDescription("Capability Statement for Haven Health Passport FHIR Server - Secure health records for refugees");
            cs.setKind(CapabilityStatement.CapabilityStatementKind.INSTANCE);
            cs.setFhirVersion(Enumerations.FHIRVersion._4_0_1);

            // Add supported formats
            cs.getFormat().clear();
            cs.addFormat("application/fhir+json");
            cs.addFormat("application/fhir+xml");

            // Add patch formats
            cs.addPatchFormat("application/json-patch+json");
            cs.addPatchFormat("application/fhir+json");

            // Implementation details
            CapabilityStatement.CapabilityStatementImplementationComponent impl = cs.getImplementation();
            impl.setDescription("Haven Health Passport - Secure, portable health records for refugees and displaced populations");

            // Software details
            CapabilityStatement.CapabilityStatementSoftwareComponent software = cs.getSoftware();
            software.setName("Haven Health Passport FHIR Server");
            software.setVersion("1.0.0");
            software.setReleaseDate(new Date());

            // Configure REST component
            if (cs.getRest().isEmpty()) {
                cs.addRest();
            }
            CapabilityStatement.CapabilityStatementRestComponent rest = cs.getRest().get(0);
            rest.setMode(CapabilityStatement.RestfulCapabilityMode.SERVER);

            // Configure supported resources with detailed capabilities
            configureResourceCapabilities(rest);

            // Add custom search parameters
            addCustomSearchParameters(rest);

            // Configure supported interactions
            configureSupportedInteractions(rest);

            // Add security information
            CapabilityStatement.CapabilityStatementRestSecurityComponent security =
                cs.getRest().get(0).getSecurity();
            security.setCors(true);
            security.setDescription("OAuth2 authentication required for all write operations. " +
                "Supports role-based access control for refugees, healthcare providers, and administrators.");

            // Add OAuth2 service
            CodeableConcept oauthService = new CodeableConcept();
            oauthService.addCoding()
                .setSystem("http://terminology.hl7.org/CodeSystem/restful-security-service")
                .setCode("OAuth")
                .setDisplay("OAuth2 Token");
            security.getService().add(oauthService);

            // Add security information
            configureSecurityComponent(rest);

            // Add custom operations
            addCustomOperations(cs);

            // Add implementation guides
            cs.getImplementationGuide().clear();
            cs.getImplementationGuide().add(new CanonicalType("http://hl7.org/fhir/uv/ips/"));
            cs.getImplementationGuide().add(new CanonicalType("https://havenhealthpassport.org/fhir/ImplementationGuide/refugee-health"));
        }

        private void configureResourceCapabilities(CapabilityStatement.CapabilityStatementRestComponent rest) {
            // Clear existing resources to configure from scratch
            rest.getResource().clear();

            // Configure Patient resource
            CapabilityStatement.CapabilityStatementRestResourceComponent patient = new CapabilityStatement.CapabilityStatementRestResourceComponent();
            patient.setType("Patient");
            patient.setProfile("http://hl7.org/fhir/StructureDefinition/Patient");
            configureResourceInteractions(patient, true, true, true, true, true);
            patient.setVersioning(CapabilityStatement.ResourceVersionPolicy.VERSIONED);
            patient.setReadHistory(true);
            patient.setUpdateCreate(true);
            patient.setConditionalCreate(true);
            patient.setConditionalRead(CapabilityStatement.ConditionalReadStatus.FULLSUPPORT);
            patient.setConditionalUpdate(true);
            patient.setConditionalDelete(CapabilityStatement.ConditionalDeleteStatus.MULTIPLE);
            patient.addReferencePolicy(CapabilityStatement.ReferenceHandlingPolicy.LITERAL);
            patient.addReferencePolicy(CapabilityStatement.ReferenceHandlingPolicy.LOGICAL);
            patient.addSearchInclude("Patient:general-practitioner");
            patient.addSearchInclude("Patient:link");
            patient.addSearchInclude("Patient:organization");
            patient.addSearchRevInclude("AllergyIntolerance:patient");
            patient.addSearchRevInclude("Condition:patient");
            patient.addSearchRevInclude("Observation:patient");
            rest.addResource(patient);

            // Configure Observation resource
            CapabilityStatement.CapabilityStatementRestResourceComponent observation = new CapabilityStatement.CapabilityStatementRestResourceComponent();
            observation.setType("Observation");
            observation.setProfile("http://hl7.org/fhir/StructureDefinition/Observation");
            configureResourceInteractions(observation, true, true, true, false, true);
            observation.setVersioning(CapabilityStatement.ResourceVersionPolicy.VERSIONED);
            rest.addResource(observation);

            // Configure Condition resource
            CapabilityStatement.CapabilityStatementRestResourceComponent condition = new CapabilityStatement.CapabilityStatementRestResourceComponent();
            condition.setType("Condition");
            condition.setProfile("http://hl7.org/fhir/StructureDefinition/Condition");
            configureResourceInteractions(condition, true, true, true, false, true);
            condition.setVersioning(CapabilityStatement.ResourceVersionPolicy.VERSIONED);
            rest.addResource(condition);

            // Configure MedicationRequest resource
            CapabilityStatement.CapabilityStatementRestResourceComponent medicationRequest = new CapabilityStatement.CapabilityStatementRestResourceComponent();
            medicationRequest.setType("MedicationRequest");
            medicationRequest.setProfile("http://hl7.org/fhir/StructureDefinition/MedicationRequest");
            configureResourceInteractions(medicationRequest, true, true, true, false, true);
            medicationRequest.setVersioning(CapabilityStatement.ResourceVersionPolicy.VERSIONED);
            rest.addResource(medicationRequest);

            // Configure Procedure resource
            CapabilityStatement.CapabilityStatementRestResourceComponent procedure = new CapabilityStatement.CapabilityStatementRestResourceComponent();
            procedure.setType("Procedure");
            procedure.setProfile("http://hl7.org/fhir/StructureDefinition/Procedure");
            configureResourceInteractions(procedure, true, true, true, false, true);
            procedure.setVersioning(CapabilityStatement.ResourceVersionPolicy.VERSIONED);
            rest.addResource(procedure);

            // Configure DocumentReference resource
            CapabilityStatement.CapabilityStatementRestResourceComponent documentReference = new CapabilityStatement.CapabilityStatementRestResourceComponent();
            documentReference.setType("DocumentReference");
            documentReference.setProfile("http://hl7.org/fhir/StructureDefinition/DocumentReference");
            configureResourceInteractions(documentReference, true, true, true, false, true);
            documentReference.setVersioning(CapabilityStatement.ResourceVersionPolicy.VERSIONED);
            rest.addResource(documentReference);

            // Configure AllergyIntolerance resource
            CapabilityStatement.CapabilityStatementRestResourceComponent allergyIntolerance = new CapabilityStatement.CapabilityStatementRestResourceComponent();
            allergyIntolerance.setType("AllergyIntolerance");
            allergyIntolerance.setProfile("http://hl7.org/fhir/StructureDefinition/AllergyIntolerance");
            configureResourceInteractions(allergyIntolerance, true, true, true, false, true);
            allergyIntolerance.setVersioning(CapabilityStatement.ResourceVersionPolicy.VERSIONED);
            rest.addResource(allergyIntolerance);

            // Configure Immunization resource
            CapabilityStatement.CapabilityStatementRestResourceComponent immunization = new CapabilityStatement.CapabilityStatementRestResourceComponent();
            immunization.setType("Immunization");
            immunization.setProfile("http://hl7.org/fhir/StructureDefinition/Immunization");
            configureResourceInteractions(immunization, true, true, true, false, true);
            immunization.setVersioning(CapabilityStatement.ResourceVersionPolicy.VERSIONED);
            rest.addResource(immunization);

            // Configure Organization resource
            CapabilityStatement.CapabilityStatementRestResourceComponent organization = new CapabilityStatement.CapabilityStatementRestResourceComponent();
            organization.setType("Organization");
            organization.setProfile("http://hl7.org/fhir/StructureDefinition/Organization");
            configureResourceInteractions(organization, true, true, false, false, true);
            organization.setVersioning(CapabilityStatement.ResourceVersionPolicy.VERSIONED);
            rest.addResource(organization);

            // Configure Practitioner resource
            CapabilityStatement.CapabilityStatementRestResourceComponent practitioner = new CapabilityStatement.CapabilityStatementRestResourceComponent();
            practitioner.setType("Practitioner");
            practitioner.setProfile("http://hl7.org/fhir/StructureDefinition/Practitioner");
            configureResourceInteractions(practitioner, true, true, false, false, true);
            practitioner.setVersioning(CapabilityStatement.ResourceVersionPolicy.VERSIONED);
            rest.addResource(practitioner);
        }

        private void configureResourceInteractions(CapabilityStatement.CapabilityStatementRestResourceComponent resource,
                                                  boolean supportsCRUD, boolean supportsHistory, boolean supportsDelete,
                                                  boolean supportsPatch, boolean supportsSearch) {
            if (supportsCRUD) {
                resource.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.READ);
                resource.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.VREAD);
                resource.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.UPDATE);
                resource.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.CREATE);
            }
            if (supportsDelete) {
                resource.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.DELETE);
            }
            if (supportsPatch) {
                resource.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.PATCH);
            }
            if (supportsHistory) {
                resource.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.HISTORYINSTANCE);
                resource.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.HISTORYTYPE);
            }
            if (supportsSearch) {
                resource.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.SEARCHTYPE);
            }
        }

        private void addCustomSearchParameters(CapabilityStatement.CapabilityStatementRestComponent rest) {
            for (CapabilityStatement.CapabilityStatementRestResourceComponent resource : rest.getResource()) {
                switch (resource.getType()) {
                    case "Patient":
                        addPatientSearchParameters(resource);
                        break;
                    case "Observation":
                        addObservationSearchParameters(resource);
                        break;
                    case "Condition":
                        addConditionSearchParameters(resource);
                        break;
                    case "MedicationRequest":
                        addMedicationRequestSearchParameters(resource);
                        break;
                    case "Procedure":
                        addProcedureSearchParameters(resource);
                        break;
                    case "DocumentReference":
                        addDocumentReferenceSearchParameters(resource);
                        break;
                    case "AllergyIntolerance":
                        addAllergyIntoleranceSearchParameters(resource);
                        break;
                    case "Immunization":
                        addImmunizationSearchParameters(resource);
                        break;
                    case "Organization":
                        addOrganizationSearchParameters(resource);
                        break;
                    case "Practitioner":
                        addPractitionerSearchParameters(resource);
                        break;
                }
            }
        }

        private void addPatientSearchParameters(CapabilityStatement.CapabilityStatementRestResourceComponent resource) {
            resource.getSearchParam().clear();
            addSearchParam(resource, "identifier", Enumerations.SearchParamType.TOKEN, "Patient identifier");
            addSearchParam(resource, "name", Enumerations.SearchParamType.STRING, "Patient name");
            addSearchParam(resource, "birthdate", Enumerations.SearchParamType.DATE, "Patient birth date");
            addSearchParam(resource, "gender", Enumerations.SearchParamType.TOKEN, "Patient gender");
            addSearchParam(resource, "refugee-status", Enumerations.SearchParamType.TOKEN, "Refugee status (custom)");
            addSearchParam(resource, "camp-location", Enumerations.SearchParamType.TOKEN, "Refugee camp location (custom)");
        }

        private void addObservationSearchParameters(CapabilityStatement.CapabilityStatementRestResourceComponent resource) {
            resource.getSearchParam().clear();
            addSearchParam(resource, "code", Enumerations.SearchParamType.TOKEN, "Observation code");
            addSearchParam(resource, "date", Enumerations.SearchParamType.DATE, "Observation date");
            addSearchParam(resource, "patient", Enumerations.SearchParamType.REFERENCE, "Patient reference");
            addSearchParam(resource, "category", Enumerations.SearchParamType.TOKEN, "Observation category");
            addSearchParam(resource, "value-quantity", Enumerations.SearchParamType.QUANTITY, "Observation value");
        }

        private void addConditionSearchParameters(CapabilityStatement.CapabilityStatementRestResourceComponent resource) {
            resource.getSearchParam().clear();
            addSearchParam(resource, "code", Enumerations.SearchParamType.TOKEN, "Condition code");
            addSearchParam(resource, "patient", Enumerations.SearchParamType.REFERENCE, "Patient reference");
            addSearchParam(resource, "clinical-status", Enumerations.SearchParamType.TOKEN, "Clinical status");
            addSearchParam(resource, "severity", Enumerations.SearchParamType.TOKEN, "Condition severity");
        }

        private void addMedicationRequestSearchParameters(CapabilityStatement.CapabilityStatementRestResourceComponent resource) {
            resource.getSearchParam().clear();
            addSearchParam(resource, "patient", Enumerations.SearchParamType.REFERENCE, "Patient reference");
            addSearchParam(resource, "status", Enumerations.SearchParamType.TOKEN, "Medication request status");
            addSearchParam(resource, "medication", Enumerations.SearchParamType.REFERENCE, "Medication reference");
            addSearchParam(resource, "authoredon", Enumerations.SearchParamType.DATE, "Authorization date");
        }

        private void addProcedureSearchParameters(CapabilityStatement.CapabilityStatementRestResourceComponent resource) {
            resource.getSearchParam().clear();
            addSearchParam(resource, "code", Enumerations.SearchParamType.TOKEN, "Procedure code");
            addSearchParam(resource, "patient", Enumerations.SearchParamType.REFERENCE, "Patient reference");
            addSearchParam(resource, "date", Enumerations.SearchParamType.DATE, "Procedure date");
            addSearchParam(resource, "status", Enumerations.SearchParamType.TOKEN, "Procedure status");
        }

        private void addDocumentReferenceSearchParameters(CapabilityStatement.CapabilityStatementRestResourceComponent resource) {
            resource.getSearchParam().clear();
            addSearchParam(resource, "patient", Enumerations.SearchParamType.REFERENCE, "Patient reference");
            addSearchParam(resource, "type", Enumerations.SearchParamType.TOKEN, "Document type");
            addSearchParam(resource, "date", Enumerations.SearchParamType.DATE, "Document date");
            addSearchParam(resource, "status", Enumerations.SearchParamType.TOKEN, "Document status");
        }

        private void addAllergyIntoleranceSearchParameters(CapabilityStatement.CapabilityStatementRestResourceComponent resource) {
            resource.getSearchParam().clear();
            addSearchParam(resource, "patient", Enumerations.SearchParamType.REFERENCE, "Patient reference");
            addSearchParam(resource, "code", Enumerations.SearchParamType.TOKEN, "Allergy code");
            addSearchParam(resource, "clinical-status", Enumerations.SearchParamType.TOKEN, "Clinical status");
        }

        private void addImmunizationSearchParameters(CapabilityStatement.CapabilityStatementRestResourceComponent resource) {
            resource.getSearchParam().clear();
            addSearchParam(resource, "patient", Enumerations.SearchParamType.REFERENCE, "Patient reference");
            addSearchParam(resource, "vaccine-code", Enumerations.SearchParamType.TOKEN, "Vaccine code");
            addSearchParam(resource, "date", Enumerations.SearchParamType.DATE, "Immunization date");
            addSearchParam(resource, "status", Enumerations.SearchParamType.TOKEN, "Immunization status");
        }

        private void addOrganizationSearchParameters(CapabilityStatement.CapabilityStatementRestResourceComponent resource) {
            resource.getSearchParam().clear();
            addSearchParam(resource, "name", Enumerations.SearchParamType.STRING, "Organization name");
            addSearchParam(resource, "identifier", Enumerations.SearchParamType.TOKEN, "Organization identifier");
        }

        private void addPractitionerSearchParameters(CapabilityStatement.CapabilityStatementRestResourceComponent resource) {
            resource.getSearchParam().clear();
            addSearchParam(resource, "name", Enumerations.SearchParamType.STRING, "Practitioner name");
            addSearchParam(resource, "identifier", Enumerations.SearchParamType.TOKEN, "Practitioner identifier");
        }

        private void addSearchParam(CapabilityStatement.CapabilityStatementRestResourceComponent resource,
                                   String name, Enumerations.SearchParamType type, String documentation) {
            CapabilityStatement.CapabilityStatementRestResourceSearchParamComponent param =
                new CapabilityStatement.CapabilityStatementRestResourceSearchParamComponent();
            param.setName(name);
            param.setType(type);
            param.setDocumentation(documentation);
            resource.getSearchParam().add(param);
        }

        private void configureSupportedInteractions(CapabilityStatement.CapabilityStatementRestComponent rest) {
            // Configure system-level interactions
            rest.addInteraction().setCode(CapabilityStatement.SystemRestfulInteraction.TRANSACTION);
            rest.addInteraction().setCode(CapabilityStatement.SystemRestfulInteraction.BATCH);
            rest.addInteraction().setCode(CapabilityStatement.SystemRestfulInteraction.HISTORYSYSTEM);
            rest.addInteraction().setCode(CapabilityStatement.SystemRestfulInteraction.SEARCHSYSTEM);

            // Configure search result parameters
            rest.addSearchParam()
                .setName("_sort")
                .setType(Enumerations.SearchParamType.STRING)
                .setDocumentation("Sort results by field");
            rest.addSearchParam()
                .setName("_count")
                .setType(Enumerations.SearchParamType.NUMBER)
                .setDocumentation("Number of results per page");
            rest.addSearchParam()
                .setName("_include")
                .setType(Enumerations.SearchParamType.STRING)
                .setDocumentation("Include referenced resources");
            rest.addSearchParam()
                .setName("_revinclude")
                .setType(Enumerations.SearchParamType.STRING)
                .setDocumentation("Include resources that reference this resource");
            rest.addSearchParam()
                .setName("_summary")
                .setType(Enumerations.SearchParamType.TOKEN)
                .setDocumentation("Summary mode");
            rest.addSearchParam()
                .setName("_total")
                .setType(Enumerations.SearchParamType.TOKEN)
                .setDocumentation("Include total count");
            rest.addSearchParam()
                .setName("_elements")
                .setType(Enumerations.SearchParamType.STRING)
                .setDocumentation("Include only specified elements");
        }

        private void configureSecurityComponent(CapabilityStatement.CapabilityStatementRestComponent rest) {
            CapabilityStatement.CapabilityStatementRestSecurityComponent security = rest.getSecurity();
            security.setCors(true);
            security.setDescription("OAuth2 authentication required for all write operations. " +
                "Supports role-based access control for refugees, healthcare providers, and administrators.");

            // Add OAuth2 service
            CodeableConcept oauthService = new CodeableConcept();
            oauthService.addCoding()
                .setSystem("http://terminology.hl7.org/CodeSystem/restful-security-service")
                .setCode("OAuth")
                .setDisplay("OAuth2 Token");
            security.getService().add(oauthService);
        }

        private void addCustomOperations(CapabilityStatement cs) {
            CapabilityStatement.CapabilityStatementRestComponent rest = cs.getRest().get(0);

            // Add system-level operations
            CapabilityStatement.CapabilityStatementRestResourceOperationComponent transactionOp =
                new CapabilityStatement.CapabilityStatementRestResourceOperationComponent();
            transactionOp.setName("transaction");
            transactionOp.setDefinition("http://hl7.org/fhir/OperationDefinition/Bundle-transaction");
            transactionOp.setDocumentation("Process a transaction Bundle");
            rest.getOperation().add(transactionOp);

            CapabilityStatement.CapabilityStatementRestResourceOperationComponent historyOp =
                new CapabilityStatement.CapabilityStatementRestResourceOperationComponent();
            historyOp.setName("history-system");
            historyOp.setDefinition("http://hl7.org/fhir/OperationDefinition/Resource-history");
            historyOp.setDocumentation("Retrieve the history of all resources");
            rest.getOperation().add(historyOp);

            CapabilityStatement.CapabilityStatementRestResourceOperationComponent searchOp =
                new CapabilityStatement.CapabilityStatementRestResourceOperationComponent();
            searchOp.setName("search-system");
            searchOp.setDefinition("http://hl7.org/fhir/OperationDefinition/Resource-search");
            searchOp.setDocumentation("Search across all resource types");
            rest.getOperation().add(searchOp);

            CapabilityStatement.CapabilityStatementRestResourceOperationComponent capabilitiesOp =
                new CapabilityStatement.CapabilityStatementRestResourceOperationComponent();
            capabilitiesOp.setName("capabilities");
            capabilitiesOp.setDefinition("http://hl7.org/fhir/OperationDefinition/CapabilityStatement-capabilities");
            capabilitiesOp.setDocumentation("Retrieve server capability statement");
            rest.getOperation().add(capabilitiesOp);

            // Add resource-specific operations
            for (CapabilityStatement.CapabilityStatementRestResourceComponent resource : rest.getResource()) {
                switch (resource.getType()) {
                    case "Patient":
                        // Add $everything operation
                        CapabilityStatement.CapabilityStatementRestResourceOperationComponent everythingOp =
                            new CapabilityStatement.CapabilityStatementRestResourceOperationComponent();
                        everythingOp.setName("everything");
                        everythingOp.setDefinition("http://hl7.org/fhir/OperationDefinition/Patient-everything");
                        everythingOp.setDocumentation("Retrieve all resources related to a patient");
                        resource.getOperation().add(everythingOp);

                        // Add $match operation
                        CapabilityStatement.CapabilityStatementRestResourceOperationComponent matchOp =
                            new CapabilityStatement.CapabilityStatementRestResourceOperationComponent();
                        matchOp.setName("match");
                        matchOp.setDefinition("http://hl7.org/fhir/OperationDefinition/Patient-match");
                        matchOp.setDocumentation("Find patient matches based on demographic criteria");
                        resource.getOperation().add(matchOp);
                        break;

                    case "ValueSet":
                        // Add $expand operation
                        CapabilityStatement.CapabilityStatementRestResourceOperationComponent expandOp =
                            new CapabilityStatement.CapabilityStatementRestResourceOperationComponent();
                        expandOp.setName("expand");
                        expandOp.setDefinition("http://hl7.org/fhir/OperationDefinition/ValueSet-expand");
                        expandOp.setDocumentation("Expand a value set");
                        resource.getOperation().add(expandOp);

                        // Add $validate-code operation
                        CapabilityStatement.CapabilityStatementRestResourceOperationComponent validateCodeOp =
                            new CapabilityStatement.CapabilityStatementRestResourceOperationComponent();
                        validateCodeOp.setName("validate-code");
                        validateCodeOp.setDefinition("http://hl7.org/fhir/OperationDefinition/ValueSet-validate-code");
                        validateCodeOp.setDocumentation("Validate a code against a value set");
                        resource.getOperation().add(validateCodeOp);
                        break;

                    case "CodeSystem":
                        // Add $lookup operation
                        CapabilityStatement.CapabilityStatementRestResourceOperationComponent lookupOp =
                            new CapabilityStatement.CapabilityStatementRestResourceOperationComponent();
                        lookupOp.setName("lookup");
                        lookupOp.setDefinition("http://hl7.org/fhir/OperationDefinition/CodeSystem-lookup");
                        lookupOp.setDocumentation("Look up code system information");
                        resource.getOperation().add(lookupOp);

                        // Add $validate-code operation for CodeSystem
                        CapabilityStatement.CapabilityStatementRestResourceOperationComponent csValidateCodeOp =
                            new CapabilityStatement.CapabilityStatementRestResourceOperationComponent();
                        csValidateCodeOp.setName("validate-code");
                        csValidateCodeOp.setDefinition("http://hl7.org/fhir/OperationDefinition/CodeSystem-validate-code");
                        csValidateCodeOp.setDocumentation("Validate a code in a code system");
                        resource.getOperation().add(csValidateCodeOp);
                        break;

                    case "ConceptMap":
                        // Add $translate operation
                        CapabilityStatement.CapabilityStatementRestResourceOperationComponent translateOp =
                            new CapabilityStatement.CapabilityStatementRestResourceOperationComponent();
                        translateOp.setName("translate");
                        translateOp.setDefinition("http://hl7.org/fhir/OperationDefinition/ConceptMap-translate");
                        translateOp.setDocumentation("Translate codes between systems");
                        resource.getOperation().add(translateOp);
                        break;
                }
            }
        }
    }
}
