package org.havenhealthpassport.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.PropertySource;

/**
 * Configuration class to load FHIR conformance configuration
 */
@Configuration
@EnableConfigurationProperties
@PropertySource("classpath:config/conformance-config.yaml")
public class ConformanceConfiguration {

    // This class enables the loading of conformance-config.yaml
    // The actual configuration is applied in HavenCapabilityStatementConfig
}
