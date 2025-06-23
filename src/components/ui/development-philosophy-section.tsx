import { cn } from "@/lib/utils";
import {
  IconUsers,
  IconShield,
  IconDeviceMobile,
  IconGauge,
} from "@tabler/icons-react";

export function DevelopmentPhilosophySection() {
  const features = [
    {
      title: "User-Centered Design",
      description:
        "Every feature is designed with input from refugees, healthcare workers, and aid organizations. The platform prioritizes usability in challenging environments over technical complexity.",
      details: [
        "Direct feedback from refugee communities and healthcare workers",
        "Iterative design process with field testing",
        "Accessibility-first approach for diverse user needs",
        "Cultural sensitivity in interface design",
        "Simplified workflows for high-stress environments"
      ],
      icon: <IconUsers />,
    },
    {
      title: "Security Without Compromise",
      description:
        "Healthcare data demands the highest security standards. The implementation includes defense-in-depth strategies, end-to-end encryption, and regular security audits.",
      details: [
        "End-to-end encryption for all medical data",
        "Zero-knowledge proof systems for verification",
        "Regular penetration testing and security audits",
        "HIPAA and GDPR compliance by design",
        "Multi-factor authentication and access controls"
      ],
      icon: <IconShield />,
    },
    {
      title: "Built for Reality",
      description:
        "Technology choices reflect field realities: intermittent connectivity, device constraints, language diversity, and the need for immediate usability under stress.",
      details: [
        "Offline-first architecture for unreliable networks",
        "Optimized for low-end smartphones and tablets",
        "Support for 50+ languages with cultural adaptation",
        "Battery-efficient design for extended field use",
        "Resilient to infrastructure failures and conflicts"
      ],
      icon: <IconDeviceMobile />,
    },
    {
      title: "Performance at Scale",
      description:
        "Optimized for everything from low-end smartphones to high-volume border checkpoints, ensuring consistent performance across all deployment scenarios.",
      details: [
        "Horizontal scaling for millions of users",
        "Multi-region deployment with automatic failover",
        "Intelligent caching and data synchronization",
        "Load balancing for high-traffic scenarios",
        "Performance monitoring and optimization"
      ],
      icon: <IconGauge />,
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 relative z-10 py-10 max-w-7xl mx-auto">
      {features.map((feature, index) => (
        <Feature key={feature.title} {...feature} index={index} />
      ))}
    </div>
  );
}

const Feature = ({
  title,
  description,
  details,
  icon,
  index,
}: {
  title: string;
  description: string;
  details: string[];
  icon: React.ReactNode;
  index: number;
}) => {
  return (
    <div
      className={cn(
        "flex flex-col lg:border-r py-10 relative group/feature dark:border-neutral-800",
        (index === 0 || index === 2) && "lg:border-l dark:border-neutral-800",
        index < 2 && "lg:border-b dark:border-neutral-800"
      )}
    >
      {index < 2 && (
        <div className="opacity-0 group-hover/feature:opacity-100 transition duration-200 absolute inset-0 h-full w-full bg-gradient-to-t from-neutral-100 dark:from-neutral-800 to-transparent pointer-events-none" />
      )}
      {index >= 2 && (
        <div className="opacity-0 group-hover/feature:opacity-100 transition duration-200 absolute inset-0 h-full w-full bg-gradient-to-b from-neutral-100 dark:from-neutral-800 to-transparent pointer-events-none" />
      )}
      <div className="mb-4 relative z-10 px-10 text-neutral-600 dark:text-neutral-400">
        {icon}
      </div>
      <div className="text-lg font-bold mb-2 relative z-10 px-10">
        <div className="absolute left-0 inset-y-0 h-6 group-hover/feature:h-8 w-1 rounded-tr-full rounded-br-full bg-neutral-300 dark:bg-neutral-700 group-hover/feature:bg-purple-500 transition-all duration-200 origin-center" />
        <span className="group-hover/feature:translate-x-2 transition duration-200 inline-block text-neutral-800 dark:text-neutral-100">
          {title}
        </span>
      </div>
      <p className="text-sm text-neutral-600 dark:text-neutral-300 mb-4 relative z-10 px-10">
        {description}
      </p>
      <ul className="text-xs text-neutral-500 dark:text-neutral-400 space-y-1 relative z-10 px-10">
        {details.map((detail, detailIndex) => (
          <li key={detailIndex} className="opacity-0 group-hover/feature:opacity-100 transition duration-300 delay-100">
            • {detail}
          </li>
        ))}
      </ul>
    </div>
  );
}; 