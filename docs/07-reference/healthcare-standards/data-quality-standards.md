# Data Quality Standards

## Overview

Haven Health Passport implements comprehensive data quality standards to ensure the accuracy, completeness, consistency, and reliability of healthcare information. This document defines validation rules, standardization procedures, and quality metrics.

## Data Quality Dimensions

### 1. Accuracy
- Correctness of data values
- Valid code references
- Proper data types
- Range validation

### 2. Completeness
- Required field presence
- Minimum data set compliance
- Clinical documentation standards

### 3. Consistency
- Cross-field validation
- Temporal consistency
- Referential integrity

### 4. Timeliness
- Data currency requirements
- Update frequency standards
- Synchronization windows

### 5. Validity
- Format compliance
- Business rule adherence
- Clinical plausibility

## Validation Framework

### Core Validation Engine

```python
class DataQualityValidator:
    """Central data quality validation engine"""

    def __init__(self):
        self.rules = self.load_validation_rules()
        self.validators = {
            'required': RequiredFieldValidator(),
            'format': FormatValidator(),
            'range': RangeValidator(),
            'code': CodeValidator(),
            'cross_field': CrossFieldValidator(),
            'temporal': TemporalValidator(),
            'clinical': ClinicalPlausibilityValidator()
        }

    def validate_resource(self, resource_type, resource_data):
        """Validate a FHIR resource against quality rules"""

        validation_results = {
            'resource_type': resource_type,
            'validation_timestamp': datetime.utcnow(),
            'errors': [],
            'warnings': [],
            'info': []
        }

        # Get rules for resource type
        rules = self.rules.get(resource_type, [])

        for rule in rules:
            validator = self.validators[rule['type']]
            result = validator.validate(resource_data, rule)

            if result.severity == 'error':
                validation_results['errors'].append(result)
            elif result.severity == 'warning':
                validation_results['warnings'].append(result)
            else:
                validation_results['info'].append(result)

        validation_results['quality_score'] = self.calculate_quality_score(validation_results)

        return validation_results
```

### Validation Rules Definition

```yaml
validation_rules:
  Patient:
    - type: required
      fields: ["identifier", "name", "birthDate"]
      severity: error
      message: "Patient must have identifier, name, and birth date"

    - type: format
      field: birthDate
      pattern: "^\\d{4}-\\d{2}-\\d{2}$"
      severity: error
      message: "Birth date must be in YYYY-MM-DD format"

    - type: range
      field: birthDate
      min: "1900-01-01"
      max: "current_date"
      severity: error
      message: "Birth date must be between 1900 and current date"

    - type: cross_field
      condition: "deceasedBoolean = true"
      requires: "deceasedDateTime"
      severity: warning
      message: "Deceased patients should have deceased date/time"

  Observation:
    - type: required
      fields: ["status", "code", "subject"]
      severity: error
      message: "Observation must have status, code, and subject"

    - type: code
      field: "code.coding"
      systems: ["http://loinc.org", "http://snomed.info/sct"]
      severity: error
      message: "Observation code must be from LOINC or SNOMED CT"

    - type: clinical
      rule: vital_sign_ranges
      severity: warning
      message: "Vital sign value outside normal range"
```

## Field-Level Validators

### Required Field Validator

```python
class RequiredFieldValidator:
    """Validate presence of required fields"""

    def validate(self, data, rule):
        """Check if required fields are present and non-empty"""

        missing_fields = []

        for field_path in rule['fields']:
            value = self.get_field_value(data, field_path)

            if value is None or value == "" or value == []:
                missing_fields.append(field_path)

        if missing_fields:
            return ValidationResult(
                severity=rule['severity'],
                message=f"{rule['message']}. Missing: {', '.join(missing_fields)}",
                field_paths=missing_fields
            )

        return ValidationResult(severity='info', message='All required fields present')
```

### Format Validator

```python
class FormatValidator:
    """Validate field formats against patterns"""

    COMMON_PATTERNS = {
        'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        'phone': r'^\+?1?\d{10,14}$',
        'postal_code': r'^\d{5}(-\d{4})?$',
        'date': r'^\d{4}-\d{2}-\d{2}$',
        'datetime': r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$',
        'uuid': r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    }

    def validate(self, data, rule):
        """Validate field format against pattern"""

        field_value = self.get_field_value(data, rule['field'])

        if field_value is None:
            return ValidationResult(severity='info', message='Field not present')

        pattern = rule.get('pattern') or self.COMMON_PATTERNS.get(rule.get('format_type'))

        if pattern and not re.match(pattern, str(field_value)):
            return ValidationResult(
                severity=rule['severity'],
                message=rule['message'],
                field_paths=[rule['field']],
                actual_value=field_value
            )

        return ValidationResult(severity='info', message='Format valid')
```

### Range Validator

```python
class RangeValidator:
    """Validate numeric and date ranges"""

    def validate(self, data, rule):
        """Check if value is within specified range"""

        field_value = self.get_field_value(data, rule['field'])

        if field_value is None:
            return ValidationResult(severity='info', message='Field not present')

        # Handle different data types
        if isinstance(field_value, (int, float)):
            value = field_value
        elif isinstance(field_value, str):
            try:
                # Try to parse as date
                value = datetime.fromisoformat(field_value.replace('Z', '+00:00'))
            except:
                try:
                    # Try to parse as number
                    value = float(field_value)
                except:
                    return ValidationResult(
                        severity='error',
                        message='Cannot parse value for range validation',
                        field_paths=[rule['field']]
                    )

        # Check range
        min_val = self.parse_value(rule.get('min'))
        max_val = self.parse_value(rule.get('max'))

        if min_val and value < min_val:
            return ValidationResult(
                severity=rule['severity'],
                message=f"{rule['message']}. Value {value} is below minimum {min_val}",
                field_paths=[rule['field']]
            )

        if max_val and value > max_val:
            return ValidationResult(
                severity=rule['severity'],
                message=f"{rule['message']}. Value {value} is above maximum {max_val}",
                field_paths=[rule['field']]
            )

        return ValidationResult(severity='info', message='Value within range')
```

## Clinical Validation

### Clinical Plausibility Rules

```python
class ClinicalPlausibilityValidator:
    """Validate clinical plausibility of data"""

    VITAL_SIGN_RANGES = {
        # LOINC Code -> (min, max, unit)
        '8310-5': (10, 50, '°C'),  # Body temperature
        '8867-4': (30, 250, '/min'),  # Heart rate
        '9279-1': (5, 60, '/min'),  # Respiratory rate
        '8480-6': (50, 250, 'mm[Hg]'),  # Systolic blood pressure
        '8462-4': (20, 150, 'mm[Hg]'),  # Diastolic blood pressure
        '2708-6': (70, 100, '%'),  # Oxygen saturation
        '3141-9': (20, 500, 'kg'),  # Body weight
        '8302-2': (50, 250, 'cm')  # Body height
    }

    def validate_vital_signs(self, observation):
        """Validate vital sign measurements"""

        # Get LOINC code
        loinc_code = None
        for coding in observation.get('code', {}).get('coding', []):
            if coding.get('system') == 'http://loinc.org':
                loinc_code = coding.get('code')
                break

        if not loinc_code or loinc_code not in self.VITAL_SIGN_RANGES:
            return ValidationResult(severity='info', message='Not a known vital sign')

        # Get value
        value_quantity = observation.get('valueQuantity', {})
        value = value_quantity.get('value')

        if value is None:
            return ValidationResult(
                severity='error',
                message='Vital sign observation missing value'
            )

        # Check range
        min_val, max_val, expected_unit = self.VITAL_SIGN_RANGES[loinc_code]

        if value < min_val or value > max_val:
            return ValidationResult(
                severity='warning',
                message=f'Vital sign value {value} outside normal range ({min_val}-{max_val})',
                clinical_significance='high'
            )

        return ValidationResult(severity='info', message='Vital sign within normal range')
```

### Drug Interaction Checking

```python
class DrugInteractionValidator:
    """Validate for potential drug interactions"""

    def validate_medication_list(self, patient_id):
        """Check all active medications for interactions"""

        # Get active medications
        medications = self.get_active_medications(patient_id)
        interactions = []

        # Check each pair
        for i in range(len(medications)):
            for j in range(i + 1, len(medications)):
                interaction = self.check_interaction(
                    medications[i]['code'],
                    medications[j]['code']
                )

                if interaction:
                    interactions.append({
                        'drug1': medications[i],
                        'drug2': medications[j],
                        'severity': interaction['severity'],
                        'description': interaction['description'],
                        'clinical_significance': interaction['clinical_significance']
                    })

        if interactions:
            high_severity = [i for i in interactions if i['severity'] == 'high']

            return ValidationResult(
                severity='warning' if high_severity else 'info',
                message=f'Found {len(interactions)} potential drug interactions',
                details=interactions
            )

        return ValidationResult(severity='info', message='No drug interactions found')
```

## Data Standardization

### Name Standardization

```python
class NameStandardizer:
    """Standardize patient names"""

    def standardize_name(self, name_obj):
        """Apply name standardization rules"""

        standardized = {
            'use': name_obj.get('use', 'official'),
            'family': self.standardize_family_name(name_obj.get('family', '')),
            'given': [self.standardize_given_name(g) for g in name_obj.get('given', [])]
        }

        # Handle prefixes
        if 'prefix' in name_obj:
            standardized['prefix'] = [self.standardize_prefix(p) for p in name_obj['prefix']]

        # Handle suffixes
        if 'suffix' in name_obj:
            standardized['suffix'] = [self.standardize_suffix(s) for s in name_obj['suffix']]

        return standardized

    def standardize_family_name(self, family_name):
        """Standardize family name"""

        # Convert to title case
        name = family_name.strip().title()

        # Handle special cases
        special_cases = {
            'Mcdonald': 'McDonald',
            'Macdonald': 'MacDonald',
            'O\'Brien': 'O\'Brien',
            'Van Der': 'van der',
            'De La': 'de la'
        }

        for pattern, replacement in special_cases.items():
            if pattern.lower() in name.lower():
                name = re.sub(pattern, replacement, name, flags=re.IGNORECASE)

        return name
```

### Address Standardization

```python
class AddressStandardizer:
    """Standardize addresses using USPS standards"""

    STREET_ABBREVIATIONS = {
        'STREET': 'ST',
        'AVENUE': 'AVE',
        'BOULEVARD': 'BLVD',
        'ROAD': 'RD',
        'LANE': 'LN',
        'DRIVE': 'DR',
        'COURT': 'CT',
        'PLACE': 'PL',
        'PARKWAY': 'PKWY'
    }

    DIRECTIONAL_ABBREVIATIONS = {
        'NORTH': 'N',
        'SOUTH': 'S',
        'EAST': 'E',
        'WEST': 'W',
        'NORTHEAST': 'NE',
        'NORTHWEST': 'NW',
        'SOUTHEAST': 'SE',
        'SOUTHWEST': 'SW'
    }

    def standardize_address(self, address_obj):
        """Standardize address components"""

        standardized = {
            'use': address_obj.get('use', 'home'),
            'type': address_obj.get('type', 'physical'),
            'line': [],
            'city': self.standardize_city(address_obj.get('city', '')),
            'state': self.standardize_state(address_obj.get('state', '')),
            'postalCode': self.standardize_postal_code(address_obj.get('postalCode', '')),
            'country': self.standardize_country(address_obj.get('country', ''))
        }

        # Standardize address lines
        for line in address_obj.get('line', []):
            standardized['line'].append(self.standardize_address_line(line))

        return standardized

    def standardize_address_line(self, line):
        """Standardize individual address line"""

        # Convert to uppercase
        line = line.upper().strip()

        # Replace street types
        for full, abbr in self.STREET_ABBREVIATIONS.items():
            line = re.sub(r'\b' + full + r'\b', abbr, line)

        # Replace directionals
        for full, abbr in self.DIRECTIONAL_ABBREVIATIONS.items():
            line = re.sub(r'\b' + full + r'\b', abbr, line)

        return line
```

## Duplicate Detection

### Patient Matching Algorithm

```python
class DuplicateDetector:
    """Detect potential duplicate records"""

    def find_potential_duplicates(self, patient):
        """Find potential duplicate patient records"""

        candidates = []

        # Search by exact identifiers
        for identifier in patient.get('identifier', []):
            matches = self.search_by_identifier(identifier)
            candidates.extend(matches)

        # Search by demographics
        demographic_matches = self.search_by_demographics(patient)
        candidates.extend(demographic_matches)

        # Score each candidate
        scored_candidates = []
        for candidate in candidates:
            score = self.calculate_match_score(patient, candidate)
            if score > 0.7:  # Threshold for potential match
                scored_candidates.append({
                    'patient': candidate,
                    'score': score,
                    'match_details': self.get_match_details(patient, candidate)
                })

        # Sort by score
        scored_candidates.sort(key=lambda x: x['score'], reverse=True)

        return scored_candidates

    def calculate_match_score(self, patient1, patient2):
        """Calculate similarity score between two patients"""

        score = 0.0
        weights = {
            'identifier': 0.3,
            'name': 0.25,
            'birthDate': 0.2,
            'gender': 0.1,
            'address': 0.1,
            'telecom': 0.05
        }

        # Compare identifiers
        if self.compare_identifiers(patient1, patient2):
            score += weights['identifier']

        # Compare names
        name_similarity = self.calculate_name_similarity(patient1, patient2)
        score += weights['name'] * name_similarity

        # Compare birth date
        if patient1.get('birthDate') == patient2.get('birthDate'):
            score += weights['birthDate']

        # Compare gender
        if patient1.get('gender') == patient2.get('gender'):
            score += weights['gender']

        # Compare address
        address_similarity = self.calculate_address_similarity(patient1, patient2)
        score += weights['address'] * address_similarity

        # Compare telecom
        if self.compare_telecom(patient1, patient2):
            score += weights['telecom']

        return score
```

## Quality Metrics

### Data Quality Dashboard

```python
class DataQualityMetrics:
    """Calculate and track data quality metrics"""

    def calculate_resource_quality_metrics(self, resource_type, time_period):
        """Calculate quality metrics for a resource type"""

        metrics = {
            'resource_type': resource_type,
            'time_period': time_period,
            'total_resources': 0,
            'completeness_score': 0.0,
            'accuracy_score': 0.0,
            'consistency_score': 0.0,
            'timeliness_score': 0.0,
            'overall_quality_score': 0.0,
            'field_completeness': {},
            'validation_errors': {},
            'common_issues': []
        }

        # Get all resources for time period
        resources = self.get_resources(resource_type, time_period)
        metrics['total_resources'] = len(resources)

        # Calculate completeness
        completeness_scores = []
        for resource in resources:
            score = self.calculate_completeness(resource, resource_type)
            completeness_scores.append(score)

            # Track field-level completeness
            for field, is_complete in score['fields'].items():
                if field not in metrics['field_completeness']:
                    metrics['field_completeness'][field] = {'complete': 0, 'total': 0}

                metrics['field_completeness'][field]['total'] += 1
                if is_complete:
                    metrics['field_completeness'][field]['complete'] += 1

        metrics['completeness_score'] = np.mean([s['overall'] for s in completeness_scores])

        # Calculate accuracy (validation pass rate)
        validation_results = []
        for resource in resources:
            result = self.validator.validate_resource(resource_type, resource)
            validation_results.append(result)

            # Track error types
            for error in result['errors']:
                error_type = error['type']
                if error_type not in metrics['validation_errors']:
                    metrics['validation_errors'][error_type] = 0
                metrics['validation_errors'][error_type] += 1

        error_count = sum(len(r['errors']) for r in validation_results)
        metrics['accuracy_score'] = 1.0 - (error_count / (len(resources) * 10))  # Assume max 10 errors per resource

        # Calculate consistency
        metrics['consistency_score'] = self.calculate_consistency_score(resources)

        # Calculate timeliness
        metrics['timeliness_score'] = self.calculate_timeliness_score(resources)

        # Overall quality score
        metrics['overall_quality_score'] = np.mean([
            metrics['completeness_score'],
            metrics['accuracy_score'],
            metrics['consistency_score'],
            metrics['timeliness_score']
        ])

        # Identify common issues
        metrics['common_issues'] = self.identify_common_issues(validation_results)

        return metrics
```

### Quality Reporting

```python
def generate_quality_report(self, start_date, end_date):
    """Generate comprehensive data quality report"""

    report = {
        'report_period': {
            'start': start_date,
            'end': end_date
        },
        'generated_at': datetime.utcnow(),
        'summary': {},
        'resource_metrics': {},
        'trends': {},
        'recommendations': []
    }

    # Calculate metrics for each resource type
    for resource_type in ['Patient', 'Observation', 'MedicationRequest', 'Condition']:
        metrics = self.calculate_resource_quality_metrics(
            resource_type,
            (start_date, end_date)
        )
        report['resource_metrics'][resource_type] = metrics

    # Calculate summary statistics
    report['summary'] = {
        'total_resources': sum(m['total_resources'] for m in report['resource_metrics'].values()),
        'average_quality_score': np.mean([m['overall_quality_score'] for m in report['resource_metrics'].values()]),
        'resources_with_errors': sum(len(m['validation_errors']) > 0 for m in report['resource_metrics'].values())
    }

    # Analyze trends
    report['trends'] = self.analyze_quality_trends(start_date, end_date)

    # Generate recommendations
    report['recommendations'] = self.generate_recommendations(report)

    return report
```

## Implementation Guidelines

### Integration Points

1. **FHIR Server Integration**
   - Pre-save validation hooks
   - Post-save quality scoring
   - Batch validation jobs

2. **API Integration**
   - Validation middleware
   - Quality score headers
   - Error response formatting

3. **UI Integration**
   - Real-time validation feedback
   - Quality indicators
   - Data entry assistance

### Performance Optimization

```python
class ValidationCache:
    """Cache validation results for performance"""

    def __init__(self):
        self.cache = {}
        self.ttl = 3600  # 1 hour

    def get_cached_result(self, resource_type, resource_hash):
        """Get cached validation result"""

        key = f"{resource_type}:{resource_hash}"

        if key in self.cache:
            result, timestamp = self.cache[key]

            if datetime.utcnow() - timestamp < timedelta(seconds=self.ttl):
                return result
            else:
                del self.cache[key]

        return None

    def cache_result(self, resource_type, resource_hash, result):
        """Cache validation result"""

        key = f"{resource_type}:{resource_hash}"
        self.cache[key] = (result, datetime.utcnow())
```

## References

- [FHIR Data Quality Guidelines](http://hl7.org/fhir/us/core/general-guidance.html#data-quality)
- [ISO 8000 Data Quality Standards](https://www.iso.org/standard/50798.html)
- [AHIMA Data Quality Model](https://www.ahima.org/data-quality)
- [CDC Data Quality Guidelines](https://www.cdc.gov/nchs/data/quality/data_quality_guidelines.pdf)
