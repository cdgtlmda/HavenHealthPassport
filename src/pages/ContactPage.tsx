import React from 'react';
import Navigation from '@/components/Navigation';
import Footer from '@/components/Footer';

const ContactPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-black text-white">
      <Navigation />
      <div className="pt-20">
        {/* Blank page - ready for new content */}
      </div>
      <Footer />
    </div>
  );
};

export default ContactPage;