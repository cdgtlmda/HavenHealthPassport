import * as React from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { 
  User, 
  Calendar, 
  MapPin, 
  Phone, 
  AlertCircle, 
  CheckCircle, 
  Clock,
  MoreVertical 
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface PatientData {
  id: string;
  name: string;
  photo?: string;
  dateOfBirth: string;
  gender: 'male' | 'female' | 'other';
  nationality: string;
  phone?: string;
  unhcrId?: string;
  status: 'active' | 'pending' | 'verified' | 'flagged';
  lastVisit?: string;
  medicalAlerts?: string[];
  location?: string;
}

export interface PatientCardProps {
  patient: PatientData;
  onClick?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  className?: string;
  compact?: boolean;
}

const statusConfig = {
  active: { color: 'bg-green-100 text-green-800', icon: CheckCircle },
  pending: { color: 'bg-yellow-100 text-yellow-800', icon: Clock },
  verified: { color: 'bg-blue-100 text-blue-800', icon: CheckCircle },
  flagged: { color: 'bg-red-100 text-red-800', icon: AlertCircle },
};

const PatientCard = React.forwardRef<HTMLDivElement, PatientCardProps>(
  ({ patient, onClick, onEdit, onDelete, className, compact = false }, ref) => {
    const StatusIcon = statusConfig[patient.status].icon;
    
    const calculateAge = (dateOfBirth: string) => {
      const today = new Date();
      const birthDate = new Date(dateOfBirth);
      let age = today.getFullYear() - birthDate.getFullYear();
      const monthDiff = today.getMonth() - birthDate.getMonth();
      
      if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
        age--;
      }
      
      return age;
    };

    const formatDate = (dateString: string) => {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    };

    return (
      <Card 
        ref={ref}
        className={cn(
          "transition-all duration-200 hover:shadow-md cursor-pointer",
          "border border-gray-200 hover:border-gray-300",
          compact && "p-2",
          className
        )}
        onClick={onClick}
      >
        <CardHeader className={cn("pb-3", compact && "pb-2")}>
          <div className="flex items-start justify-between">
            <div className="flex items-center space-x-3">
              <Avatar className={cn("h-12 w-12", compact && "h-8 w-8")}>
                <AvatarImage src={patient.photo} alt={patient.name} />
                <AvatarFallback className="bg-primary/10 text-primary">
                  {patient.name.split(' ').map(n => n[0]).join('').toUpperCase()}
                </AvatarFallback>
              </Avatar>
              
              <div className="flex-1 min-w-0">
                <div className="flex items-center space-x-2">
                  <h3 className={cn(
                    "font-semibold text-gray-900 truncate",
                    compact ? "text-sm" : "text-base"
                  )}>
                    {patient.name}
                  </h3>
                  <Badge 
                    className={cn(
                      "text-xs",
                      statusConfig[patient.status].color
                    )}
                  >
                    <StatusIcon className="w-3 h-3 mr-1" />
                    {patient.status}
                  </Badge>
                </div>
                
                <div className="flex items-center space-x-4 mt-1">
                  <span className={cn(
                    "text-gray-600 flex items-center",
                    compact ? "text-xs" : "text-sm"
                  )}>
                    <User className="w-3 h-3 mr-1" />
                    {calculateAge(patient.dateOfBirth)}y, {patient.gender}
                  </span>
                  
                  {patient.nationality && (
                    <span className={cn(
                      "text-gray-600 flex items-center",
                      compact ? "text-xs" : "text-sm"
                    )}>
                      <MapPin className="w-3 h-3 mr-1" />
                      {patient.nationality}
                    </span>
                  )}
                </div>
              </div>
            </div>
            
            <div className="flex items-center space-x-1">
              {(onEdit || onDelete) && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    // Add dropdown menu logic here
                  }}
                >
                  <MoreVertical className="w-4 h-4" />
                </Button>
              )}
            </div>
          </div>
        </CardHeader>

        {!compact && (
          <CardContent className="pt-0">
            <div className="grid grid-cols-2 gap-4 text-sm">
              {patient.unhcrId && (
                <div>
                  <span className="text-gray-500">UNHCR ID:</span>
                  <p className="font-medium">{patient.unhcrId}</p>
                </div>
              )}
              
              {patient.phone && (
                <div>
                  <span className="text-gray-500 flex items-center">
                    <Phone className="w-3 h-3 mr-1" />
                    Phone:
                  </span>
                  <p className="font-medium">{patient.phone}</p>
                </div>
              )}
              
              {patient.lastVisit && (
                <div>
                  <span className="text-gray-500 flex items-center">
                    <Calendar className="w-3 h-3 mr-1" />
                    Last Visit:
                  </span>
                  <p className="font-medium">{formatDate(patient.lastVisit)}</p>
                </div>
              )}
              
              {patient.location && (
                <div>
                  <span className="text-gray-500">Location:</span>
                  <p className="font-medium">{patient.location}</p>
                </div>
              )}
            </div>
            
            {patient.medicalAlerts && patient.medicalAlerts.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-100">
                <span className="text-xs text-gray-500 mb-2 block">Medical Alerts:</span>
                <div className="flex flex-wrap gap-1">
                  {patient.medicalAlerts.map((alert, index) => (
                    <Badge key={index} variant="outline" className="text-xs bg-red-50 text-red-700 border-red-200">
                      <AlertCircle className="w-3 h-3 mr-1" />
                      {alert}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        )}
      </Card>
    );
  }
);

PatientCard.displayName = "PatientCard";

export { PatientCard };