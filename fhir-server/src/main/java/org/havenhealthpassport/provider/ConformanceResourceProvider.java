package org.havenhealthpassport.provider;

import ca.uhn.fhir.rest.annotation.IdParam;
import ca.uhn.fhir.rest.annotation.Read;
import ca.uhn.fhir.rest.annotation.Search;
import ca.uhn.fhir.rest.server.IResourceProvider;
import ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException;
import org.hl7.fhir.instance.model.api.IBaseResource;
import org.hl7.fhir.r4.model.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.*;

/**
 * Provider for conformance resources including StructureDefinitions,
 * SearchParameters, ValueSets, and CodeSystems
 */
@Component
public class ConformanceResourceProvider {

    private static final Logger logger = LoggerFactory.getLogger(ConformanceResourceProvider.class);

    /**
     * StructureDefinition Provider
     */
    @Component
    public static class StructureDefinitionProvider implements IResourceProvider {

        private final Map<String, StructureDefinition> structureDefinitions = new HashMap<>();

        public StructureDefinitionProvider() {
            initializeStructureDefinitions();
        }

        @Override
        public Class<? extends IBaseResource> getResourceType() {
            return StructureDefinition.class;
        }

        @Read
        public StructureDefinition read(@IdParam IdType theId) {
            StructureDefinition sd = structureDefinitions.get(theId.getIdPart());
            if (sd == null) {
                throw new ResourceNotFoundException(theId);
            }
            return sd;
        }

        @Search
        public List<StructureDefinition> search() {
            return new ArrayList<>(structureDefinitions.values());
        }
        private void initializeStructureDefinitions() {
            // Create custom Patient profile for refugees
            StructureDefinition refugeePatient = new StructureDefinition();
            refugeePatient.setId("refugee-patient");
            refugeePatient.setUrl("https://havenhealthpassport.org/fhir/StructureDefinition/refugee-patient");
            refugeePatient.setName("RefugeePatient");
            refugeePatient.setTitle("Refugee Patient Profile");
            refugeePatient.setStatus(Enumerations.PublicationStatus.ACTIVE);
            refugeePatient.setKind(StructureDefinition.StructureDefinitionKind.RESOURCE);
            refugeePatient.setAbstract(false);
            refugeePatient.setType("Patient");
            refugeePatient.setBaseDefinition("http://hl7.org/fhir/StructureDefinition/Patient");
            refugeePatient.setDerivation(StructureDefinition.TypeDerivationRule.CONSTRAINT);
            refugeePatient.setDescription("Patient profile for refugees with additional refugee-specific extensions");

            // Add refugee-specific extensions
            ElementDefinition refugeeStatus = new ElementDefinition();
            refugeeStatus.setId("Patient.extension:refugeeStatus");
            refugeeStatus.setPath("Patient.extension");
            refugeeStatus.setSliceName("refugeeStatus");
            refugeeStatus.setMin(0);
            refugeeStatus.setMax("1");
            refugeeStatus.setType(Collections.singletonList(new ElementDefinition.TypeRefComponent().setCode("Extension")));

            ElementDefinition campLocation = new ElementDefinition();
            campLocation.setId("Patient.extension:campLocation");
            campLocation.setPath("Patient.extension");
            campLocation.setSliceName("campLocation");
            campLocation.setMin(0);
            campLocation.setMax("1");
            campLocation.setType(Collections.singletonList(new ElementDefinition.TypeRefComponent().setCode("Extension")));

            refugeePatient.getDifferential().addElement(refugeeStatus);
            refugeePatient.getDifferential().addElement(campLocation);

            structureDefinitions.put("refugee-patient", refugeePatient);

            logger.info("Initialized {} StructureDefinitions", structureDefinitions.size());
        }
    }
    /**
     * SearchParameter Provider
     */
    @Component
    public static class SearchParameterProvider implements IResourceProvider {

        private final Map<String, SearchParameter> searchParameters = new HashMap<>();

        public SearchParameterProvider() {
            initializeSearchParameters();
        }

        @Override
        public Class<? extends IBaseResource> getResourceType() {
            return SearchParameter.class;
        }

        @Read
        public SearchParameter read(@IdParam IdType theId) {
            SearchParameter sp = searchParameters.get(theId.getIdPart());
            if (sp == null) {
                throw new ResourceNotFoundException(theId);
            }
            return sp;
        }

        @Search
        public List<SearchParameter> search() {
            return new ArrayList<>(searchParameters.values());
        }
        private void initializeSearchParameters() {
            // Create custom search parameter for refugee status
            SearchParameter refugeeStatus = new SearchParameter();
            refugeeStatus.setId("patient-refugee-status");
            refugeeStatus.setUrl("https://havenhealthpassport.org/fhir/SearchParameter/patient-refugee-status");
            refugeeStatus.setName("refugee-status");
            refugeeStatus.setStatus(Enumerations.PublicationStatus.ACTIVE);
            refugeeStatus.setDescription("Search by refugee status");
            refugeeStatus.setCode("refugee-status");
            refugeeStatus.addBase("Patient");
            refugeeStatus.setType(Enumerations.SearchParamType.TOKEN);
            refugeeStatus.setExpression("Patient.extension('https://havenhealthpassport.org/fhir/StructureDefinition/refugee-status')");
            refugeeStatus.setXpath("f:Patient/f:extension[@url='https://havenhealthpassport.org/fhir/StructureDefinition/refugee-status']");
            refugeeStatus.setXpathUsage(SearchParameter.XPathUsageType.NORMAL);

            searchParameters.put("patient-refugee-status", refugeeStatus);

            // Create custom search parameter for camp location
            SearchParameter campLocation = new SearchParameter();
            campLocation.setId("patient-camp-location");
            campLocation.setUrl("https://havenhealthpassport.org/fhir/SearchParameter/patient-camp-location");
            campLocation.setName("camp-location");
            campLocation.setStatus(Enumerations.PublicationStatus.ACTIVE);
            campLocation.setDescription("Search by refugee camp location");
            campLocation.setCode("camp-location");
            campLocation.addBase("Patient");
            campLocation.setType(Enumerations.SearchParamType.TOKEN);
            campLocation.setExpression("Patient.extension('https://havenhealthpassport.org/fhir/StructureDefinition/camp-location')");
            campLocation.setXpath("f:Patient/f:extension[@url='https://havenhealthpassport.org/fhir/StructureDefinition/camp-location']");
            campLocation.setXpathUsage(SearchParameter.XPathUsageType.NORMAL);

            searchParameters.put("patient-camp-location", campLocation);

            logger.info("Initialized {} SearchParameters", searchParameters.size());
        }
    }
    /**
     * ValueSet Provider
     */
    @Component
    public static class ValueSetProvider implements IResourceProvider {

        private final Map<String, ValueSet> valueSets = new HashMap<>();

        public ValueSetProvider() {
            initializeValueSets();
        }

        @Override
        public Class<? extends IBaseResource> getResourceType() {
            return ValueSet.class;
        }

        @Read
        public ValueSet read(@IdParam IdType theId) {
            ValueSet vs = valueSets.get(theId.getIdPart());
            if (vs == null) {
                throw new ResourceNotFoundException(theId);
            }
            return vs;
        }

        @Search
        public List<ValueSet> search() {
            return new ArrayList<>(valueSets.values());
        }
        private void initializeValueSets() {
            // Create refugee status value set
            ValueSet refugeeStatusVS = new ValueSet();
            refugeeStatusVS.setId("refugee-status-valueset");
            refugeeStatusVS.setUrl("https://havenhealthpassport.org/fhir/ValueSet/refugee-status");
            refugeeStatusVS.setName("RefugeeStatusValueSet");
            refugeeStatusVS.setTitle("Refugee Status Value Set");
            refugeeStatusVS.setStatus(Enumerations.PublicationStatus.ACTIVE);
            refugeeStatusVS.setDescription("Codes representing refugee status");
            refugeeStatusVS.setExperimental(false);

            ValueSet.ValueSetComposeComponent compose = new ValueSet.ValueSetComposeComponent();
            ValueSet.ConceptSetComponent conceptSet = new ValueSet.ConceptSetComponent();
            conceptSet.setSystem("https://havenhealthpassport.org/fhir/CodeSystem/refugee-status");
            conceptSet.addConcept().setCode("refugee").setDisplay("Refugee");
            conceptSet.addConcept().setCode("asylum-seeker").setDisplay("Asylum Seeker");
            conceptSet.addConcept().setCode("internally-displaced").setDisplay("Internally Displaced Person");
            conceptSet.addConcept().setCode("stateless").setDisplay("Stateless Person");
            conceptSet.addConcept().setCode("returnee").setDisplay("Returnee");
            compose.addInclude(conceptSet);
            refugeeStatusVS.setCompose(compose);

            valueSets.put("refugee-status-valueset", refugeeStatusVS);
            // Create camp location value set
            ValueSet campLocationVS = new ValueSet();
            campLocationVS.setId("camp-location-valueset");
            campLocationVS.setUrl("https://havenhealthpassport.org/fhir/ValueSet/camp-location");
            campLocationVS.setName("CampLocationValueSet");
            campLocationVS.setTitle("Refugee Camp Location Value Set");
            campLocationVS.setStatus(Enumerations.PublicationStatus.ACTIVE);
            campLocationVS.setDescription("Codes representing refugee camp locations");
            campLocationVS.setExperimental(false);

            ValueSet.ValueSetComposeComponent campCompose = new ValueSet.ValueSetComposeComponent();
            ValueSet.ConceptSetComponent campConceptSet = new ValueSet.ConceptSetComponent();
            campConceptSet.setSystem("https://havenhealthpassport.org/fhir/CodeSystem/camp-location");
            // Add example camp locations
            campConceptSet.addConcept().setCode("kakuma").setDisplay("Kakuma Refugee Camp");
            campConceptSet.addConcept().setCode("dadaab").setDisplay("Dadaab Refugee Complex");
            campConceptSet.addConcept().setCode("zaatari").setDisplay("Zaatari Refugee Camp");
            campConceptSet.addConcept().setCode("cox-bazar").setDisplay("Cox's Bazar");
            campCompose.addInclude(campConceptSet);
            campLocationVS.setCompose(campCompose);

            valueSets.put("camp-location-valueset", campLocationVS);

            logger.info("Initialized {} ValueSets", valueSets.size());
        }
    }
    /**
     * CodeSystem Provider
     */
    @Component
    public static class CodeSystemProvider implements IResourceProvider {

        private final Map<String, CodeSystem> codeSystems = new HashMap<>();

        public CodeSystemProvider() {
            initializeCodeSystems();
        }

        @Override
        public Class<? extends IBaseResource> getResourceType() {
            return CodeSystem.class;
        }

        @Read
        public CodeSystem read(@IdParam IdType theId) {
            CodeSystem cs = codeSystems.get(theId.getIdPart());
            if (cs == null) {
                throw new ResourceNotFoundException(theId);
            }
            return cs;
        }

        @Search
        public List<CodeSystem> search() {
            return new ArrayList<>(codeSystems.values());
        }
        private void initializeCodeSystems() {
            // Create refugee status code system
            CodeSystem refugeeStatusCS = new CodeSystem();
            refugeeStatusCS.setId("refugee-status-codesystem");
            refugeeStatusCS.setUrl("https://havenhealthpassport.org/fhir/CodeSystem/refugee-status");
            refugeeStatusCS.setName("RefugeeStatusCodeSystem");
            refugeeStatusCS.setTitle("Refugee Status Code System");
            refugeeStatusCS.setStatus(Enumerations.PublicationStatus.ACTIVE);
            refugeeStatusCS.setContent(CodeSystem.CodeSystemContentMode.COMPLETE);
            refugeeStatusCS.setDescription("Code system for refugee status");
            refugeeStatusCS.setCount(5);

            refugeeStatusCS.addConcept()
                .setCode("refugee")
                .setDisplay("Refugee")
                .setDefinition("Person who has been forced to flee their country due to persecution, war, or violence");

            refugeeStatusCS.addConcept()
                .setCode("asylum-seeker")
                .setDisplay("Asylum Seeker")
                .setDefinition("Person who has left their country seeking protection but whose claim has not yet been assessed");

            refugeeStatusCS.addConcept()
                .setCode("internally-displaced")
                .setDisplay("Internally Displaced Person")
                .setDefinition("Person forced to flee their home but remains within their country's borders");

            refugeeStatusCS.addConcept()
                .setCode("stateless")
                .setDisplay("Stateless Person")
                .setDefinition("Person not considered a national by any state");

            refugeeStatusCS.addConcept()
                .setCode("returnee")
                .setDisplay("Returnee")
                .setDefinition("Former refugee who has returned to their country of origin");

            codeSystems.put("refugee-status-codesystem", refugeeStatusCS);
            // Create camp location code system
            CodeSystem campLocationCS = new CodeSystem();
            campLocationCS.setId("camp-location-codesystem");
            campLocationCS.setUrl("https://havenhealthpassport.org/fhir/CodeSystem/camp-location");
            campLocationCS.setName("CampLocationCodeSystem");
            campLocationCS.setTitle("Refugee Camp Location Code System");
            campLocationCS.setStatus(Enumerations.PublicationStatus.ACTIVE);
            campLocationCS.setContent(CodeSystem.CodeSystemContentMode.COMPLETE);
            campLocationCS.setDescription("Code system for refugee camp locations");
            campLocationCS.setCount(4);

            campLocationCS.addConcept()
                .setCode("kakuma")
                .setDisplay("Kakuma Refugee Camp")
                .setDefinition("Kakuma refugee camp in northwestern Kenya");

            campLocationCS.addConcept()
                .setCode("dadaab")
                .setDisplay("Dadaab Refugee Complex")
                .setDefinition("Dadaab refugee complex in eastern Kenya");

            campLocationCS.addConcept()
                .setCode("zaatari")
                .setDisplay("Zaatari Refugee Camp")
                .setDefinition("Zaatari refugee camp in northern Jordan");

            campLocationCS.addConcept()
                .setCode("cox-bazar")
                .setDisplay("Cox's Bazar")
                .setDefinition("Cox's Bazar refugee settlement in Bangladesh");

            codeSystems.put("camp-location-codesystem", campLocationCS);

            logger.info("Initialized {} CodeSystems", codeSystems.size());
        }
    }
}
