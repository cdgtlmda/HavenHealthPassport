package org.havenhealthpassport.config;

import ca.uhn.fhir.rest.server.RestfulServer;
import org.havenhealthpassport.interceptor.HavenAuthorizationInterceptor;
import org.havenhealthpassport.provider.ConformanceResourceProvider;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.event.ContextRefreshedEvent;
import org.springframework.context.event.EventListener;

/**
 * Haven Health Passport FHIR Server Configuration
 *
 * This configuration class registers custom interceptors with the HAPI FHIR server.
 */
@Configuration
public class HavenFhirServerConfig {

    @Autowired
    private RestfulServer restfulServer;

    @Autowired
    private HavenAuthorizationInterceptor authorizationInterceptor;

    @Autowired(required = false)
    private ConformanceResourceProvider.StructureDefinitionProvider structureDefinitionProvider;

    @Autowired(required = false)
    private ConformanceResourceProvider.SearchParameterProvider searchParameterProvider;

    @Autowired(required = false)
    private ConformanceResourceProvider.ValueSetProvider valueSetProvider;

    @Autowired(required = false)
    private ConformanceResourceProvider.CodeSystemProvider codeSystemProvider;

    /**
     * Register interceptors and conformance resource providers when the Spring context is ready
     */
    @EventListener(ContextRefreshedEvent.class)
    public void configureServer() {
        // Register the authorization interceptor
        restfulServer.registerInterceptor(authorizationInterceptor);
        System.out.println("Haven Health Passport Authorization Interceptor registered successfully");

        // Register conformance resource providers
        registerConformanceResourceProviders();
    }

    /**
     * Register conformance resource providers
     */
    private void registerConformanceResourceProviders() {
        if (structureDefinitionProvider != null) {
            restfulServer.registerProvider(structureDefinitionProvider);
            System.out.println("StructureDefinition provider registered");
        }

        if (searchParameterProvider != null) {
            restfulServer.registerProvider(searchParameterProvider);
            System.out.println("SearchParameter provider registered");
        }

        if (valueSetProvider != null) {
            restfulServer.registerProvider(valueSetProvider);
            System.out.println("ValueSet provider registered");
        }

        if (codeSystemProvider != null) {
            restfulServer.registerProvider(codeSystemProvider);
            System.out.println("CodeSystem provider registered");
        }

        System.out.println("Conformance resource providers registration complete");
    }
}
