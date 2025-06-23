import { motion } from "framer-motion";
import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CardSpotlight } from "./CardSpotlight";
import { Link } from "react-router-dom";

const PricingTier = ({
  name,
  price,
  description,
  features,
  isPopular,
}: {
  name: string;
  price: string;
  description: string;
  features: string[];
  isPopular?: boolean;
}) => (
  <CardSpotlight className={`h-full ${isPopular ? "border-primary" : "border-white/10"} border-2`}>
    <div className="relative h-full p-6 flex flex-col">
      {isPopular && (
        <span className="text-xs font-medium bg-primary/10 text-primary rounded-full px-3 py-1 w-fit mb-4">
          Most Popular
        </span>
      )}
      <h3 className="text-xl font-medium mb-2 text-white">{name}</h3>
      <div className="mb-4">
        <span className="text-4xl font-bold text-white">{price}</span>
        {price !== "Custom" && <span className="text-gray-300">/month</span>}
      </div>
      <p className="text-gray-300 mb-6">{description}</p>
      <ul className="space-y-3 mb-8 flex-grow">
        {features.map((feature, index) => (
          <li key={index} className="flex items-center gap-2">
            <Check className="w-5 h-5 text-primary" />
            <span className="text-sm text-gray-200">{feature}</span>
          </li>
        ))}
      </ul>
      <Link to="/dashboard">
        <Button className="button-gradient w-full">
          Get Access
        </Button>
      </Link>
    </div>
  </CardSpotlight>
);

export const PricingSection = () => {
  return (
    <section className="container px-4 py-24">
      <div className="max-w-2xl mx-auto text-center mb-12">
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-5xl md:text-6xl font-normal mb-6 text-white"
        >
          Pricing Plans{" "}
          <span className="text-gradient font-medium">Access Plan</span>
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.5 }}
          className="text-lg text-gray-300"
        >
          Secure health record access designed for refugees, healthcare providers, and humanitarian organizations
        </motion.p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
        <PricingTier
          name="Individual Access"
          price="Free"
          description="Essential health record access for refugees and displaced individuals"
          features={[
            "Secure blockchain-verified records",
            "Offline-first mobile app",
            "Multi-language interface (20+ languages)",
            "Document scanning with AI OCR",
            "Patient-controlled consent management",
            "24/7 support"
          ]}
        />
        <PricingTier
          name="Healthcare Provider"
          price="$49"
          description="Enhanced features for medical professionals and clinics"
          features={[
            "Advanced patient management dashboard",
            "AI-powered document processing",
            "FHIR data integration",
            "Medical terminology translation",
            "Bulk patient onboarding",
            "Priority support",
            "Analytics and reporting"
          ]}
          isPopular
        />
        <PricingTier
          name="Humanitarian Organization"
          price="Custom"
          description="Enterprise solutions for NGOs and relief organizations"
          features={[
            "Custom Hyperledger Fabric deployment",
            "Unlimited patient records",
            "Advanced compliance tools (HIPAA/GDPR)",
            "Dedicated account manager",
            "Custom API integration",
            "Training and onboarding",
            "24/7 priority support",
            "Multi-organization blockchain network"
          ]}
        />
      </div>
    </section>
  );
};