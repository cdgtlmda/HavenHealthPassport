import React from 'react';
import Navigation from '@/components/Navigation';
import Footer from '@/components/Footer';
import { GooeyText } from '@/components/ui/gooey-text-morphing';
import InteractiveScrambledText from '@/components/ui/interactive-scrambled-text';
import { ProfileCard } from '@/components/ui/profile-card';

const AboutMePage: React.FC = () => {
  return (
    <div className="min-h-screen bg-black text-white">
      <Navigation />
      
      {/* Hero Section with Gooey Text */}
      <section className="relative container px-4 pt-40 pb-8">
        <div className="absolute inset-0 -z-10 bg-[#0A0A0A]" />
        
        <div className="max-w-7xl mx-auto text-center relative z-10">
          <div className="h-[120px] flex items-center justify-center mb-4">
            <GooeyText
              texts={["Hi, I'm Cadence"]}
              morphTime={1.5}
              cooldownTime={2}
              className="font-bold text-3xl md:text-4xl lg:text-5xl xl:text-6xl whitespace-nowrap"
              textClassName="text-white"
            />
          </div>
        </div>
      </section>
      
      {/* Personal Journey Section */}
      <section className="container px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold mb-6 text-white">My Journey</h2>
          <InteractiveScrambledText
            radius={120}
            duration={1.5}
            speed={0.4}
            scrambleChars={'.:'}
            className="text-white leading-relaxed text-sm md:text-base lg:text-lg break-words hyphens-auto"
          >
            In 2024, I walked away from anything that no longer aligned with my values, purpose, or creative direction. That decision opened the door to something new — in 2025, I immersed myself in global and in-person hackathons that demanded not just technical skill, but vision. HavenHealth Passport is one of those outcomes.
          </InteractiveScrambledText>
        </div>
      </section>

      {/* Project Origin Section */}
      <section className="container px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold mb-6 text-white">The Challenge</h2>
          <InteractiveScrambledText
            radius={120}
            duration={1.5}
            speed={0.4}
            scrambleChars={'.:'}
            className="text-white leading-relaxed text-sm md:text-base lg:text-lg break-words hyphens-auto"
          >
            Built for the 2025 AWS Breaking Barriers Challenge, this project answers a powerful prompt: build an innovative application that fuses AWS generative AI services with next-generation connectivity — like 5G, IoT, or edge computing — to address urgent societal needs. I chose to tackle a crisis close to my own history: healthcare access for displaced populations.
          </InteractiveScrambledText>
        </div>
      </section>

      {/* Personal Connection Section */}
      <section className="container px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold mb-6 text-white">Personal Connection</h2>
          <InteractiveScrambledText
            radius={120}
            duration={1.5}
            speed={0.4}
            scrambleChars={'.:'}
            className="text-white leading-relaxed text-sm md:text-base lg:text-lg break-words hyphens-auto"
          >
            My parents were refugees from the Vietnam War. They arrived with no records, no documented history, and limited access to care. Their story — and millions like it — inspired me to build something that could restore continuity where it's most often lost: in conflict, in migration, and in the chaos of borderless displacement.
          </InteractiveScrambledText>
        </div>
      </section>

      {/* What I Built Section */}
      <section className="container px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold mb-6 text-white">What I Built</h2>
          <InteractiveScrambledText
            radius={120}
            duration={1.5}
            speed={0.4}
            scrambleChars={'.:'}
            className="text-white leading-relaxed text-sm md:text-base lg:text-lg break-words hyphens-auto"
          >
            HavenHealth Passport is a decentralized, multilingual health record system that gives stateless individuals medically recognized, portable health identities. It combines AI, connectivity, and blockchain infrastructure to deliver trusted, accessible care across borders and systems.
          </InteractiveScrambledText>
        </div>
      </section>

      {/* Core AI/ML Services Section */}
      <section className="container px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold mb-6 text-white">Core AI/ML Services</h2>
          <InteractiveScrambledText
            radius={120}
            duration={1.5}
            speed={0.4}
            scrambleChars={'.:'}
            className="text-white leading-relaxed text-sm md:text-base lg:text-lg break-words hyphens-auto"
          >
            • Amazon Bedrock with Anthropic Claude, Amazon Titan, and Meta Llama2 models for high-fidelity translation of fragmented electronic medical records with cultural adaptation.
            • Amazon SageMaker for custom training of refugee-specific healthcare patterns and real-time inference on language, region, and condition-specific nuances.
            • Amazon Comprehend Medical for PHI detection, medical entity extraction, and translation integrity validation.
            • Amazon Transcribe Medical with domain-specific vocabularies, speaker recognition, and HIPAA-compliant redaction.
            • Amazon Textract for OCR processing of paper-based intake forms, vaccination cards, and scanned medical documents.
            • Amazon Polly to generate multilingual voice summaries using healthcare-specific lexicons — ensuring accessibility for low-literacy users.
            • Amazon Comprehend for analyzing cultural sentiment and preserving tone in care-related translations.
            • Amazon Rekognition for extracting visual medical labels and translating anatomical annotations.
            • Amazon Translate with medical terminology preservation, optimized for both real-time and batch workflows.
          </InteractiveScrambledText>
        </div>
      </section>

      {/* Healthcare & Infrastructure Section */}
      <section className="container px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold mb-6 text-white">Healthcare & Infrastructure Services</h2>
          <InteractiveScrambledText
            radius={120}
            duration={1.5}
            speed={0.4}
            scrambleChars={'.:'}
            className="text-white leading-relaxed text-sm md:text-base lg:text-lg break-words hyphens-auto"
          >
            • AWS HealthLake for FHIR-compliant storage of clinical records and longitudinal patient data across jurisdictions.
            • AWS Managed Blockchain with Hyperledger Fabric for tamper-proof verification of immunization and treatment records.
            • LangChain + LlamaIndex (integrated with Bedrock) for semantic search over decentralized and multilingual archives — enabling clinicians to retrieve relevant case histories and treatment timelines.
            • AWS IoT Core to connect medical devices and synchronize records in real time — even in refugee camps or remote clinics with intermittent connectivity.
            • AWS Nitro Enclaves to enforce hardware-level privacy boundaries, ensuring refugee data remains secure, auditable, and ethically handled.
          </InteractiveScrambledText>
        </div>
      </section>

      {/* Why It Matters Section */}
      <section className="container px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold mb-6 text-white">Why It Matters</h2>
          <InteractiveScrambledText
            radius={120}
            duration={1.5}
            speed={0.4}
            scrambleChars={'.:'}
            className="text-white leading-relaxed text-sm md:text-base lg:text-lg break-words hyphens-auto"
          >
            More than 100 million people today live without consistent access to their medical histories. War, migration, and fractured systems erase critical data — putting lives at risk during treatment. Paper doesn't cross borders. Centralized systems break at the edge. But telecom-grade infrastructure, real-time inference, and generative AI can bridge that gap — if we build for it.

            HavenHealth Passport is my attempt to do exactly that.
          </InteractiveScrambledText>
        </div>
      </section>

      {/* Looking Ahead Section */}
      <section className="container px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold mb-6 text-white">Looking Ahead</h2>
          <InteractiveScrambledText
            radius={120}
            duration={1.5}
            speed={0.4}
            scrambleChars={'.:'}
            className="text-white leading-relaxed text-sm md:text-base lg:text-lg break-words hyphens-auto"
          >
            I didn't build this for awards. I built it because I believe technologists have a responsibility to serve those who are structurally excluded — and to prove that solo developers, with the right tools and conviction, can prototype real change.

            Thank you for visiting my demo. This is only the beginning of what I hope will be a broader conversation — not just about what's possible with AI and edge computing, but who we choose to build for when given the opportunity.

            — Cadence
          </InteractiveScrambledText>
        </div>
      </section>

      {/* Profile Card Section */}
      <section className="container px-4 py-16">
        <div className="max-w-4xl mx-auto">
          <ProfileCard />
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default AboutMePage;