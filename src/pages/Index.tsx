import Footer from "@/components/Footer";
import LogoCarousel from "@/components/LogoCarousel";
import Navigation from "@/components/Navigation";
import TestimonialsSection from "@/components/TestimonialsSection";
import { FeaturesSection } from "@/components/features/FeaturesSection";
import { PricingSection } from "@/components/pricing/PricingSection";
import { WelcomeDialog } from "@/components/ui/WelcomeDialog";
import { Button } from "@/components/ui/button";
import { TextGenerateEffect } from "@/components/ui/text-generate-effect";
import { WorldMap } from "@/components/ui/world-map";
import { motion } from "framer-motion";
import { ArrowRight, Command } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

const Index = () => {
  const [showWelcomeDialog, setShowWelcomeDialog] = useState(false);

  useEffect(() => {
    // Check if user has seen the welcome dialog before
    const hasSeenWelcome = localStorage.getItem("hasSeenWelcomeDialog");

    if (!hasSeenWelcome) {
      // Show dialog after a short delay for better UX
      const timer = setTimeout(() => {
        setShowWelcomeDialog(true);
      }, 1000);

      return () => clearTimeout(timer);
    }
  }, []);

  const handleWelcomeDialogClose = (open: boolean) => {
    setShowWelcomeDialog(open);
    if (!open) {
      // Mark that user has seen the welcome dialog
      localStorage.setItem("hasSeenWelcomeDialog", "true");
    }
  };

  return (
    <div className="min-h-screen bg-black text-white">
      <Navigation />

      {/* Welcome Dialog */}
      <WelcomeDialog open={showWelcomeDialog} onOpenChange={handleWelcomeDialogClose} />

      {/* Hero Section */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative container px-4 pt-40 pb-20"
      >
        {/* Background */}
        <div className="absolute inset-0 -z-10 bg-[#0A0A0A]" />

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="inline-block mb-4 px-4 py-1.5 rounded-full button-gradient"
        >
          <span className="text-sm font-medium text-white">
            <Command className="w-4 h-4 inline-block mr-2 text-white" />
            Serving 100+ million displaced people globally
          </span>
        </motion.div>

        <div className="max-w-4xl relative z-10">
          <h1 className="text-5xl md:text-7xl font-normal mb-4 tracking-tight text-left">
            <span className="text-white">
              <TextGenerateEffect words="Blockchain-verified health records" />
            </span>
            <br />
            <span className="text-white font-medium">
              <TextGenerateEffect words="for displaced populations" />
            </span>
          </h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="text-lg md:text-xl text-gray-200 mb-8 max-w-2xl text-left"
          >
            A blockchain-verified health record management system addressing critical
            challenges faced by refugees and migrants. Features AI-powered translation,
            offline-first mobile access, and secure patient-controlled data sharing.{" "}
            <span className="text-white">Healthcare continuity across borders.</span>
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="flex flex-col sm:flex-row gap-4 items-start"
          >
            <Link to="/dashboard">
              <Button size="lg" className="button-gradient">
                Access Medical Dashboard
                <ArrowRight className="ml-2 w-4 h-4" />
              </Button>
            </Link>
            <Link to="/demos">
              <Button
                size="lg"
                variant="link"
                className="text-white hover:text-gray-200"
              >
                View System Demos <ArrowRight className="ml-2 w-4 h-4" />
              </Button>
            </Link>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="relative mx-auto max-w-5xl mt-20"
        >
          <div className="glass rounded-xl overflow-hidden">
            <img
              src="/Haven-main.png"
              alt="Haven Health Passport Platform Dashboard"
              className="w-full h-auto"
            />
          </div>
        </motion.div>
      </motion.section>

      {/* Logo Carousel */}
      <LogoCarousel />

      {/* Features Section */}
      <div id="features" className="bg-black">
        <FeaturesSection />
      </div>

      {/* Pricing Section */}
      <div id="pricing" className="bg-black">
        <PricingSection />
      </div>

      {/* Testimonials Section */}
      <div className="bg-black">
        <TestimonialsSection />
      </div>

      {/* CTA Section */}
      <section className="container px-4 py-12 relative bg-black">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="bg-gradient-to-r from-primary to-[#9fa0f7] rounded-xl p-8 md:p-12 text-center relative z-10"
        >
          <h2 className="text-3xl md:text-4xl font-bold mb-4 text-white">
            Ready to experience portable healthcare records?
          </h2>
          <p className="text-lg text-white/80 mb-8 max-w-2xl mx-auto">
            Experience the HIPAA-compliant platform with blockchain verification,
            AI-powered translation, and offline-first design supporting 50+ languages
            with medical accuracy.
          </p>
          <Link to="/dashboard">
            <Button size="lg" className="bg-white text-primary hover:bg-white/90">
              Access Medical Dashboard
              <ArrowRight className="ml-2 w-4 h-4" />
            </Button>
          </Link>
        </motion.div>
      </section>

      {/* World Map Section */}
      <section className="container px-4 py-20 relative bg-black">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="max-w-7xl mx-auto text-center"
        >
          <h2 className="text-3xl md:text-4xl font-bold mb-4 text-white">
            Borderless{" "}
            <motion.span
              className="text-primary"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
            >
              Health Access
            </motion.span>
          </h2>
          <p className="text-lg text-gray-200 max-w-3xl mx-auto mb-12">
            Keep medical history within reach—whether at a remote border crossing, a
            field clinic, or a refugee camp. Designed for displaced individuals, aid
            workers, and healthcare teams serving vulnerable populations.
          </p>
          <WorldMap
            dots={[
              {
                start: { lat: 33.8869, lng: 35.5131 }, // Lebanon (Beirut)
                end: { lat: 52.52, lng: 13.405 }, // Germany (Berlin)
              },
              {
                start: { lat: 23.8859, lng: 45.0792 }, // Saudi Arabia (Riyadh)
                end: { lat: 41.9028, lng: 12.4964 }, // Italy (Rome)
              },
              {
                start: { lat: 39.9042, lng: 32.8597 }, // Turkey (Ankara)
                end: { lat: 59.3293, lng: 18.0686 }, // Sweden (Stockholm)
              },
              {
                start: { lat: 6.5244, lng: 3.3792 }, // Nigeria (Lagos)
                end: { lat: 51.5074, lng: -0.1278 }, // UK (London)
              },
              {
                start: { lat: 34.0522, lng: -118.2437 }, // USA (Los Angeles)
                end: { lat: 45.4215, lng: -75.6972 }, // Canada (Ottawa)
              },
              {
                start: { lat: -1.2921, lng: 36.8219 }, // Kenya (Nairobi)
                end: { lat: -26.2041, lng: 28.0473 }, // South Africa (Johannesburg)
              },
            ]}
            lineColor="#6366f1"
          />
        </motion.div>
      </section>

      {/* Footer */}
      <div className="bg-black">
        <Footer />
      </div>
    </div>
  );
};

export default Index;
