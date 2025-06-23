import { motion } from "framer-motion";

interface FeatureContentProps {
  image: string;
  title: string;
}

export const FeatureContent = ({ image, title }: FeatureContentProps) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="w-full h-full flex items-stretch"
    >
      <div className="glass rounded-xl overflow-hidden w-full relative h-full">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent" />
        <img
          src={image}
          alt={title}
          className="w-full h-full object-cover relative z-10"
        />
      </div>
    </motion.div>
  );
};