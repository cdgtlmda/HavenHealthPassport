import * as React from "react";
import { MedicalSidebar } from "./MedicalSidebar";
import { MedicalHeader } from "./MedicalHeader";
import { cn } from "@/lib/utils";

export interface MedicalLayoutProps {
  children: React.ReactNode;
  sidebarCollapsed?: boolean;
  onSidebarToggle?: () => void;
  className?: string;
}

const MedicalLayout = React.forwardRef<HTMLDivElement, MedicalLayoutProps>(
  ({ children, sidebarCollapsed = false, onSidebarToggle, className }, ref) => {
    const [collapsed, setCollapsed] = React.useState(sidebarCollapsed);

    const handleToggle = () => {
      setCollapsed(!collapsed);
      onSidebarToggle?.();
    };

    return (
      <div ref={ref} className={cn("flex h-screen bg-gray-50", className)}>
        {/* Sidebar */}
        <MedicalSidebar 
          collapsed={collapsed} 
          onToggle={handleToggle}
          patientCount={1234}
          pendingCount={12}
        />
        
        {/* Main Content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Header */}
          <MedicalHeader 
            notifications={5}
            onSearch={(query) => console.log('Search:', query)}
            onNotificationClick={() => console.log('Notifications clicked')}
            onProfileClick={() => console.log('Profile clicked')}
            onSettingsClick={() => console.log('Settings clicked')}
            onLogout={() => console.log('Logout clicked')}
          />
          
          {/* Page Content */}
          <main className="flex-1 overflow-auto p-6">
            {children}
          </main>
        </div>
      </div>
    );
  }
);

MedicalLayout.displayName = "MedicalLayout";

export { MedicalLayout };