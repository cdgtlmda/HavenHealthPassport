import { FileText, Globe, ShieldCheck, Brain, Smartphone } from "lucide-react";

export const features = [
  {
    title: "Offline-First Mobile Access",
    description: "React Native app designed for displaced populations with local storage, intelligent sync, and biometric authentication that works in remote areas without internet connectivity.",
    icon: <Smartphone className="w-6 h-6" />,
    image: "/havenhealth-uploads/86329743-ee49-4f2e-96f7-50508436273d.png"
  },
  {
    title: "AI-Powered Document Processing",
    description: "Multi-language OCR processing handwritten medical documents, vaccination cards, and prescriptions using Amazon Textract with medical terminology detection.",
    icon: <Brain className="w-6 h-6" />,
    image: "/havenhealth-uploads/7335619d-58a9-41ad-a233-f7826f56f3e9.png"
  },
  {
    title: "50+ Language Medical Translation",
    description: "AWS Bedrock-powered translation system supporting refugee languages including Arabic, Kurdish, Dari, Somali, and Amharic with cultural adaptation for medical contexts.",
    icon: <Globe className="w-6 h-6" />,
    image: "/havenhealth-uploads/b6436838-5c1a-419a-9cdc-1f9867df073d.png"
  },
  {
    title: "Blockchain Cross-Border Verification",
    description: "AWS Managed Blockchain with Hyperledger Fabric enabling tamper-proof health record verification at border checkpoints and healthcare facilities worldwide.",
    icon: <ShieldCheck className="w-6 h-6" />,
    image: "/havenhealth-uploads/79f2b901-8a4e-42a5-939f-fae0828e0aef.png"
  },
  {
    title: "FHIR-Compliant Health Records",
    description: "Amazon HealthLake integration with FHIR R4 standards, HL7 messaging, and ICD-10/SNOMED CT mapping for complete healthcare interoperability.",
    icon: <FileText className="w-6 h-6" />,
    image: "/havenhealth-uploads/c32c6788-5e4a-4fee-afee-604b03113c7f.png"
  }
];