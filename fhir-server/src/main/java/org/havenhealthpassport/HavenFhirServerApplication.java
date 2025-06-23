package org.havenhealthpassport;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.ComponentScan;

/**
 * Main Spring Boot Application for Haven Health Passport FHIR Server
 */
@SpringBootApplication
@ComponentScan(basePackages = {
    "org.havenhealthpassport.config",
    "org.havenhealthpassport.provider",
    "org.havenhealthpassport.interceptor",
    "org.havenhealthpassport.terminology"
})
public class HavenFhirServerApplication {

    public static void main(String[] args) {
        SpringApplication.run(HavenFhirServerApplication.class, args);
    }
}
