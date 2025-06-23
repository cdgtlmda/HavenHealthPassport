import { useState } from "react";
import { FeatureTab } from "./FeatureTab";
import { FeatureContent } from "./FeatureContent";
import { features } from "@/config/features";

export const FeaturesSection = () => {
  const [activeFeature, setActiveFeature] = useState(features[0].title);

  return (
    <section className="container px-4 py-24">
      {/* Header Section */}
      <div className="max-w-2xl mb-20">
        <h2 className="text-5xl md:text-6xl font-normal mb-6 tracking-tight text-left text-white">
          Secure Health
          <br />
          <span className="text-gradient font-medium">Records Platform</span>
        </h2>
        <p className="text-lg md:text-xl text-gray-300 text-left">
          Advanced blockchain technology and AI-powered tools designed to protect and manage health records for refugees and displaced populations.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-stretch">
        {/* Left side - Feature buttons */}
        <div className="w-full flex flex-col space-y-3">
          {features.map((feature) => (
            <button
              key={feature.title}
              onClick={() => setActiveFeature(feature.title)}
              className="w-full text-left"
            >
              <FeatureTab
                title={feature.title}
                description={feature.description}
                icon={feature.icon}
                isActive={activeFeature === feature.title}
              />
            </button>
          ))}
        </div>

        {/* Right side - Active feature content */}
        <div className="w-full h-full flex items-stretch">
          {features.map((feature) => 
            activeFeature === feature.title ? (
              <FeatureContent
                key={feature.title}
                image={feature.image}
                title={feature.title}
              />
            ) : null
          )}
        </div>
      </div>
    </section>
  );
};