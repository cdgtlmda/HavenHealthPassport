import { ReactNode } from "react";

interface FeatureTabProps {
  title: string;
  description: string;
  icon: ReactNode;
  isActive: boolean;
}

export const FeatureTab = ({ title, description, icon, isActive }: FeatureTabProps) => {
  return (
    <div
      className={`
        w-full p-6 rounded-xl border transition-all duration-300 text-left
        ${
          isActive
            ? "bg-white/10 border-white/20 shadow-lg"
            : "bg-white/5 border-white/10 hover:bg-white/8 hover:border-white/15"
        }
      `}
    >
      <div className="flex items-start gap-4">
        <div 
          className={`
            flex-shrink-0 w-12 h-12 rounded-lg flex items-center justify-center transition-colors
            ${isActive ? "bg-primary/20 text-primary" : "bg-white/10 text-white/60"}
          `}
        >
          {icon}
        </div>
        
        <div className="flex-1 min-w-0">
          <h3 
            className={`
              text-lg font-semibold mb-2 transition-colors
              ${isActive ? "text-white" : "text-white/80"}
            `}
          >
            {title}
          </h3>
          <p 
            className={`
              text-sm leading-relaxed transition-colors
              ${isActive ? "text-white/90" : "text-white/60"}
            `}
          >
            {description}
          </p>
        </div>
      </div>
    </div>
  );
};