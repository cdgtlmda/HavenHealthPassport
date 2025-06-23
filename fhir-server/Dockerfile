# Custom HAPI FHIR Server with Haven Health Passport Authorization
FROM hapiproject/hapi:latest AS base

# Install Maven for building custom interceptors
FROM maven:3.9-eclipse-temurin-17 AS builder

# Copy source code
WORKDIR /build
COPY ./src ./src
COPY ./pom.xml ./pom.xml

# Build the custom interceptor JAR
RUN mvn clean package

# Final image
FROM base

# Copy custom JAR to HAPI FHIR server classpath
COPY --from=builder /build/target/haven-fhir-server-1.0.0.jar /app/libs/

# Create directories for terminology
RUN mkdir -p /app/terminology/loinc && \
    mkdir -p /app/terminology/snomed && \
    mkdir -p /app/terminology/icd10 && \
    mkdir -p /app/terminology/rxnorm && \
    mkdir -p /app/data/terminology-index

# Copy configuration files
COPY ./config/application.yaml /app/config/application.yaml
COPY ./config/auth-config.yaml /app/config/auth-config.yaml
COPY ./config/transaction-config.yaml /app/config/transaction-config.yaml
COPY ./config/terminology-config.yaml /app/config/terminology-config.yaml
COPY ./config/conformance-config.yaml /app/config/conformance-config.yaml

# Set environment variables for authorization
ENV FHIR_AUTH_ENABLED=true
ENV JAVA_OPTS="-Xmx2g -Dspring.config.location=/app/config/application.yaml,/app/config/auth-config.yaml,/app/config/transaction-config.yaml,/app/config/terminology-config.yaml,/app/config/conformance-config.yaml"

# Add custom classpath
ENV CLASSPATH="/app/libs/*:${CLASSPATH}"

# Expose FHIR server port
EXPOSE 8080

# Start HAPI FHIR server with custom configuration
CMD ["java", "-cp", "/app/*:/app/libs/*", "ca.uhn.fhir.jpa.starter.Application"]
