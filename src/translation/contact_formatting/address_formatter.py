"""Address formatter for various country formats."""

import re
from difflib import get_close_matches
from typing import Dict, List

from src.utils.logging import get_logger

from .address_nlp import AddressNLPParser
from .types import AddressFormat, CountryAddressFormat

logger = get_logger(__name__)


class AddressFormatter:
    """Formats addresses for different countries with NLP enhancements."""

    # Country address formats with enhanced data
    COUNTRY_FORMATS = {
        "US": CountryAddressFormat(
            country_code="US",
            format_order=["street", "unit", "city", "state", "postal_code"],
            required_fields=["street", "city", "state", "postal_code"],
            postal_code_format=r"^\d{5}(-\d{4})?$",
            state_provinces={
                "AL": "Alabama",
                "AK": "Alaska",
                "AZ": "Arizona",
                "AR": "Arkansas",
                "CA": "California",
                "CO": "Colorado",
                "CT": "Connecticut",
                "DE": "Delaware",
                "FL": "Florida",
                "GA": "Georgia",
                "HI": "Hawaii",
                "ID": "Idaho",
                "IL": "Illinois",
                "IN": "Indiana",
                "IA": "Iowa",
                "KS": "Kansas",
                "KY": "Kentucky",
                "LA": "Louisiana",
                "ME": "Maine",
                "MD": "Maryland",
                "MA": "Massachusetts",
                "MI": "Michigan",
                "MN": "Minnesota",
                "MS": "Mississippi",
                "MO": "Missouri",
                "MT": "Montana",
                "NE": "Nebraska",
                "NV": "Nevada",
                "NH": "New Hampshire",
                "NJ": "New Jersey",
                "NM": "New Mexico",
                "NY": "New York",
                "NC": "North Carolina",
                "ND": "North Dakota",
                "OH": "Ohio",
                "OK": "Oklahoma",
                "OR": "Oregon",
                "PA": "Pennsylvania",
                "RI": "Rhode Island",
                "SC": "South Carolina",
                "SD": "South Dakota",
                "TN": "Tennessee",
                "TX": "Texas",
                "UT": "Utah",
                "VT": "Vermont",
                "VA": "Virginia",
                "WA": "Washington",
                "WV": "West Virginia",
                "WI": "Wisconsin",
                "WY": "Wyoming",
                "DC": "District of Columbia",
            },
            address_format=AddressFormat.WESTERN,
            local_terms={"postal_code": "ZIP code", "state": "state"},
            common_prefixes=["N", "S", "E", "W", "NE", "NW", "SE", "SW"],
            common_suffixes=["St", "Ave", "Rd", "Dr", "Ln", "Blvd", "Way", "Ct", "Pl"],
        ),
        "GB": CountryAddressFormat(
            country_code="GB",
            format_order=["street", "locality", "city", "county", "postal_code"],
            required_fields=["street", "city", "postal_code"],
            postal_code_format=r"^[A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2}$",
            state_provinces={
                "ENG": "England",
                "SCT": "Scotland",
                "WLS": "Wales",
                "NIR": "Northern Ireland",
            },
            address_format=AddressFormat.WESTERN,
            local_terms={"postal_code": "postcode", "state": "county"},
            common_prefixes=["North", "South", "East", "West", "Upper", "Lower"],
            common_suffixes=["Street", "Road", "Lane", "Avenue", "Close", "Gardens"],
        ),
        "SA": CountryAddressFormat(
            country_code="SA",
            format_order=["building", "street", "district", "city", "postal_code"],
            required_fields=["street", "city"],
            postal_code_format=r"^\d{5}$",
            state_provinces={
                "01": "Riyadh",
                "02": "Makkah",
                "03": "Madinah",
                "04": "Eastern Province",
                "05": "Al-Qassim",
                "06": "Hail",
                "07": "Tabuk",
                "08": "Northern Borders",
                "09": "Jizan",
                "10": "Najran",
                "11": "Al-Baha",
                "12": "Al-Jouf",
                "13": "Asir",
            },
            address_format=AddressFormat.MIDDLE_EASTERN,
            local_terms={
                "postal_code": "postal code",
                "state": "region",
                "street": "شارع",
            },
            common_prefixes=["شارع", "طريق"],
            common_suffixes=[],
        ),
        "AF": CountryAddressFormat(
            country_code="AF",
            format_order=["house", "street", "district", "city", "province"],
            required_fields=["district", "city", "province"],
            postal_code_format=None,
            state_provinces={
                "KAB": "Kabul",
                "KAN": "Kandahar",
                "HER": "Herat",
                "BAL": "Balkh",
                "NAN": "Nangarhar",
                "GHA": "Ghazni",
                "BAD": "Badakhshan",
                "KUN": "Kunduz",
                "TAK": "Takhar",
                "BAG": "Baghlan",
                "KHO": "Khost",
                "PAK": "Paktia",
                "LOG": "Logar",
                "WAR": "Wardak",
                "FAR": "Faryab",
                "HEL": "Helmand",
                "NIM": "Nimroz",
                "URU": "Uruzgan",
                "ZAB": "Zabul",
                "GHO": "Ghor",
                "BAM": "Bamyan",
                "PAR": "Parwan",
                "KAP": "Kapisa",
                "LAG": "Laghman",
                "NUR": "Nuristan",
                "BDG": "Badghis",
                "FRH": "Farah",
                "SAM": "Samangan",
                "SAR": "Sar-e Pol",
                "DAY": "Daykundi",
                "PAN": "Panjshir",
            },
            address_format=AddressFormat.MIDDLE_EASTERN,
            local_terms={"state": "ولایت", "district": "ولسوالی", "street": "سرک"},
            common_prefixes=["کوچه", "سرک"],
            common_suffixes=[],
        ),
        "PK": CountryAddressFormat(
            country_code="PK",
            format_order=[
                "house",
                "street",
                "sector",
                "area",
                "city",
                "province",
                "postal_code",
            ],
            required_fields=["area", "city", "province"],
            postal_code_format=r"^\d{5}$",
            state_provinces={
                "PB": "Punjab",
                "SD": "Sindh",
                "KP": "Khyber Pakhtunkhwa",
                "BA": "Balochistan",
                "GB": "Gilgit-Baltistan",
                "AK": "Azad Kashmir",
                "IS": "Islamabad",
            },
            address_format=AddressFormat.EASTERN,
            local_terms={
                "state": "province",
                "postal_code": "postal code",
                "area": "محلہ",
            },
            common_prefixes=["Block", "Sector", "Street", "Road"],
            common_suffixes=["Road", "Street", "Colony", "Town"],
        ),
        "BD": CountryAddressFormat(
            country_code="BD",
            format_order=[
                "house",
                "road",
                "block",
                "area",
                "thana",
                "district",
                "division",
            ],
            required_fields=["area", "thana", "district"],
            postal_code_format=r"^\d{4}$",
            state_provinces={
                "DHK": "Dhaka",
                "CTG": "Chittagong",
                "RAJ": "Rajshahi",
                "KHU": "Khulna",
                "BAR": "Barisal",
                "SYL": "Sylhet",
                "RAN": "Rangpur",
                "MYM": "Mymensingh",
            },
            address_format=AddressFormat.EASTERN,
            local_terms={"state": "division", "city": "district", "road": "রাস্তা"},
            common_prefixes=["Road", "Lane", "Block"],
            common_suffixes=[],
        ),
        "IN": CountryAddressFormat(
            country_code="IN",
            format_order=[
                "flat",
                "building",
                "street",
                "locality",
                "landmark",
                "city",
                "district",
                "state",
                "pin_code",
            ],
            required_fields=["locality", "city", "state", "pin_code"],
            postal_code_format=r"^\d{6}$",
            state_provinces={
                "AN": "Andaman and Nicobar Islands",
                "AP": "Andhra Pradesh",
                "AR": "Arunachal Pradesh",
                "AS": "Assam",
                "BR": "Bihar",
                "CH": "Chandigarh",
                "CT": "Chhattisgarh",
                "DN": "Dadra and Nagar Haveli",
                "DD": "Daman and Diu",
                "DL": "Delhi",
                "GA": "Goa",
                "GJ": "Gujarat",
                "HR": "Haryana",
                "HP": "Himachal Pradesh",
                "JK": "Jammu and Kashmir",
                "JH": "Jharkhand",
                "KA": "Karnataka",
                "KL": "Kerala",
                "LD": "Lakshadweep",
                "MP": "Madhya Pradesh",
                "MH": "Maharashtra",
                "MN": "Manipur",
                "ML": "Meghalaya",
                "MZ": "Mizoram",
                "NL": "Nagaland",
                "OR": "Odisha",
                "PY": "Puducherry",
                "PB": "Punjab",
                "RJ": "Rajasthan",
                "SK": "Sikkim",
                "TN": "Tamil Nadu",
                "TG": "Telangana",
                "TR": "Tripura",
                "UP": "Uttar Pradesh",
                "UT": "Uttarakhand",
                "WB": "West Bengal",
            },
            address_format=AddressFormat.EASTERN,
            local_terms={
                "postal_code": "PIN code",
                "state": "state",
                "locality": "मोहल्ला",
            },
            common_prefixes=["Plot", "House", "Flat", "Shop"],
            common_suffixes=["Nagar", "Colony", "Vihar", "Puram", "Layout"],
        ),
        "KE": CountryAddressFormat(
            country_code="KE",
            format_order=[
                "plot",
                "building",
                "street",
                "estate",
                "area",
                "city",
                "county",
                "postal_code",
            ],
            required_fields=["area", "city", "county"],
            postal_code_format=r"^\d{5}$",
            state_provinces={
                "001": "Mombasa",
                "002": "Kwale",
                "003": "Kilifi",
                "004": "Tana River",
                "005": "Lamu",
                "006": "Taita-Taveta",
                "007": "Garissa",
                "008": "Wajir",
                "009": "Mandera",
                "010": "Marsabit",
                "011": "Isiolo",
                "012": "Meru",
                "013": "Tharaka-Nithi",
                "014": "Embu",
                "015": "Kitui",
                "016": "Machakos",
                "017": "Makueni",
                "018": "Nyandarua",
                "019": "Nyeri",
                "020": "Kirinyaga",
                "021": "Murang'a",
                "022": "Kiambu",
                "023": "Turkana",
                "024": "West Pokot",
                "025": "Samburu",
                "026": "Trans-Nzoia",
                "027": "Uasin Gishu",
                "028": "Elgeyo-Marakwet",
                "029": "Nandi",
                "030": "Baringo",
                "031": "Laikipia",
                "032": "Nakuru",
                "033": "Narok",
                "034": "Kajiado",
                "035": "Kericho",
                "036": "Bomet",
                "037": "Kakamega",
                "038": "Vihiga",
                "039": "Bungoma",
                "040": "Busia",
                "041": "Siaya",
                "042": "Kisumu",
                "043": "Homa Bay",
                "044": "Migori",
                "045": "Kisii",
                "046": "Nyamira",
                "047": "Nairobi",
            },
            address_format=AddressFormat.WESTERN,
            local_terms={"state": "county", "postal_code": "postal code"},
            common_prefixes=["Plot", "LR"],
            common_suffixes=["Road", "Street", "Avenue", "Drive", "Close"],
        ),
        "ET": CountryAddressFormat(
            country_code="ET",
            format_order=["house", "kebele", "subcity", "woreda", "city", "region"],
            required_fields=["kebele", "woreda", "city", "region"],
            postal_code_format=r"^\d{4}$",
            state_provinces={
                "AA": "Addis Ababa",
                "DD": "Dire Dawa",
                "OR": "Oromia",
                "AM": "Amhara",
                "TG": "Tigray",
                "SO": "Somali",
                "SN": "SNNPR",
                "AF": "Afar",
                "BG": "Benishangul-Gumuz",
                "GM": "Gambela",
                "HR": "Harari",
                "SD": "Sidama",
            },
            address_format=AddressFormat.EASTERN,
            local_terms={"state": "ክልል", "district": "ወረዳ", "street": "መንገድ"},
            common_prefixes=["ቀበሌ", "ክፍለ ከተማ"],
            common_suffixes=[],
        ),
        "SY": CountryAddressFormat(
            country_code="SY",
            format_order=["building", "street", "neighborhood", "city", "governorate"],
            required_fields=["neighborhood", "city", "governorate"],
            postal_code_format=None,
            state_provinces={
                "DI": "Damascus",
                "RI": "Rif Dimashq",
                "QU": "Al-Qunaytirah",
                "DR": "Daraa",
                "SW": "As-Suwayda",
                "HL": "Aleppo",
                "ID": "Idlib",
                "HM": "Hama",
                "HMS": "Homs",
                "TA": "Tartus",
                "LA": "Latakia",
                "RQ": "Ar-Raqqah",
                "DZ": "Deir ez-Zor",
                "HA": "Al-Hasakah",
            },
            address_format=AddressFormat.MIDDLE_EASTERN,
            local_terms={"state": "محافظة", "neighborhood": "حي", "street": "شارع"},
            common_prefixes=["شارع", "حي"],
            common_suffixes=[],
        ),
        "IQ": CountryAddressFormat(
            country_code="IQ",
            format_order=[
                "house",
                "mahalla",
                "street",
                "district",
                "city",
                "governorate",
            ],
            required_fields=["district", "city", "governorate"],
            postal_code_format=r"^\d{5}$",
            state_provinces={
                "AN": "Al Anbar",
                "BA": "Basra",
                "MU": "Al-Muthanna",
                "QA": "Al-Qādisiyyah",
                "NA": "Najaf",
                "AR": "Erbil",
                "SU": "As-Sulaymaniyah",
                "DI": "Diyala",
                "BG": "Baghdad",
                "KI": "Kirkuk",
                "WA": "Wasit",
                "BB": "Babylon",
                "KA": "Karbala",
                "SD": "Saladin",
                "NI": "Nineveh",
                "DH": "Dohuk",
                "MA": "Maysan",
                "DQ": "Dhi Qar",
                "HA": "Halabja",
            },
            address_format=AddressFormat.MIDDLE_EASTERN,
            local_terms={"state": "محافظة", "district": "قضاء", "neighborhood": "محلة"},
            common_prefixes=["محلة", "شارع"],
            common_suffixes=[],
        ),
    }

    def __init__(self) -> None:
        """Initialize formatter with NLP parser."""
        self.nlp_parser = AddressNLPParser()

    def format_address(
        self,
        address_components: Dict[str, str],
        country_code: str,
        format_type: str = "postal",
    ) -> str:
        """
        Format address for display with NLP enhancements.

        Args:
            address_components: Dictionary of address parts
            country_code: ISO country code
            format_type: "postal" or "display"

        Returns:
            Formatted address string
        """
        country_format = self.COUNTRY_FORMATS.get(country_code)
        if not country_format:
            # Default format
            parts = [
                address_components.get("street", ""),
                address_components.get("city", ""),
                address_components.get("state", ""),
                address_components.get("postal_code", ""),
            ]
            return ", ".join(filter(None, parts))

        # Build address according to country format
        formatted_parts = []

        for field in country_format.format_order:
            value = address_components.get(field)
            if value:
                # Handle state/province codes
                if field == "state" and country_format.state_provinces:
                    # Try to expand abbreviations
                    if (
                        len(value) <= 3
                        and value.upper() in country_format.state_provinces
                    ):
                        value = country_format.state_provinces[value.upper()]
                    elif value in country_format.state_provinces.values():
                        # Already full name, no need to change
                        pass
                    else:
                        # Try fuzzy matching for common misspellings
                        matches = get_close_matches(
                            value,
                            list(country_format.state_provinces.values()),
                            n=1,
                            cutoff=0.8,
                        )
                        if matches:
                            value = matches[0]

                formatted_parts.append(value)

        # Join based on format type
        if format_type == "postal":
            # Multi-line format
            if country_format.address_format == AddressFormat.WESTERN:
                # Group by line
                lines = []

                # Line 1: Street address and unit
                line1_parts = []
                if "house" in address_components:
                    line1_parts.append(address_components["house"])
                if "street" in address_components:
                    line1_parts.append(address_components["street"])
                if "unit" in address_components:
                    line1_parts.append(f"#{address_components['unit']}")
                if line1_parts:
                    lines.append(" ".join(line1_parts))

                # Line 2: Building/Complex name if exists
                if "building" in address_components:
                    lines.append(address_components["building"])

                # Line 3: City, State, Postal
                line3_parts = []
                for field in ["city", "state", "postal_code"]:
                    if field in address_components:
                        if field == "state" and "postal_code" in address_components:
                            line3_parts.append(f"{address_components[field]},")
                        else:
                            line3_parts.append(address_components[field])
                if line3_parts:
                    lines.append(" ".join(line3_parts))

                return "\n".join(lines)

            elif country_format.address_format in [
                AddressFormat.EASTERN,
                AddressFormat.MIDDLE_EASTERN,
            ]:
                # More lines, hierarchical structure
                lines = []

                # Group related fields
                if country_code in ["IN", "PK", "BD"]:
                    # Line 1: Flat/House details
                    if any(f in address_components for f in ["flat", "house", "plot"]):
                        line1 = []
                        for f in ["flat", "house", "plot"]:
                            if f in address_components:
                                line1.append(
                                    f"{f.capitalize()} {address_components[f]}"
                                )
                        lines.append(", ".join(line1))

                    # Line 2: Building/Street
                    if any(f in address_components for f in ["building", "street"]):
                        line2 = []
                        for f in ["building", "street"]:
                            if f in address_components:
                                line2.append(address_components[f])
                        lines.append(", ".join(line2))

                    # Line 3: Area/Locality
                    if any(
                        f in address_components for f in ["sector", "area", "locality"]
                    ):
                        line3 = []
                        for f in ["sector", "area", "locality"]:
                            if f in address_components:
                                line3.append(address_components[f])
                        lines.append(", ".join(line3))

                    # Line 4: City/District
                    line4 = []
                    for f in ["city", "district", "thana"]:
                        if f in address_components:
                            line4.append(address_components[f])
                    if line4:
                        lines.append(", ".join(line4))

                    # Line 5: State/Province - Postal
                    line5 = []
                    if "state" in address_components:
                        line5.append(address_components["state"])
                    if "postal_code" in address_components:
                        line5.append(f"- {address_components['postal_code']}")
                    if line5:
                        lines.append(" ".join(line5))
                else:
                    # Generic Eastern format
                    lines = [v for v in formatted_parts if v]

                return "\n".join(lines)

        else:  # display - single line
            return ", ".join(formatted_parts)

        # Fallback return to satisfy type checker
        return ", ".join(formatted_parts)

    def validate_postal_code(self, postal_code: str, country_code: str) -> bool:
        """Validate postal code format."""
        country_format = self.COUNTRY_FORMATS.get(country_code)
        if not country_format or not country_format.postal_code_format:
            return True  # No validation available

        return bool(re.match(country_format.postal_code_format, postal_code))

    def get_required_fields(self, country_code: str) -> List[str]:
        """Get required address fields for a country."""
        country_format = self.COUNTRY_FORMATS.get(country_code)
        return country_format.required_fields if country_format else ["street", "city"]

    def get_address_labels(
        self, country_code: str, language: str = "en"
    ) -> Dict[str, str]:
        """Get localized labels for address fields."""
        country_format = self.COUNTRY_FORMATS.get(country_code)

        # Base labels
        labels = {
            "street": "Street Address",
            "unit": "Apt/Unit",
            "city": "City",
            "state": "State/Province",
            "postal_code": "Postal Code",
            "country": "Country",
            "building": "Building",
            "floor": "Floor",
            "district": "District",
            "area": "Area",
            "locality": "Locality",
            "landmark": "Landmark",
        }

        # Apply local terms
        if country_format:
            for field, local_term in country_format.local_terms.items():
                if field in labels:
                    labels[field] = local_term.title()

        # Translate to target language
        translations = {
            "ar": {
                "street": "عنوان الشارع",
                "city": "المدينة",
                "state": "الولاية/المحافظة",
                "postal_code": "الرمز البريدي",
                "building": "المبنى",
                "floor": "الطابق",
                "district": "الحي",
                "area": "المنطقة",
            },
            "ur": {
                "street": "گلی کا پتہ",
                "city": "شہر",
                "state": "صوبہ",
                "postal_code": "پوسٹل کوڈ",
                "area": "علاقہ",
                "locality": "محلہ",
            },
            "hi": {
                "street": "गली का पता",
                "city": "शहर",
                "state": "राज्य",
                "postal_code": "पिन कोड",
                "area": "क्षेत्र",
                "locality": "मोहल्ला",
                "landmark": "लैंडमार्क",
            },
            "bn": {
                "street": "রাস্তার ঠিকানা",
                "city": "শহর",
                "state": "বিভাগ",
                "postal_code": "পোস্টাল কোড",
                "area": "এলাকা",
                "district": "জেলা",
            },
            "fa": {
                "street": "آدرس خیابان",
                "city": "شهر",
                "state": "استان",
                "postal_code": "کد پستی",
                "district": "منطقه",
                "area": "محله",
            },
        }

        if language in translations:
            labels.update(translations[language])

        return labels

    def parse_address_line(
        self, address_line: str, country_code: str, language: str = "en"
    ) -> Dict[str, str]:
        """
        Parse unstructured address using NLP.

        Args:
            address_line: Free-form address text
            country_code: Country code for context
            language: Language of the address

        Returns:
            Parsed address components
        """
        # Use NLP parser for advanced parsing
        return self.nlp_parser.parse_address_advanced(
            address_line, country_code, language
        )
