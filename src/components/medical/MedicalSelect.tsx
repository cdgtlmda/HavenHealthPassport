import * as React from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface MedicalSelectProps {
  label?: string;
  placeholder?: string;
  options: SelectOption[];
  value?: string | string[];
  onValueChange?: (value: string | string[]) => void;
  error?: string;
  success?: string;
  required?: boolean;
  multiple?: boolean;
  searchable?: boolean;
  className?: string;
}

const MedicalSelect = React.forwardRef<HTMLDivElement, MedicalSelectProps>(
  ({ 
    label, 
    placeholder, 
    options, 
    value, 
    onValueChange, 
    error, 
    success, 
    required, 
    multiple = false,
    searchable = false,
    className 
  }, ref) => {
    const selectId = React.useId();
    const [searchTerm, setSearchTerm] = React.useState("");
    const [selectedValues, setSelectedValues] = React.useState<string[]>(
      multiple ? (Array.isArray(value) ? value : []) : []
    );

    const filteredOptions = searchable 
      ? options.filter(option => 
          option.label.toLowerCase().includes(searchTerm.toLowerCase())
        )
      : options;

    const handleValueChange = (newValue: string) => {
      if (multiple) {
        const updatedValues = selectedValues.includes(newValue)
          ? selectedValues.filter(v => v !== newValue)
          : [...selectedValues, newValue];
        setSelectedValues(updatedValues);
        onValueChange?.(updatedValues);
      } else {
        onValueChange?.(newValue);
      }
    };

    const removeValue = (valueToRemove: string) => {
      const updatedValues = selectedValues.filter(v => v !== valueToRemove);
      setSelectedValues(updatedValues);
      onValueChange?.(updatedValues);
    };

    return (
      <div ref={ref} className={cn("space-y-2", className)}>
        {label && (
          <Label 
            htmlFor={selectId}
            className={cn(
              "text-sm font-medium text-gray-700",
              required && "after:content-['*'] after:ml-0.5 after:text-red-500"
            )}
          >
            {label}
          </Label>
        )}
        
        {multiple && selectedValues.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {selectedValues.map(val => {
              const option = options.find(opt => opt.value === val);
              return (
                <Badge key={val} variant="secondary" className="text-xs">
                  {option?.label || val}
                  <button
                    type="button"
                    onClick={() => removeValue(val)}
                    className="ml-1 hover:text-red-500"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              );
            })}
          </div>
        )}

        <Select 
          value={multiple ? undefined : (value as string)} 
          onValueChange={handleValueChange}
        >
          <SelectTrigger 
            id={selectId}
            className={cn(
              "transition-colors",
              error && "border-red-500 focus:border-red-500 focus:ring-red-500",
              success && "border-green-500 focus:border-green-500 focus:ring-green-500"
            )}
            aria-invalid={!!error}
          >
            <SelectValue placeholder={placeholder} />
          </SelectTrigger>
          <SelectContent>
            {searchable && (
              <div className="p-2">
                <input
                  type="text"
                  placeholder="Search..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full px-2 py-1 text-sm border rounded"
                />
              </div>
            )}
            {filteredOptions.map((option) => (
              <SelectItem 
                key={option.value} 
                value={option.value}
                disabled={option.disabled}
              >
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {error && (
          <p className="text-sm text-red-600" role="alert">
            {error}
          </p>
        )}
        {success && (
          <p className="text-sm text-green-600">
            {success}
          </p>
        )}
      </div>
    );
  }
);

MedicalSelect.displayName = "MedicalSelect";

export { MedicalSelect };