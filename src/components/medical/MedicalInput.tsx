import * as React from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export interface MedicalInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  success?: string;
  required?: boolean;
  medicalId?: boolean;
  phoneNumber?: boolean;
  units?: string;
}

const MedicalInput = React.forwardRef<HTMLInputElement, MedicalInputProps>(
  ({ className, label, error, success, required, medicalId, phoneNumber, units, ...props }, ref) => {
    const inputId = React.useId();
    
    // Medical ID validation pattern
    const medicalIdPattern = medicalId ? "^[A-Z]{3}[0-9]{6}$" : undefined;
    
    // Phone number formatting
    const formatPhoneNumber = (value: string) => {
      if (!phoneNumber) return value;
      const cleaned = value.replace(/\D/g, '');
      const match = cleaned.match(/^(\d{0,3})(\d{0,3})(\d{0,4})$/);
      if (match) {
        return [match[1], match[2], match[3]].filter(Boolean).join('-');
      }
      return value;
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (phoneNumber) {
        e.target.value = formatPhoneNumber(e.target.value);
      }
      props.onChange?.(e);
    };

    return (
      <div className="space-y-2">
        {label && (
          <Label 
            htmlFor={inputId}
            className={cn(
              "text-sm font-medium text-gray-700",
              required && "after:content-['*'] after:ml-0.5 after:text-red-500"
            )}
          >
            {label}
          </Label>
        )}
        <div className="relative">
          <Input
            id={inputId}
            ref={ref}
            pattern={medicalIdPattern}
            onChange={handleChange}
            className={cn(
              "transition-colors",
              error && "border-red-500 focus:border-red-500 focus:ring-red-500",
              success && "border-green-500 focus:border-green-500 focus:ring-green-500",
              units && "pr-12",
              className
            )}
            aria-invalid={!!error}
            aria-describedby={error ? `${inputId}-error` : success ? `${inputId}-success` : undefined}
            {...props}
          />
          {units && (
            <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
              <span className="text-sm text-gray-500">{units}</span>
            </div>
          )}
        </div>
        {error && (
          <p id={`${inputId}-error`} className="text-sm text-red-600" role="alert">
            {error}
          </p>
        )}
        {success && (
          <p id={`${inputId}-success`} className="text-sm text-green-600">
            {success}
          </p>
        )}
      </div>
    );
  }
);

MedicalInput.displayName = "MedicalInput";

export { MedicalInput };