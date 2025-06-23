package org.havenhealthpassport.provider;

import org.hl7.fhir.r4.model.*;
import org.springframework.stereotype.Component;

import java.util.*;

/**
 * Extension definitions for Haven Health Passport
 */
@Component
public class ExtensionDefinitionProvider {

    private final Map<String, StructureDefinition> extensionDefinitions = new HashMap<>();

    public ExtensionDefinitionProvider() {
        initializeExtensions();
    }

    public Map<String, StructureDefinition> getExtensions() {
        return Collections.unmodifiableMap(extensionDefinitions);
    }

    private void initializeExtensions() {
        createRefugeeStatusExtension();
        createCampLocationExtension();
    }
    private void createRefugeeStatusExtension() {
        StructureDefinition refugeeStatusExt = new StructureDefinition();
        refugeeStatusExt.setId("refugee-status");
        refugeeStatusExt.setUrl("https://havenhealthpassport.org/fhir/StructureDefinition/refugee-status");
        refugeeStatusExt.setName("RefugeeStatus");
        refugeeStatusExt.setTitle("Refugee Status Extension");
        refugeeStatusExt.setStatus(Enumerations.PublicationStatus.ACTIVE);
        refugeeStatusExt.setKind(StructureDefinition.StructureDefinitionKind.COMPLEXTYPE);
        refugeeStatusExt.setAbstract(false);
        refugeeStatusExt.setType("Extension");
        refugeeStatusExt.setBaseDefinition("http://hl7.org/fhir/StructureDefinition/Extension");
        refugeeStatusExt.setDerivation(StructureDefinition.TypeDerivationRule.CONSTRAINT);
        refugeeStatusExt.setDescription("Extension to capture refugee status information");

        // Add context
        StructureDefinition.StructureDefinitionContextComponent context = new StructureDefinition.StructureDefinitionContextComponent();
        context.setType(StructureDefinition.ExtensionContextType.ELEMENT);
        context.setExpression("Patient");
        refugeeStatusExt.addContext(context);

        // Define the extension structure
        ElementDefinition root = new ElementDefinition();
        root.setId("Extension");
        root.setPath("Extension");
        root.setShort("Refugee status");
        root.setDefinition("The refugee status of the patient");
        root.setMin(0);
        root.setMax("1");

        ElementDefinition value = new ElementDefinition();
        value.setId("Extension.value[x]");
        value.setPath("Extension.value[x]");
        value.setShort("Refugee status code");
        value.setDefinition("Code representing the refugee status");
        value.setMin(1);
        value.setMax("1");
        value.setType(Collections.singletonList(new ElementDefinition.TypeRefComponent()
            .setCode("CodeableConcept")));
        value.setBinding(new ElementDefinition.ElementDefinitionBindingComponent()
            .setStrength(Enumerations.BindingStrength.REQUIRED)
            .setValueSet("https://havenhealthpassport.org/fhir/ValueSet/refugee-status"));

        refugeeStatusExt.getDifferential().addElement(root);
        refugeeStatusExt.getDifferential().addElement(value);

        extensionDefinitions.put("refugee-status", refugeeStatusExt);
    }
    private void createCampLocationExtension() {
        StructureDefinition campLocationExt = new StructureDefinition();
        campLocationExt.setId("camp-location");
        campLocationExt.setUrl("https://havenhealthpassport.org/fhir/StructureDefinition/camp-location");
        campLocationExt.setName("CampLocation");
        campLocationExt.setTitle("Refugee Camp Location Extension");
        campLocationExt.setStatus(Enumerations.PublicationStatus.ACTIVE);
        campLocationExt.setKind(StructureDefinition.StructureDefinitionKind.COMPLEXTYPE);
        campLocationExt.setAbstract(false);
        campLocationExt.setType("Extension");
        campLocationExt.setBaseDefinition("http://hl7.org/fhir/StructureDefinition/Extension");
        campLocationExt.setDerivation(StructureDefinition.TypeDerivationRule.CONSTRAINT);
        campLocationExt.setDescription("Extension to capture refugee camp location information");

        // Add context
        StructureDefinition.StructureDefinitionContextComponent context = new StructureDefinition.StructureDefinitionContextComponent();
        context.setType(StructureDefinition.ExtensionContextType.ELEMENT);
        context.setExpression("Patient");
        campLocationExt.addContext(context);

        // Define the extension structure
        ElementDefinition root = new ElementDefinition();
        root.setId("Extension");
        root.setPath("Extension");
        root.setShort("Camp location");
        root.setDefinition("The refugee camp location where the patient resides");
        root.setMin(0);
        root.setMax("1");

        ElementDefinition value = new ElementDefinition();
        value.setId("Extension.value[x]");
        value.setPath("Extension.value[x]");
        value.setShort("Camp location code");
        value.setDefinition("Code representing the refugee camp location");
        value.setMin(1);
        value.setMax("1");
        value.setType(Collections.singletonList(new ElementDefinition.TypeRefComponent()
            .setCode("CodeableConcept")));
        value.setBinding(new ElementDefinition.ElementDefinitionBindingComponent()
            .setStrength(Enumerations.BindingStrength.EXTENSIBLE)
            .setValueSet("https://havenhealthpassport.org/fhir/ValueSet/camp-location"));

        campLocationExt.getDifferential().addElement(root);
        campLocationExt.getDifferential().addElement(value);

        extensionDefinitions.put("camp-location", campLocationExt);
    }
}
