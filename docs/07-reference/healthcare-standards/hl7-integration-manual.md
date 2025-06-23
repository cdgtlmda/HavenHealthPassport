# HL7 Integration Manual

## Overview

Haven Health Passport supports HL7 v2.x messaging for integration with legacy healthcare systems. This manual covers message parsing, transformation, routing, and the bidirectional mapping between HL7 v2 and FHIR resources.

## HL7 v2 Message Structure

### Message Components

```
MSH|^~\&|SENDING_APP|SENDING_FAC|RECEIVING_APP|RECEIVING_FAC|20240531120000||ADT^A01|MSG00001|P|2.5
EVN|A01|20240531120000
PID|1||123456^^^HAVEN^MR||DOE^JOHN^A||19800101|M||W|123 MAIN ST^^CITY^STATE^12345||(555)123-4567|||M|NONE|987654321
NK1|1|DOE^JANE|SPOUSE
PV1|1|I|ICU^101^A||||1234^SMITH^JOHN^MD|||MED||||||||ADM|A0
```

### Segment Definitions

| Segment | Purpose | Required Fields |
|---------|---------|-----------------|
| MSH | Message Header | Field separator, encoding chars, sending/receiving info |
| PID | Patient Identification | Patient ID, name, DOB, gender |
| PV1 | Patient Visit | Admission type, location, attending physician |
| OBR | Observation Request | Order info, test codes, priority |
| OBX | Observation Result | Result type, value, units, reference range |
| NK1 | Next of Kin | Relationship, contact info |

## Message Types Implementation

### ADT (Admission, Discharge, Transfer)

```python
class ADTMessageHandler:
    """Handler for ADT message types"""

    MESSAGE_EVENTS = {
        "A01": "admission",
        "A02": "transfer",
        "A03": "discharge",
        "A04": "register_outpatient",
        "A05": "pre_admission",
        "A08": "update_patient",
        "A11": "cancel_admission",
        "A13": "cancel_discharge"
    }

    def process_adt_message(self, message):
        """Process incoming ADT message"""

        # Parse message
        parsed = self.parser.parse(message)
        event_type = parsed.get_segment("MSH").get_field(9).split("^")[1]

        # Extract patient data
        patient_data = self.extract_patient_data(parsed)

        # Handle specific event
        handler = getattr(self, f"handle_{self.MESSAGE_EVENTS[event_type]}")
        result = handler(patient_data, parsed)

        # Generate acknowledgment
        return self.generate_ack(parsed, result)

    def extract_patient_data(self, parsed_message):
        """Extract patient data from HL7 message"""

        pid = parsed_message.get_segment("PID")

        return {
            "identifiers": self.parse_identifiers(pid.get_field(3)),
            "name": self.parse_name(pid.get_field(5)),
            "birthDate": self.parse_date(pid.get_field(7)),
            "gender": self.map_gender(pid.get_field(8)),
            "address": self.parse_address(pid.get_field(11)),
            "telecom": self.parse_telecom(pid.get_field(13))
        }
```

### ORM (Order Entry)

```python
class ORMMessageHandler:
    """Handler for Order Entry messages"""

    def process_order_message(self, message):
        """Process ORM^O01 order message"""

        parsed = self.parser.parse(message)

        # Extract order details
        orc = parsed.get_segment("ORC")
        obr = parsed.get_segment("OBR")

        order = {
            "orderControl": orc.get_field(1),
            "placerOrderNumber": orc.get_field(2),
            "fillerOrderNumber": orc.get_field(3),
            "orderStatus": orc.get_field(5),
            "orderDateTime": self.parse_timestamp(orc.get_field(9)),
            "enteredBy": self.parse_provider(orc.get_field(10)),
            "orderingProvider": self.parse_provider(orc.get_field(12)),
            "universalServiceId": self.parse_coded_element(obr.get_field(4)),
            "priority": obr.get_field(5),
            "specimenSource": self.parse_specimen(obr.get_field(15))
        }

        # Convert to FHIR ServiceRequest
        fhir_request = self.create_service_request(order)

        # Save and return response
        saved = self.fhir_client.create(fhir_request)
        return self.generate_order_response(parsed, saved)
```

### ORU (Observation Results)

```python
class ORUMessageHandler:
    """Handler for Observation Result messages"""

    def process_result_message(self, message):
        """Process ORU^R01 result message"""

        parsed = self.parser.parse(message)
        observations = []

        # Process each OBX segment
        for obx in parsed.get_segments("OBX"):
            observation = {
                "setId": obx.get_field(1),
                "valueType": obx.get_field(2),
                "observationId": self.parse_coded_element(obx.get_field(3)),
                "value": self.parse_value(obx.get_field(5), obx.get_field(2)),
                "units": self.parse_units(obx.get_field(6)),
                "referenceRange": obx.get_field(7),
                "abnormalFlags": obx.get_field(8),
                "resultStatus": obx.get_field(11),
                "observationDateTime": self.parse_timestamp(obx.get_field(14))
            }

            observations.append(observation)

        # Create FHIR Observations
        fhir_observations = [
            self.create_fhir_observation(obs) for obs in observations
        ]

        # Create DiagnosticReport
        report = self.create_diagnostic_report(parsed, fhir_observations)

        return self.save_results(report, fhir_observations)
```

## HL7 to FHIR Mapping

### Patient Mapping

```python
class HL7ToFHIRMapper:
    """Map HL7 v2 segments to FHIR resources"""

    def map_pid_to_patient(self, pid_segment):
        """Map PID segment to FHIR Patient resource"""

        patient = {
            "resourceType": "Patient",
            "identifier": [],
            "name": [],
            "telecom": [],
            "address": [],
            "extension": []
        }

        # Map identifiers (PID-3)
        for id_field in pid_segment.get_field(3).split("~"):
            if id_field:
                parts = id_field.split("^")
                patient["identifier"].append({
                    "value": parts[0],
                    "system": self.map_identifier_system(parts[3]) if len(parts) > 3 else None,
                    "type": {
                        "coding": [{
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                            "code": parts[4] if len(parts) > 4 else "MR"
                        }]
                    }
                })

        # Map name (PID-5)
        name_parts = pid_segment.get_field(5).split("^")
        patient["name"].append({
            "family": name_parts[0],
            "given": [name_parts[1]] if len(name_parts) > 1 else [],
            "prefix": [name_parts[4]] if len(name_parts) > 4 else [],
            "use": "official"
        })

        # Map birth date (PID-7)
        if pid_segment.get_field(7):
            patient["birthDate"] = self.format_date(pid_segment.get_field(7))

        # Map gender (PID-8)
        gender_map = {"M": "male", "F": "female", "O": "other", "U": "unknown"}
        patient["gender"] = gender_map.get(pid_segment.get_field(8), "unknown")

        return patient
```

### Observation Mapping

```python
def map_obx_to_observation(self, obx_segment, obr_segment=None):
    """Map OBX segment to FHIR Observation"""

    observation = {
        "resourceType": "Observation",
        "status": self.map_result_status(obx_segment.get_field(11)),
        "code": self.map_observation_code(obx_segment.get_field(3)),
        "effectiveDateTime": self.format_timestamp(obx_segment.get_field(14))
    }

    # Map value based on type
    value_type = obx_segment.get_field(2)
    value = obx_segment.get_field(5)

    if value_type == "NM":  # Numeric
        observation["valueQuantity"] = {
            "value": float(value),
            "unit": obx_segment.get_field(6).split("^")[0],
            "system": "http://unitsofmeasure.org"
        }
    elif value_type == "ST":  # String
        observation["valueString"] = value
    elif value_type == "CE":  # Coded element
        observation["valueCodeableConcept"] = self.parse_coded_element(value)

    # Map reference range
    if obx_segment.get_field(7):
        observation["referenceRange"] = [self.parse_reference_range(obx_segment.get_field(7))]

    # Map interpretation
    if obx_segment.get_field(8):
        observation["interpretation"] = [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                "code": obx_segment.get_field(8)
            }]
        }]

    return observation
```

## Message Transformation

### XSLT Transformations

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="2.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

    <!-- Transform HL7 v2 XML to FHIR Bundle -->
    <xsl:template match="/HL7Message">
        <Bundle xmlns="http://hl7.org/fhir">
            <type value="transaction"/>

            <!-- Process each segment -->
            <xsl:apply-templates select="MSH"/>
            <xsl:apply-templates select="PID"/>
            <xsl:apply-templates select="PV1"/>
            <xsl:apply-templates select="OBX"/>
        </Bundle>
    </xsl:template>

    <!-- Transform PID to Patient -->
    <xsl:template match="PID">
        <entry>
            <resource>
                <Patient>
                    <identifier>
                        <value>
                            <xsl:value-of select="PID.3/CX.1"/>
                        </value>
                    </identifier>
                    <name>
                        <family>
                            <xsl:value-of select="PID.5/XPN.1"/>
                        </family>
                        <given>
                            <xsl:value-of select="PID.5/XPN.2"/>
                        </given>
                    </name>
                </Patient>
            </resource>
            <request>
                <method value="POST"/>
                <url value="Patient"/>
            </request>
        </entry>
    </xsl:template>

</xsl:stylesheet>
```

## Error Handling

### ACK Generation

```python
class ACKGenerator:
    """Generate HL7 acknowledgment messages"""

    def generate_ack(self, original_message, success=True, error_message=None):
        """Generate ACK message"""

        msh = original_message.get_segment("MSH")

        # Build ACK MSH segment
        ack_msh = f"MSH|^~\\&|{msh.get_field(5)}|{msh.get_field(6)}|"
        ack_msh += f"{msh.get_field(3)}|{msh.get_field(4)}|"
        ack_msh += f"{datetime.now().strftime('%Y%m%d%H%M%S')}||"
        ack_msh += f"ACK^{msh.get_field(9).split('^')[1]}|"
        ack_msh += f"{self.generate_message_id()}|P|2.5"

        # Build MSA segment
        ack_code = "AA" if success else "AE"
        msa = f"MSA|{ack_code}|{msh.get_field(10)}"

        if error_message:
            msa += f"|{error_message}"

        return f"{ack_msh}\r{msa}"

    def generate_nack(self, original_message, error_code, error_text):
        """Generate negative acknowledgment"""

        ack = self.generate_ack(original_message, False, error_text)

        # Add ERR segment
        err = f"ERR|^^^{error_code}&{error_text}"

        return f"{ack}\r{err}"
```

## Message Routing

### Routing Configuration

```yaml
message_routing:
  routes:
    - name: "ADT to Patient Service"
      filter:
        message_type: "ADT"
        events: ["A01", "A04", "A08"]
      destination:
        type: "fhir"
        endpoint: "https://fhir.havenpassport.org/Patient"

    - name: "Lab Results to Observation Service"
      filter:
        message_type: "ORU"
        sending_facility: "LAB*"
      destination:
        type: "fhir"
        endpoint: "https://fhir.havenpassport.org/Observation"

    - name: "Orders to ServiceRequest"
      filter:
        message_type: "ORM"
      destination:
        type: "fhir"
        endpoint: "https://fhir.havenpassport.org/ServiceRequest"

  error_handling:
    max_retries: 3
    retry_interval: 60
    dead_letter_queue: "hl7-errors"
```

### Message Router Implementation

```python
class HL7MessageRouter:
    """Route HL7 messages based on configuration"""

    def route_message(self, message):
        """Route message to appropriate handler"""

        # Parse message header
        msh = self.parse_msh(message)
        message_type = msh["message_type"]
        event = msh["trigger_event"]

        # Find matching route
        route = self.find_route(message_type, event, msh)

        if not route:
            raise RoutingError(f"No route found for {message_type}^{event}")

        # Apply transformations
        transformed = self.apply_transformations(message, route)

        # Send to destination
        return self.send_to_destination(transformed, route["destination"])

    def apply_transformations(self, message, route):
        """Apply configured transformations"""

        transformations = route.get("transformations", [])
        result = message

        for transform in transformations:
            if transform["type"] == "xslt":
                result = self.apply_xslt(result, transform["template"])
            elif transform["type"] == "script":
                result = self.apply_script(result, transform["script"])
            elif transform["type"] == "mapping":
                result = self.apply_mapping(result, transform["map"])

        return result
```

## Security

### Message Encryption

```python
class HL7Security:
    """Security functions for HL7 messages"""

    def encrypt_segment(self, segment, fields_to_encrypt):
        """Encrypt specific fields in a segment"""

        parts = segment.split("|")

        for field_num in fields_to_encrypt:
            if field_num < len(parts):
                parts[field_num] = self.encrypt_field(parts[field_num])

        return "|".join(parts)

    def add_security_header(self, message):
        """Add security header to message"""

        # Create SFT (Software Segment) for security info
        sft = "SFT|Haven Health Passport|1.0|HL7Secure|"
        sft += f"{datetime.now().strftime('%Y%m%d')}||"
        sft += f"{self.generate_security_token()}"

        # Insert after MSH
        lines = message.split("\r")
        lines.insert(1, sft)

        return "\r".join(lines)
```

## Performance Optimization

### Message Parsing Optimization

```python
class OptimizedHL7Parser:
    """Optimized HL7 message parser"""

    def __init__(self):
        self.segment_cache = {}
        self.field_separator = "|"
        self.encoding_chars = "^~\\&"

    def parse_message(self, message):
        """Parse HL7 message with caching"""

        # Check cache
        message_hash = hashlib.md5(message.encode()).hexdigest()
        if message_hash in self.segment_cache:
            return self.segment_cache[message_hash]

        # Parse message
        segments = {}
        for line in message.strip().split("\r"):
            if line:
                segment_type = line[:3]
                if segment_type not in segments:
                    segments[segment_type] = []
                segments[segment_type].append(self.parse_segment(line))

        # Cache result
        self.segment_cache[message_hash] = segments

        return segments

    def parse_segment(self, segment):
        """Parse individual segment"""

        fields = segment.split(self.field_separator)

        # Special handling for MSH
        if fields[0] == "MSH":
            # MSH field count is off by one due to field separator
            fields.insert(1, self.field_separator)

        return fields
```

## Testing

### Message Validation

```python
class HL7Validator:
    """Validate HL7 messages against profiles"""

    def validate_message(self, message, profile):
        """Validate message against profile"""

        errors = []
        parsed = self.parser.parse(message)

        # Check required segments
        for segment in profile["required_segments"]:
            if segment not in parsed:
                errors.append(f"Missing required segment: {segment}")

        # Validate each segment
        for segment_type, segments in parsed.items():
            if segment_type in profile["segments"]:
                segment_profile = profile["segments"][segment_type]
                for segment in segments:
                    errors.extend(
                        self.validate_segment(segment, segment_profile)
                    )

        return errors
```

### Test Message Generation

```python
def generate_test_adt_a01():
    """Generate test ADT^A01 admission message"""

    return """MSH|^~\\&|TEST_SEND|FACILITY|TEST_RECV|FACILITY|20240531120000||ADT^A01|MSG00001|P|2.5
EVN|A01|20240531120000
PID|1||123456^^^HAVEN^MR||TEST^PATIENT^A||19800101|M||W|123 TEST ST^^CITY^STATE^12345||(555)123-4567|||M|NONE|987654321
NK1|1|TEST^NEXTOFKIN|SPOUSE||(555)987-6543
PV1|1|I|ICU^101^A||||1234^DOCTOR^TEST^MD|||MED||||||||ADM|A0
DG1|1||I10^A00.0^Cholera^I10||20240531|A
IN1|1|INS001|INSURANCE CO|||||||||20240101||||TEST^PATIENT^A|SELF|19800101|123 TEST ST^^CITY^STATE^12345|||||||||||||||||||||||||||||||||||"""
```

## Troubleshooting

### Common Issues

1. **Character Encoding Issues**
   - Ensure proper encoding (UTF-8)
   - Handle special characters in names/addresses
   - Use proper escape sequences

2. **Segment Order**
   - Maintain correct segment order per message type
   - Handle repeating segments properly
   - Validate cardinality requirements

3. **Field Length Limits**
   - Monitor field lengths against HL7 specifications
   - Truncate or reject oversized fields appropriately
   - Log truncation warnings

## References

- [HL7 v2.5.1 Specification](http://www.hl7.org/implement/standards/product_brief.cfm?product_id=144)
- [HL7 FHIR Mapping Language](http://hl7.org/fhir/mapping-language.html)
- [HL7 v2 to FHIR Mapping](http://hl7.org/fhir/hl7-v2.html)
- [HAPI HL7v2 Library](https://hapifhir.github.io/hapi-hl7v2/)
