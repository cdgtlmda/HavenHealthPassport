import { motion } from "framer-motion";
import { Avatar, AvatarFallback, AvatarImage } from "./ui/avatar";
import { Card } from "./ui/card";

const testimonials = [
  {
    name: "Dr. Sarah Ahmed",
    role: "Refugee Health Coordinator, MSF",
    image: "https://avatars.githubusercontent.com/u/1234567?v=4",
    content: "Haven Health Passport has transformed how we manage patient records across multiple refugee camps. The blockchain verification gives us confidence in record authenticity, and the offline capability is crucial for remote areas."
  },
  {
    name: "Hassan Al-Rashid",
    role: "Syrian Refugee, Germany",
    image: "https://avatars.githubusercontent.com/u/2345678?v=4",
    content: "Finally, my medical history from Syria is secure and accessible to doctors here in Germany. The AI translation helps doctors understand my previous treatments, and I control who sees my data."
  },
  {
    name: "Dr. Maria Santos",
    role: "Emergency Medicine, Doctors Without Borders",
    image: "https://avatars.githubusercontent.com/u/3456789?v=4",
    content: "The AI document processing saved us countless hours digitizing handwritten medical records. The FHIR integration means we can share data seamlessly with other healthcare systems while maintaining patient privacy."
  },
  {
    name: "Amara Okafor",
    role: "Displaced Person, Nigeria",
    image: "https://avatars.githubusercontent.com/u/4567890?v=4",
    content: "Having my children's vaccination records and medical history secured on blockchain means no matter where we go, their healthcare continues seamlessly. The mobile app works even without internet connection."
  },
  {
    name: "Dr. James Mitchell",
    role: "UNHCR Health Program Officer",
    image: "https://avatars.githubusercontent.com/u/5678901?v=4",
    content: "The platform's compliance with international health standards and its cultural adaptation features make it perfect for diverse refugee populations. The emergency access protocols ensure care is never delayed."
  },
  {
    name: "Fatima Kone",
    role: "Community Health Worker, Mali",
    image: "https://avatars.githubusercontent.com/u/6789012?v=4",
    content: "The multi-language support and cultural adaptation features help us serve refugees from different countries more effectively. The system understands medical terminology in local languages and contexts."
  }
];

const TestimonialsSection = () => {
  return (
    <section className="py-20 overflow-hidden bg-black">
      <div className="container px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="text-center mb-16"
        >
          <h2 className="text-5xl font-normal mb-4 text-white">Trusted by Healthcare Providers</h2>
          <p className="text-gray-300 text-lg">
            Join thousands of healthcare professionals and organizations using Haven Health Passport to serve displaced populations
          </p>
        </motion.div>

        <div className="relative flex flex-col antialiased">
          <div className="relative flex overflow-hidden py-4">
            <div className="animate-marquee flex min-w-full shrink-0 items-stretch gap-8">
              {testimonials.map((testimonial, index) => (
                <Card key={`${index}-1`} className="w-[400px] shrink-0 bg-black/40 backdrop-blur-xl border-white/5 hover:border-white/10 transition-all duration-300 p-8">
                  <div className="flex items-center gap-4 mb-6">
                    <Avatar className="h-12 w-12">
                      <AvatarImage src={testimonial.image} />
                      <AvatarFallback>{testimonial.name[0]}</AvatarFallback>
                    </Avatar>
                    <div>
                      <h4 className="font-medium text-white">{testimonial.name}</h4>
                      <p className="text-sm text-gray-300">{testimonial.role}</p>
                    </div>
                  </div>
                  <p className="text-gray-200 leading-relaxed">
                    {testimonial.content}
                  </p>
                </Card>
              ))}
            </div>
            <div className="animate-marquee flex min-w-full shrink-0 items-stretch gap-8">
              {testimonials.map((testimonial, index) => (
                <Card key={`${index}-2`} className="w-[400px] shrink-0 bg-black/40 backdrop-blur-xl border-white/5 hover:border-white/10 transition-all duration-300 p-8">
                  <div className="flex items-center gap-4 mb-6">
                    <Avatar className="h-12 w-12">
                      <AvatarImage src={testimonial.image} />
                      <AvatarFallback>{testimonial.name[0]}</AvatarFallback>
                    </Avatar>
                    <div>
                      <h4 className="font-medium text-white">{testimonial.name}</h4>
                      <p className="text-sm text-gray-300">{testimonial.role}</p>
                    </div>
                  </div>
                  <p className="text-gray-200 leading-relaxed">
                    {testimonial.content}
                  </p>
                </Card>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default TestimonialsSection;