#!/usr/bin/env python3
"""Deploy voice synthesis models to AWS for Haven Health Passport.

CRITICAL: This deploys voice synthesis for healthcare communications.
Clear pronunciation and multi-language support are essential for refugee health.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
import asyncio
import boto3
from botocore.exceptions import ClientError

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.translation.voice.synthesis.voice_synthesizer import (
    VoiceSynthesizer,
    VoiceProfile,
    TTSEngine
)
from src.translation.voice.pronunciation_system import (
    MedicalPronunciationSystem,
    VoiceType
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VoiceSynthesisDeployer:
    """Deploy and configure voice synthesis models for healthcare."""
    
    def __init__(self, region: str = "us-east-1"):
        """Initialize voice synthesis deployer.
        
        Args:
            region: AWS region for deployment
        """
        self.region = region
        self.polly_client = boto3.client("polly", region_name=region)
        self.s3_client = boto3.client("s3", region_name=region)
        self.iam_client = boto3.client("iam", region_name=region)
        self.ssm_client = boto3.client("ssm", region_name=region)
        
        # S3 buckets
        self.audio_bucket = f"haven-health-audio-{region}"
        self.lexicon_bucket = f"haven-health-lexicons-{region}"
        
        # Voice configurations
        self.medical_voices = self._get_medical_voice_configs()
        self.supported_languages = [
            "en", "es", "ar", "fr", "hi", "bn", "sw", "zh", "ru", "pt",
            "fa", "ur", "pa", "ta", "te", "vi", "ko", "ja", "de", "it"
        ]    
    def _get_medical_voice_configs(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get medical-optimized voice configurations."""
        return {
            "en-US": [
                {
                    "VoiceId": "Joanna",
                    "Engine": "neural",
                    "Gender": "Female",
                    "LanguageCode": "en-US",
                    "LanguageName": "US English",
                    "Name": "Joanna (Clear Medical)",
                    "SupportedEngines": ["neural", "standard"],
                    "MedicalOptimized": True
                },
                {
                    "VoiceId": "Matthew",
                    "Engine": "neural",
                    "Gender": "Male",
                    "LanguageCode": "en-US",
                    "LanguageName": "US English",
                    "Name": "Matthew (Professional Medical)",
                    "SupportedEngines": ["neural", "standard"],
                    "MedicalOptimized": True
                }
            ],
            "es-ES": [
                {
                    "VoiceId": "Lupe",
                    "Engine": "neural",
                    "Gender": "Female",
                    "LanguageCode": "es-ES",
                    "LanguageName": "Spanish",
                    "Name": "Lupe (Medical Spanish)",
                    "SupportedEngines": ["neural", "standard"],
                    "MedicalOptimized": True
                }
            ],
            "ar": [
                {
                    "VoiceId": "Zeina",
                    "Engine": "standard",
                    "Gender": "Female",
                    "LanguageCode": "arb",
                    "LanguageName": "Arabic",
                    "Name": "Zeina (Medical Arabic)",
                    "SupportedEngines": ["standard"],
                    "MedicalOptimized": True
                }
            ],
            "hi-IN": [
                {
                    "VoiceId": "Aditi",
                    "Engine": "standard",
                    "Gender": "Female", 
                    "LanguageCode": "hi-IN",
                    "LanguageName": "Hindi",
                    "Name": "Aditi (Medical Hindi)",
                    "SupportedEngines": ["standard"],
                    "MedicalOptimized": True
                }
            ]
        }    
    async def deploy_voice_synthesis(self) -> Dict[str, Any]:
        """Deploy complete voice synthesis infrastructure."""
        logger.info("Deploying voice synthesis infrastructure...")
        
        deployment_results = {
            "timestamp": datetime.now().isoformat(),
            "region": self.region,
            "status": "in_progress",
            "components": {}
        }
        
        try:
            # Step 1: Create S3 buckets
            logger.info("Step 1: Creating S3 buckets...")
            bucket_results = await self._create_s3_buckets()
            deployment_results["components"]["s3_buckets"] = bucket_results
            
            # Step 2: Deploy medical lexicons
            logger.info("Step 2: Deploying medical lexicons...")
            lexicon_results = await self._deploy_medical_lexicons()
            deployment_results["components"]["lexicons"] = lexicon_results
            
            # Step 3: Configure voice profiles
            logger.info("Step 3: Configuring voice profiles...")
            voice_results = await self._configure_voice_profiles()
            deployment_results["components"]["voice_profiles"] = voice_results
            
            # Step 4: Set up pronunciation rules
            logger.info("Step 4: Setting up pronunciation rules...")
            pronunciation_results = await self._setup_pronunciation_rules()
            deployment_results["components"]["pronunciation_rules"] = pronunciation_results
            
            # Step 5: Deploy SSML templates
            logger.info("Step 5: Deploying SSML templates...")
            ssml_results = await self._deploy_ssml_templates()
            deployment_results["components"]["ssml_templates"] = ssml_results
            
            # Step 6: Configure neural voice settings
            logger.info("Step 6: Configuring neural voice settings...")
            neural_results = await self._configure_neural_voices()
            deployment_results["components"]["neural_voices"] = neural_results
            
            # Step 7: Set up voice monitoring
            logger.info("Step 7: Setting up voice monitoring...")
            monitoring_results = await self._setup_voice_monitoring()
            deployment_results["components"]["monitoring"] = monitoring_results
            
            # Step 8: Deploy test suite
            logger.info("Step 8: Deploying test suite...")
            test_results = await self._deploy_test_suite()
            deployment_results["components"]["test_suite"] = test_results
            
            deployment_results["status"] = "completed"
            logger.info("Voice synthesis deployment completed successfully!")
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            deployment_results["status"] = "failed"
            deployment_results["error"] = str(e)
            raise
        
        return deployment_results    
    async def _create_s3_buckets(self) -> Dict[str, Any]:
        """Create S3 buckets for audio storage."""
        results = {"created": [], "existing": [], "errors": []}
        
        buckets = [
            {
                "name": self.audio_bucket,
                "purpose": "Synthesized audio storage",
                "lifecycle": 30  # Days to retain
            },
            {
                "name": self.lexicon_bucket,
                "purpose": "Medical pronunciation lexicons",
                "lifecycle": None  # Keep indefinitely
            }
        ]
        
        for bucket_config in buckets:
            try:
                # Create bucket
                self.s3_client.create_bucket(
                    Bucket=bucket_config["name"],
                    CreateBucketConfiguration={
                        'LocationConstraint': self.region
                    } if self.region != 'us-east-1' else {}
                )
                
                # Enable encryption
                self.s3_client.put_bucket_encryption(
                    Bucket=bucket_config["name"],
                    ServerSideEncryptionConfiguration={
                        'Rules': [{
                            'ApplyServerSideEncryptionByDefault': {
                                'SSEAlgorithm': 'aws:kms',
                                'KMSMasterKeyID': 'alias/haven-health-voice'
                            }
                        }]
                    }
                )
                
                # Set lifecycle policy if specified
                if bucket_config["lifecycle"]:
                    self.s3_client.put_bucket_lifecycle_configuration(
                        Bucket=bucket_config["name"],
                        LifecycleConfiguration={
                            'Rules': [{
                                'ID': 'DeleteOldAudio',
                                'Status': 'Enabled',
                                'ExpirationInDays': bucket_config["lifecycle"],
                                'NoncurrentVersionExpirationInDays': 7
                            }]
                        }
                    )
                
                results["created"].append(bucket_config["name"])
                logger.info(f"Created bucket: {bucket_config['name']}")
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
                    results["existing"].append(bucket_config["name"])
                else:
                    results["errors"].append({
                        "bucket": bucket_config["name"],
                        "error": str(e)
                    })
        
        return results    
    async def _deploy_medical_lexicons(self) -> Dict[str, Any]:
        """Deploy medical pronunciation lexicons to Polly."""
        results = {"deployed": [], "errors": []}
        
        # Medical lexicons for different languages
        lexicons = [
            {
                "name": "medical-terms-en",
                "language": "en-US",
                "content": self._generate_medical_lexicon_en()
            },
            {
                "name": "medical-terms-es",
                "language": "es-ES", 
                "content": self._generate_medical_lexicon_es()
            },
            {
                "name": "medical-terms-ar",
                "language": "ar",
                "content": self._generate_medical_lexicon_ar()
            }
        ]
        
        for lexicon in lexicons:
            try:
                # Put lexicon in Polly
                self.polly_client.put_lexicon(
                    Name=lexicon["name"],
                    Content=lexicon["content"]
                )
                
                # Also save to S3 for backup
                self.s3_client.put_object(
                    Bucket=self.lexicon_bucket,
                    Key=f"lexicons/{lexicon['name']}.xml",
                    Body=lexicon["content"].encode('utf-8'),
                    ContentType='application/xml'
                )
                
                results["deployed"].append({
                    "name": lexicon["name"],
                    "language": lexicon["language"]
                })
                logger.info(f"Deployed lexicon: {lexicon['name']}")
                
            except Exception as e:
                results["errors"].append({
                    "lexicon": lexicon["name"],
                    "error": str(e)
                })
                logger.error(f"Failed to deploy lexicon {lexicon['name']}: {e}")
        
        return results    
    def _generate_medical_lexicon_en(self) -> str:
        """Generate English medical pronunciation lexicon."""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<lexicon version="1.0" 
    xmlns="http://www.w3.org/2005/01/pronunciation-lexicon"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
    xsi:schemaLocation="http://www.w3.org/2005/01/pronunciation-lexicon 
        http://www.w3.org/TR/2007/CR-pronunciation-lexicon-20071212/pls.xsd"
    alphabet="ipa" xml:lang="en-US">
    
    <!-- Common medical terms with pronunciation -->
    <lexeme>
        <grapheme>acetaminophen</grapheme>
        <phoneme>əˌsiːtəˈmɪnəfən</phoneme>
    </lexeme>
    
    <lexeme>
        <grapheme>ibuprofen</grapheme>
        <phoneme>ˌaɪbjuːˈproʊfən</phoneme>
    </lexeme>
    
    <lexeme>
        <grapheme>diabetes</grapheme>
        <phoneme>ˌdaɪəˈbiːtiːz</phoneme>
    </lexeme>
    
    <lexeme>
        <grapheme>hypertension</grapheme>
        <phoneme>ˌhaɪpərˈtɛnʃən</phoneme>
    </lexeme>
    
    <lexeme>
        <grapheme>pneumonia</grapheme>
        <phoneme>nuːˈmoʊnjə</phoneme>
    </lexeme>
    
    <lexeme>
        <grapheme>anesthesia</grapheme>
        <phoneme>ˌænəsˈθiːʒə</phoneme>
    </lexeme>
    
    <!-- Medical abbreviations -->
    <lexeme>
        <grapheme>BP</grapheme>
        <alias>blood pressure</alias>
    </lexeme>
    
    <lexeme>
        <grapheme>IV</grapheme>
        <alias>intravenous</alias>
    </lexeme>
    
    <lexeme>
        <grapheme>ER</grapheme>
        <alias>emergency room</alias>
    </lexeme>
    
    <lexeme>
        <grapheme>ICU</grapheme>
        <alias>intensive care unit</alias>
    </lexeme>
    
</lexicon>'''    
    def _generate_medical_lexicon_es(self) -> str:
        """Generate Spanish medical pronunciation lexicon."""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<lexicon version="1.0" 
    xmlns="http://www.w3.org/2005/01/pronunciation-lexicon"
    alphabet="ipa" xml:lang="es-ES">
    
    <lexeme>
        <grapheme>paracetamol</grapheme>
        <phoneme>paɾaθetaˈmol</phoneme>
    </lexeme>
    
    <lexeme>
        <grapheme>ibuprofeno</grapheme>
        <phoneme>iβupɾoˈfeno</phoneme>
    </lexeme>
    
    <lexeme>
        <grapheme>diabetes</grapheme>
        <phoneme>djaˈβetes</phoneme>
    </lexeme>
    
    <lexeme>
        <grapheme>hipertensión</grapheme>
        <phoneme>ipeɾtenˈsjon</phoneme>
    </lexeme>
    
</lexicon>'''
    
    def _generate_medical_lexicon_ar(self) -> str:
        """Generate Arabic medical pronunciation lexicon."""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<lexicon version="1.0" 
    xmlns="http://www.w3.org/2005/01/pronunciation-lexicon"
    alphabet="ipa" xml:lang="ar">
    
    <lexeme>
        <grapheme>السكري</grapheme>
        <phoneme>assukkari</phoneme>
    </lexeme>
    
    <lexeme>
        <grapheme>ضغط الدم</grapheme>
        <phoneme>daght addam</phoneme>
    </lexeme>
    
</lexicon>'''    
    async def _configure_voice_profiles(self) -> Dict[str, Any]:
        """Configure voice profiles for medical use."""
        results = {"configured": [], "errors": []}
        
        # Get available voices
        try:
            response = self.polly_client.describe_voices()
            available_voices = response['Voices']
            
            # Filter and categorize voices for medical use
            medical_voices = {}
            
            for voice in available_voices:
                lang_code = voice['LanguageCode']
                
                # Check if voice supports neural engine (preferred for clarity)
                if 'neural' in voice.get('SupportedEngines', []):
                    if lang_code not in medical_voices:
                        medical_voices[lang_code] = []
                    
                    medical_voices[lang_code].append({
                        "VoiceId": voice['Id'],
                        "Gender": voice['Gender'],
                        "Name": voice['Name'],
                        "Engine": "neural",
                        "ClearPronunciation": True
                    })
            
            # Store configuration in SSM Parameter Store
            for lang_code, voices in medical_voices.items():
                param_name = f"/haven-health/voice-synthesis/{lang_code}/voices"
                
                self.ssm_client.put_parameter(
                    Name=param_name,
                    Value=json.dumps(voices),
                    Type='String',
                    Overwrite=True,
                    Description=f"Medical voice profiles for {lang_code}"
                )
                
                results["configured"].append({
                    "language": lang_code,
                    "voice_count": len(voices)
                })
            
        except Exception as e:
            results["errors"].append(str(e))
            logger.error(f"Failed to configure voice profiles: {e}")
        
        return results    
    async def _setup_pronunciation_rules(self) -> Dict[str, Any]:
        """Set up pronunciation rules for medical terms."""
        results = {"rules_created": 0, "languages": []}
        
        # Pronunciation rules for different languages
        pronunciation_rules = {
            "en": {
                "number_format": "cardinal",  # one, two, three
                "date_format": "mdy",  # month day year
                "time_format": "12hour",  # 3:30 PM
                "abbreviation_mode": "expand"  # Expand medical abbreviations
            },
            "es": {
                "number_format": "cardinal",
                "date_format": "dmy",  # día mes año
                "time_format": "24hour",  # 15:30
                "abbreviation_mode": "expand"
            },
            "ar": {
                "number_format": "cardinal",
                "date_format": "dmy",
                "time_format": "24hour",
                "abbreviation_mode": "expand",
                "reading_direction": "rtl"  # Right to left
            }
        }
        
        for lang, rules in pronunciation_rules.items():
            try:
                # Store rules in Parameter Store
                param_name = f"/haven-health/voice-synthesis/{lang}/pronunciation-rules"
                
                self.ssm_client.put_parameter(
                    Name=param_name,
                    Value=json.dumps(rules),
                    Type='String',
                    Overwrite=True,
                    Description=f"Pronunciation rules for {lang}"
                )
                
                results["rules_created"] += 1
                results["languages"].append(lang)
                
            except Exception as e:
                logger.error(f"Failed to set pronunciation rules for {lang}: {e}")
        
        return results    
    async def _deploy_ssml_templates(self) -> Dict[str, Any]:
        """Deploy SSML templates for medical communications."""
        results = {"templates_deployed": [], "errors": []}
        
        # SSML templates for different medical scenarios
        ssml_templates = [
            {
                "name": "medication_instruction",
                "template": '''<speak>
    <prosody rate="90%">
        <emphasis level="strong">{medication_name}</emphasis>
        <break time="500ms"/>
        Take <emphasis level="moderate">{dosage}</emphasis>
        <break time="300ms"/>
        <emphasis level="moderate">{frequency}</emphasis>
        <break time="500ms"/>
        {additional_instructions}
    </prosody>
</speak>'''
            },
            {
                "name": "appointment_reminder",
                "template": '''<speak>
    <prosody rate="95%">
        You have an appointment with 
        <emphasis level="moderate">{doctor_name}</emphasis>
        on <say-as interpret-as="date" format="mdy">{date}</say-as>
        at <say-as interpret-as="time" format="12hour">{time}</say-as>
        <break time="500ms"/>
        Please arrive 15 minutes early.
    </prosody>
</speak>'''
            },
            {
                "name": "emergency_instruction",
                "template": '''<speak>
    <prosody rate="85%" pitch="+5%">
        <emphasis level="strong">Important medical instruction:</emphasis>
        <break time="700ms"/>
        {instruction}
        <break time="500ms"/>
        <emphasis level="strong">If you have questions, contact your healthcare provider immediately.</emphasis>
    </prosody>
</speak>'''
            }
        ]
        
        for template in ssml_templates:
            try:
                # Store template in S3
                key = f"ssml-templates/{template['name']}.xml"
                
                self.s3_client.put_object(
                    Bucket=self.lexicon_bucket,
                    Key=key,
                    Body=template['template'].encode('utf-8'),
                    ContentType='application/xml',
                    Metadata={
                        'template-name': template['name'],
                        'template-type': 'medical-ssml'
                    }
                )
                
                results["templates_deployed"].append(template['name'])
                logger.info(f"Deployed SSML template: {template['name']}")
                
            except Exception as e:
                results["errors"].append({
                    "template": template['name'],
                    "error": str(e)
                })
        
        return results    
    async def _configure_neural_voices(self) -> Dict[str, Any]:
        """Configure neural voice settings for clarity."""
        results = {"configured": [], "errors": []}
        
        # Neural voice settings optimized for medical clarity
        neural_settings = {
            "speaking_rate": "90%",  # Slightly slower for clarity
            "pitch": "0%",  # Natural pitch
            "volume": "loud",  # Clear volume
            "timbre": "100%",  # Full timbre for clarity
            "stress": "moderate",  # Natural stress patterns
            "engine": "neural",
            "neural_voice_style": "professional"
        }
        
        try:
            # Store neural voice settings
            param_name = "/haven-health/voice-synthesis/neural-settings"
            
            self.ssm_client.put_parameter(
                Name=param_name,
                Value=json.dumps(neural_settings),
                Type='String',
                Overwrite=True,
                Description="Neural voice settings for medical clarity"
            )
            
            results["configured"].append("neural_settings")
            
            # Configure language-specific neural settings
            language_specific = {
                "en": {"speaking_rate": "92%"},
                "es": {"speaking_rate": "88%"},
                "ar": {"speaking_rate": "85%", "pitch": "-2%"},
                "zh": {"speaking_rate": "85%"},
                "hi": {"speaking_rate": "88%"}
            }
            
            for lang, settings in language_specific.items():
                merged_settings = {**neural_settings, **settings}
                param_name = f"/haven-health/voice-synthesis/{lang}/neural-settings"
                
                self.ssm_client.put_parameter(
                    Name=param_name,
                    Value=json.dumps(merged_settings),
                    Type='String',
                    Overwrite=True
                )
                
                results["configured"].append(f"neural_settings_{lang}")
                
        except Exception as e:
            results["errors"].append(str(e))
            logger.error(f"Failed to configure neural voices: {e}")
        
        return results    
    async def _setup_voice_monitoring(self) -> Dict[str, Any]:
        """Set up monitoring for voice synthesis."""
        results = {"metrics_created": [], "alarms_created": [], "errors": []}
        
        cloudwatch = boto3.client('cloudwatch', region_name=self.region)
        
        # Create custom metrics namespace
        namespace = 'HavenHealth/VoiceSynthesis'
        
        # Define alarms
        alarms = [
            {
                'AlarmName': 'HighPollyLatency',
                'MetricName': 'SynthesisLatency',
                'Namespace': namespace,
                'Statistic': 'Average',
                'Period': 300,
                'EvaluationPeriods': 2,
                'Threshold': 1000,  # 1 second
                'ComparisonOperator': 'GreaterThanThreshold',
                'AlarmDescription': 'Alert when voice synthesis takes too long'
            },
            {
                'AlarmName': 'PollyThrottling',
                'MetricName': 'ThrottledRequests',
                'Namespace': 'AWS/Polly',
                'Statistic': 'Sum',
                'Period': 300,
                'EvaluationPeriods': 1,
                'Threshold': 5,
                'ComparisonOperator': 'GreaterThanThreshold',
                'AlarmDescription': 'Alert on Polly throttling'
            }
        ]
        
        for alarm in alarms:
            try:
                cloudwatch.put_metric_alarm(**alarm)
                results["alarms_created"].append(alarm['AlarmName'])
            except Exception as e:
                results["errors"].append({
                    "alarm": alarm['AlarmName'],
                    "error": str(e)
                })
        
        return results
    
    async def _deploy_test_suite(self) -> Dict[str, Any]:
        """Deploy test suite for voice synthesis."""
        results = {"tests_deployed": [], "errors": []}
        
        # Test cases for different languages and scenarios
        test_cases = [
            {
                "name": "english_medication",
                "language": "en-US",
                "text": "Take 2 tablets of acetaminophen every 6 hours with food.",
                "expected_duration": 3.5
            },
            {
                "name": "spanish_appointment",
                "language": "es-ES",
                "text": "Su cita es el 15 de enero a las 3:30 de la tarde.",
                "expected_duration": 3.0
            },
            {
                "name": "arabic_instruction",
                "language": "ar",
                "text": "تناول الدواء مرتين في اليوم",
                "expected_duration": 2.5
            }
        ]
        
        # Store test cases
        for test in test_cases:
            try:
                key = f"test-cases/{test['name']}.json"
                
                self.s3_client.put_object(
                    Bucket=self.lexicon_bucket,
                    Key=key,
                    Body=json.dumps(test).encode('utf-8'),
                    ContentType='application/json'
                )
                
                results["tests_deployed"].append(test['name'])
                
            except Exception as e:
                results["errors"].append({
                    "test": test['name'],
                    "error": str(e)
                })
        
        return results    
    async def test_voice_synthesis(self, language: str = "en-US") -> Dict[str, Any]:
        """Test voice synthesis deployment."""
        logger.info(f"Testing voice synthesis for {language}...")
        
        test_results = {
            "language": language,
            "timestamp": datetime.now().isoformat(),
            "tests": []
        }
        
        # Test text
        test_texts = {
            "en-US": "Your blood pressure medication is ready. Take one tablet daily with breakfast.",
            "es-ES": "Su medicamento para la presión arterial está listo. Tome una tableta al día con el desayuno.",
            "ar": "دواء ضغط الدم جاهز. تناول قرصًا واحدًا يوميًا مع الإفطار."
        }
        
        test_text = test_texts.get(language, test_texts["en-US"])
        
        try:
            # Get voice for language
            response = self.polly_client.describe_voices(LanguageCode=language)
            if not response['Voices']:
                raise ValueError(f"No voices available for {language}")
            
            # Use first available neural voice, or fallback to standard
            voice = None
            for v in response['Voices']:
                if 'neural' in v.get('SupportedEngines', []):
                    voice = v
                    break
            
            if not voice:
                voice = response['Voices'][0]
            
            # Test 1: Basic synthesis
            start_time = time.time()
            
            synth_response = self.polly_client.synthesize_speech(
                Text=test_text,
                OutputFormat='mp3',
                VoiceId=voice['Id'],
                Engine='neural' if 'neural' in voice.get('SupportedEngines', []) else 'standard'
            )
            
            synthesis_time = time.time() - start_time
            audio_data = synth_response['AudioStream'].read()
            
            test_results["tests"].append({
                "test": "basic_synthesis",
                "passed": len(audio_data) > 0,
                "synthesis_time": synthesis_time,
                "audio_size": len(audio_data),
                "voice_used": voice['Id']
            })
            
            # Test 2: SSML synthesis
            ssml_text = f'''<speak>
                <prosody rate="90%">
                    <emphasis level="strong">{test_text}</emphasis>
                </prosody>
            </speak>'''
            
            start_time = time.time()
            
            ssml_response = self.polly_client.synthesize_speech(
                Text=ssml_text,
                TextType='ssml',
                OutputFormat='mp3',
                VoiceId=voice['Id'],
                Engine='neural' if 'neural' in voice.get('SupportedEngines', []) else 'standard'
            )
            
            ssml_time = time.time() - start_time
            ssml_audio = ssml_response['AudioStream'].read()
            
            test_results["tests"].append({
                "test": "ssml_synthesis",
                "passed": len(ssml_audio) > 0,
                "synthesis_time": ssml_time,
                "audio_size": len(ssml_audio)
            })
            
            # Test 3: Medical lexicon
            if language == "en-US":
                medical_text = "Take acetaminophen for pain and ibuprofen for inflammation."
                
                med_response = self.polly_client.synthesize_speech(
                    Text=medical_text,
                    OutputFormat='mp3',
                    VoiceId=voice['Id'],
                    Engine='neural' if 'neural' in voice.get('SupportedEngines', []) else 'standard',
                    LexiconNames=['medical-terms-en']
                )
                
                med_audio = med_response['AudioStream'].read()
                
                test_results["tests"].append({
                    "test": "medical_lexicon",
                    "passed": len(med_audio) > 0,
                    "audio_size": len(med_audio)
                })
            
            test_results["overall_status"] = "passed"
            
        except Exception as e:
            logger.error(f"Voice synthesis test failed: {e}")
            test_results["overall_status"] = "failed"
            test_results["error"] = str(e)
        
        return test_results

from datetime import datetime
import time


async def main():
    """Main deployment function."""
    parser = argparse.ArgumentParser(
        description="Deploy voice synthesis models for Haven Health Passport"
    )
    
    parser.add_argument(
        "action",
        choices=["deploy", "test", "list-voices", "update-lexicons"],
        help="Action to perform"
    )
    
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)"
    )
    
    parser.add_argument(
        "--language",
        default="en-US",
        help="Language for testing (default: en-US)"
    )
    
    parser.add_argument(
        "--skip-buckets",
        action="store_true",
        help="Skip S3 bucket creation"
    )
    
    parser.add_argument(
        "--output",
        default="voice_synthesis_deployment.json",
        help="Output file for deployment results"
    )
    
    args = parser.parse_args()
    
    # Initialize deployer
    deployer = VoiceSynthesisDeployer(region=args.region)
    
    if args.action == "deploy":
        logger.info("Starting voice synthesis deployment...")
        logger.info("CRITICAL: This deploys healthcare voice systems for refugees")
        
        # Confirm deployment
        confirm = input("Deploy voice synthesis to production? (yes/no): ")
        if confirm.lower() != "yes":
            logger.info("Deployment cancelled")
            return
        
        # Run deployment
        results = await deployer.deploy_voice_synthesis()
        
        # Save results
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Deployment results saved to {args.output}")
        
        # Run basic test
        if results["status"] == "completed":
            logger.info("Running deployment verification...")
            test_results = await deployer.test_voice_synthesis()
            
            if test_results["overall_status"] == "passed":
                logger.info("✓ Voice synthesis deployment verified!")
            else:
                logger.error("✗ Voice synthesis verification failed!")
    
    elif args.action == "test":
        test_results = await deployer.test_voice_synthesis(args.language)
        print(json.dumps(test_results, indent=2))
        
    elif args.action == "list-voices":
        try:
            response = deployer.polly_client.describe_voices()
            
            print(f"\nAvailable voices for medical use:")
            print(f"{'Language':<15} {'Voice ID':<20} {'Gender':<10} {'Engine':<15}")
            print("-" * 60)
            
            for voice in sorted(response['Voices'], key=lambda x: x['LanguageCode']):
                engines = ', '.join(voice.get('SupportedEngines', ['standard']))
                print(f"{voice['LanguageCode']:<15} {voice['Id']:<20} {voice['Gender']:<10} {engines:<15}")
        
        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
    
    elif args.action == "update-lexicons":
        logger.info("Updating medical lexicons...")
        results = await deployer._deploy_medical_lexicons()
        print(json.dumps(results, indent=2))
    
    logger.info("Operation completed")


if __name__ == "__main__":
    # Run async main
    asyncio.run(main())