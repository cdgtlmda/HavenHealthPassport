package org.havenhealthpassport.interceptor;

import ca.uhn.fhir.interceptor.api.Hook;
import ca.uhn.fhir.interceptor.api.Interceptor;
import ca.uhn.fhir.interceptor.api.Pointcut;
import ca.uhn.fhir.rest.api.RestOperationTypeEnum;
import ca.uhn.fhir.rest.api.server.RequestDetails;
import ca.uhn.fhir.rest.server.exceptions.AuthenticationException;
import ca.uhn.fhir.rest.server.exceptions.ForbiddenOperationException;
import ca.uhn.fhir.rest.server.interceptor.auth.AuthorizationInterceptor;
import ca.uhn.fhir.rest.server.interceptor.auth.IAuthRule;
import ca.uhn.fhir.rest.server.interceptor.auth.RuleBuilder;
import org.apache.commons.lang3.StringUtils;
import org.hl7.fhir.instance.model.api.IBaseResource;
import org.hl7.fhir.instance.model.api.IIdType;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.util.*;

/**
 * Haven Health Passport Authorization Interceptor
 *
 * This interceptor integrates with the Python authorization service to provide
 * fine-grained access control for FHIR resources.
 */
@Component
@Interceptor
public class HavenAuthorizationInterceptor extends AuthorizationInterceptor {

    private static final Logger logger = LoggerFactory.getLogger(HavenAuthorizationInterceptor.class);

    @Value("${hapi.fhir.security.token_endpoint:http://localhost:8000/api/v1/auth/validate}")
    private String tokenEndpoint;

    @Value("${hapi.fhir.security.oauth2.enabled:false}")
    private boolean authEnabled;

    @Value("${hapi.fhir.security.allow_anonymous_read:false}")
    private boolean allowAnonymousRead;

    private final RestTemplate restTemplate = new RestTemplate();

    /**
     * Build authorization rules based on the user's token claims
     */
    @Override
    public List<IAuthRule> buildRuleList(RequestDetails theRequestDetails) {
        // If auth is disabled, allow all operations
        if (!authEnabled) {
            return new RuleBuilder()
                .allowAll()
                .build();
        }

        // Extract authorization header
        String authHeader = theRequestDetails.getHeader("Authorization");

        // Handle anonymous access
        if (StringUtils.isBlank(authHeader)) {
            if (allowAnonymousRead && isReadOperation(theRequestDetails)) {
                return new RuleBuilder()
                    .allow().read().allResources().withAnyId()
                    .build();
            } else {
                throw new AuthenticationException("Authorization header required");
            }
        }

        // Validate token with Python service
        TokenValidationResponse tokenResponse = validateToken(authHeader);
        if (tokenResponse == null || !tokenResponse.isValid()) {
            throw new AuthenticationException("Invalid or expired token");
        }

        // Store token claims in request for downstream use
        theRequestDetails.getUserData().put("tokenClaims", tokenResponse);

        // Build rules based on user roles
        return buildRulesForUser(tokenResponse);
    }

    /**
     * Hook to check authorization before resource operations
     */
    @Hook(Pointcut.SERVER_INCOMING_REQUEST_PRE_HANDLED)
    public void checkAuthorization(RequestDetails theRequestDetails) {
        if (!authEnabled) {
            return;
        }

        // Get token claims from request
        TokenValidationResponse tokenClaims = (TokenValidationResponse) theRequestDetails.getUserData().get("tokenClaims");
        if (tokenClaims == null && !allowAnonymousRead) {
            throw new ForbiddenOperationException("No authorization context found");
        }

        // Log authorization check
        logger.debug("Authorization check for user: {} on resource: {} operation: {}",
            tokenClaims != null ? tokenClaims.getUserId() : "anonymous",
            theRequestDetails.getResourceName(),
            theRequestDetails.getRestOperationType());
    }

    /**
     * Validate token with Python authorization service
     */
    private TokenValidationResponse validateToken(String authHeader) {
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.set("Authorization", authHeader);
            headers.setContentType(MediaType.APPLICATION_JSON);

            HttpEntity<String> entity = new HttpEntity<>(headers);

            ResponseEntity<TokenValidationResponse> response = restTemplate.exchange(
                tokenEndpoint,
                HttpMethod.POST,
                entity,
                TokenValidationResponse.class
            );

            return response.getBody();
        } catch (Exception e) {
            logger.error("Token validation failed: {}", e.getMessage());
            return null;
        }
    }

    /**
     * Build authorization rules based on user roles
     */
    private List<IAuthRule> buildRulesForUser(TokenValidationResponse tokenResponse) {
        RuleBuilder rules = new RuleBuilder();

        // Admin role - full access
        if (tokenResponse.getRoles().contains("admin")) {
            return rules
                .allowAll()
                .build();
        }

        // Patient role - access to own records
        if (tokenResponse.getRoles().contains("patient")) {
            String patientId = tokenResponse.getUserId();

            rules
                // Read own patient record
                .allow().read().resourcesOfType("Patient").inCompartment("Patient", new IdType("Patient", patientId))
                // Read own observations
                .allow().read().resourcesOfType("Observation").inCompartment("Patient", new IdType("Patient", patientId))
                // Read own conditions
                .allow().read().resourcesOfType("Condition").inCompartment("Patient", new IdType("Patient", patientId))
                // Read own medications
                .allow().read().resourcesOfType("MedicationRequest").inCompartment("Patient", new IdType("Patient", patientId))
                // Read own procedures
                .allow().read().resourcesOfType("Procedure").inCompartment("Patient", new IdType("Patient", patientId))
                // Read own documents
                .allow().read().resourcesOfType("DocumentReference").inCompartment("Patient", new IdType("Patient", patientId))
                // Create own documents
                .allow().write().resourcesOfType("DocumentReference").inCompartment("Patient", new IdType("Patient", patientId))
                // Read own allergies
                .allow().read().resourcesOfType("AllergyIntolerance").inCompartment("Patient", new IdType("Patient", patientId))
                // Read own immunizations
                .allow().read().resourcesOfType("Immunization").inCompartment("Patient", new IdType("Patient", patientId));
        }

        // Practitioner role - broader access
        if (tokenResponse.getRoles().contains("practitioner")) {
            rules
                // Read all patients
                .allow().read().resourcesOfType("Patient").withAnyId()
                // Create and update observations
                .allow().write().resourcesOfType("Observation").withAnyId()
                // Create and update conditions
                .allow().write().resourcesOfType("Condition").withAnyId()
                // Create, update, and delete medication requests
                .allow().write().resourcesOfType("MedicationRequest").withAnyId()
                .allow().delete().resourcesOfType("MedicationRequest").withAnyId()
                // Create and update procedures
                .allow().write().resourcesOfType("Procedure").withAnyId()
                // Search operations
                .allow().operation().named("$search").onAnyType().andAllowAllResponses();
        }

        // Emergency responder role - read-only critical info
        if (tokenResponse.getRoles().contains("emergency_responder")) {
            rules
                // Read patient demographics
                .allow().read().resourcesOfType("Patient").withAnyId()
                // Read allergies
                .allow().read().resourcesOfType("AllergyIntolerance").withAnyId()
                // Read critical conditions
                .allow().read().resourcesOfType("Condition").withAnyId()
                // Read active medications
                .allow().read().resourcesOfType("MedicationRequest").withAnyId();
        }

        // Caregiver role - limited access
        if (tokenResponse.getRoles().contains("caregiver")) {
            // Caregivers need specific patient assignments
            List<String> assignedPatients = tokenResponse.getAssignedPatients();
            if (assignedPatients != null) {
                for (String patientId : assignedPatients) {
                    rules
                        .allow().read().resourcesOfType("Patient").inCompartment("Patient", new IdType("Patient", patientId))
                        .allow().read().resourcesOfType("Observation").inCompartment("Patient", new IdType("Patient", patientId))
                        .allow().read().resourcesOfType("MedicationRequest").inCompartment("Patient", new IdType("Patient", patientId));
                }
            }
        }

        // Default deny all other operations
        rules.denyAll();

        return rules.build();
    }

    /**
     * Check if the operation is a read operation
     */
    private boolean isReadOperation(RequestDetails theRequestDetails) {
        RestOperationTypeEnum operationType = theRequestDetails.getRestOperationType();
        return operationType == RestOperationTypeEnum.READ ||
               operationType == RestOperationTypeEnum.VREAD ||
               operationType == RestOperationTypeEnum.SEARCH_TYPE ||
               operationType == RestOperationTypeEnum.SEARCH_SYSTEM ||
               operationType == RestOperationTypeEnum.HISTORY_INSTANCE ||
               operationType == RestOperationTypeEnum.HISTORY_TYPE ||
               operationType == RestOperationTypeEnum.HISTORY_SYSTEM;
    }

    /**
     * Token validation response from Python service
     */
    public static class TokenValidationResponse {
        private boolean valid;
        private String userId;
        private List<String> roles;
        private List<String> scopes;
        private List<String> assignedPatients;
        private Map<String, Object> attributes;

        // Getters and setters
        public boolean isValid() { return valid; }
        public void setValid(boolean valid) { this.valid = valid; }

        public String getUserId() { return userId; }
        public void setUserId(String userId) { this.userId = userId; }

        public List<String> getRoles() { return roles != null ? roles : new ArrayList<>(); }
        public void setRoles(List<String> roles) { this.roles = roles; }

        public List<String> getScopes() { return scopes != null ? scopes : new ArrayList<>(); }
        public void setScopes(List<String> scopes) { this.scopes = scopes; }

        public List<String> getAssignedPatients() { return assignedPatients; }
        public void setAssignedPatients(List<String> assignedPatients) { this.assignedPatients = assignedPatients; }

        public Map<String, Object> getAttributes() { return attributes; }
        public void setAttributes(Map<String, Object> attributes) { this.attributes = attributes; }
    }

    /**
     * Helper class for ID types
     */
    private static class IdType implements IIdType {
        private final String resourceType;
        private final String id;

        public IdType(String resourceType, String id) {
            this.resourceType = resourceType;
            this.id = id;
        }

        @Override
        public String getValue() {
            return resourceType + "/" + id;
        }

        @Override
        public String getIdPart() {
            return id;
        }

        @Override
        public String getResourceType() {
            return resourceType;
        }

        // Other required interface methods with default implementations
        @Override
        public boolean hasIdPart() { return true; }

        @Override
        public boolean hasResourceType() { return true; }

        @Override
        public boolean hasVersionIdPart() { return false; }

        @Override
        public String getVersionIdPart() { return null; }

        @Override
        public IIdType toUnqualifiedVersionless() { return this; }

        @Override
        public IIdType toVersionless() { return this; }

        @Override
        public IIdType withResourceType(String theResourceType) {
            return new IdType(theResourceType, id);
        }

        @Override
        public IIdType withServerBase(String theServerBase, String theResourceType) {
            return this;
        }

        @Override
        public IIdType withVersion(String theVersion) {
            return this;
        }

        @Override
        public Long getIdPartAsLong() {
            try {
                return Long.parseLong(id);
            } catch (NumberFormatException e) {
                return null;
            }
        }

        @Override
        public String getBaseUrl() { return null; }

        @Override
        public boolean isAbsolute() { return false; }

        @Override
        public boolean isIdPartValidLong() {
            try {
                Long.parseLong(id);
                return true;
            } catch (NumberFormatException e) {
                return false;
            }
        }

        @Override
        public boolean isLocal() { return false; }

        @Override
        public IIdType toUnqualified() { return this; }

        @Override
        public boolean hasBaseUrl() { return false; }

        @Override
        public boolean isEmpty() { return false; }

        @Override
        public IIdType setParts(String theBaseUrl, String theResourceType, String theIdPart, String theVersionIdPart) {
            return this;
        }
    }
}
