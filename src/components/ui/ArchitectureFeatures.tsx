import { cn } from "@/lib/utils";
import {
  IconDeviceMobile,
  IconWorld,
  IconBrain,
  IconBlockquote,
  IconDatabase,
  IconShield,
} from "@tabler/icons-react";

export function ArchitectureFeatures() {
  const features = [
    {
      title: "Frontend Applications",
      description:
        "Mobile First: React Native applications optimized for low-bandwidth environments. Progressive Web Apps: Accessible from any device with offline capabilities. Healthcare Provider Portal: Streamlined interfaces for medical professionals.",
      icon: <IconDeviceMobile />,
    },
    {
      title: "Intelligent Backend Services",
      description:
        "GraphQL API: Efficient data fetching optimized for mobile networks. Microservices Architecture: Scalable, maintainable service design. Event-Driven Processing: Real-time updates and synchronization.",
      icon: <IconWorld />,
    },
    {
      title: "AI-Powered Intelligence",
      description:
        "Amazon Bedrock Integration: State-of-the-art language models for medical translation. LangChain Orchestration: Intelligent document processing and understanding. Amazon Comprehend Medical: Automated medical entity recognition. Custom ML Models: Specialized models for refugee healthcare patterns.",
      icon: <IconBrain />,
    },
    {
      title: "Blockchain Infrastructure",
      description:
        "AWS Managed Blockchain: Enterprise-grade Hyperledger Fabric deployment. Smart Contract Verification: Automated health record validation. Blockchain Trust Network: Cross-border verification without central authority.",
      icon: <IconBlockquote />,
    },
    {
      title: "Data Layer",
      description:
        "Amazon HealthLake: FHIR-compliant health data storage. Encrypted Document Storage: Secure S3 repositories with patient-controlled access. OpenSearch Integration: Fast, relevant health information retrieval. DynamoDB: Low-latency metadata and session management.",
      icon: <IconDatabase />,
    },
    {
      title: "Security & Compliance",
      description:
        "Built from the ground up with security and privacy at its core: End-to-end encryption for all health data. HIPAA and GDPR compliance by design. Zero-trust security architecture. Biometric authentication options. Audit trails for all data access.",
      icon: <IconShield />,
    },
  ];
  
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 relative z-10 py-10 max-w-7xl mx-auto">
      {features.map((feature, index) => (
        <Feature key={feature.title} {...feature} index={index} />
      ))}
    </div>
  );
}

const Feature = ({
  title,
  description,
  icon,
  index,
}: {
  title: string;
  description: string;
  icon: React.ReactNode;
  index: number;
}) => {
  return (
    <div
      className={cn(
        "flex flex-col lg:border-r py-10 relative group/feature bg-white border-gray-200",
        (index === 0 || index === 3) && "lg:border-l border-gray-200",
        index < 3 && "lg:border-b border-gray-200"
      )}
    >
      {index < 3 && (
        <div className="opacity-0 group-hover/feature:opacity-100 transition duration-200 absolute inset-0 h-full w-full bg-gradient-to-t from-gray-100 to-transparent pointer-events-none" />
      )}
      {index >= 3 && (
        <div className="opacity-0 group-hover/feature:opacity-100 transition duration-200 absolute inset-0 h-full w-full bg-gradient-to-b from-gray-100 to-transparent pointer-events-none" />
      )}
      <div className="mb-4 relative z-10 px-10 text-gray-600">
        {icon}
      </div>
      <div className="text-lg font-bold mb-2 relative z-10 px-10">
        <div className="absolute left-0 inset-y-0 h-6 group-hover/feature:h-8 w-1 rounded-tr-full rounded-br-full bg-gray-300 group-hover/feature:bg-blue-500 transition-all duration-200 origin-center" />
        <span className="group-hover/feature:translate-x-2 transition duration-200 inline-block text-black">
          {title}
        </span>
      </div>
      <p className="text-sm text-gray-700 max-w-xs relative z-10 px-10">
        {description}
      </p>
    </div>
  );
}; 