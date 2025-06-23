import * as React from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { 
  Users, 
  FileText, 
  BarChart3, 
  Settings, 
  Shield, 
  Bell,
  Search,
  Plus,
  Menu,
  X,
  Home,
  Calendar,
  MapPin,
  AlertTriangle
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface SidebarItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  href?: string;
  badge?: string | number;
  children?: SidebarItem[];
  onClick?: () => void;
}

export interface MedicalSidebarProps {
  items?: SidebarItem[];
  collapsed?: boolean;
  onToggle?: () => void;
  currentPath?: string;
  patientCount?: number;
  pendingCount?: number;
  className?: string;
}

const defaultItems: SidebarItem[] = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: Home,
    href: '/dashboard'
  },
  {
    id: 'patients',
    label: 'Patients',
    icon: Users,
    href: '/patients',
    badge: '1,234'
  },
  {
    id: 'appointments',
    label: 'Appointments',
    icon: Calendar,
    href: '/appointments',
    badge: '12'
  },
  {
    id: 'records',
    label: 'Medical Records',
    icon: FileText,
    href: '/records'
  },
  {
    id: 'locations',
    label: 'Locations',
    icon: MapPin,
    href: '/locations'
  },
  {
    id: 'analytics',
    label: 'Analytics',
    icon: BarChart3,
    href: '/analytics'
  },
  {
    id: 'alerts',
    label: 'Alerts',
    icon: AlertTriangle,
    href: '/alerts',
    badge: '3'
  }
];

const MedicalSidebar = React.forwardRef<HTMLDivElement, MedicalSidebarProps>(
  ({ 
    items = defaultItems, 
    collapsed = false, 
    onToggle, 
    currentPath = '/dashboard',
    patientCount = 0,
    pendingCount = 0,
    className 
  }, ref) => {
    const [isMobileOpen, setIsMobileOpen] = React.useState(false);

    const SidebarContent = () => (
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className={cn(
          "flex items-center justify-between p-4 border-b border-gray-200",
          collapsed && "px-2"
        )}>
          {!collapsed && (
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                <Shield className="w-5 h-5 text-white" />
              </div>
              <span className="font-semibold text-gray-900">Haven Health</span>
            </div>
          )}
          
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggle}
            className={cn("hidden lg:flex", collapsed && "w-full justify-center")}
          >
            <Menu className="w-4 h-4" />
          </Button>
          
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsMobileOpen(false)}
            className="lg:hidden"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Quick Actions */}
        {!collapsed && (
          <div className="p-4 space-y-2">
            <Button className="w-full justify-start" size="sm">
              <Plus className="w-4 h-4 mr-2" />
              New Patient
            </Button>
            <Button variant="outline" className="w-full justify-start" size="sm">
              <Search className="w-4 h-4 mr-2" />
              Quick Search
            </Button>
          </div>
        )}

        {/* Stats */}
        {!collapsed && (
          <div className="px-4 pb-4">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="bg-blue-50 p-2 rounded">
                <div className="text-blue-600 font-semibold">{patientCount.toLocaleString()}</div>
                <div className="text-blue-500 text-xs">Total Patients</div>
              </div>
              <div className="bg-yellow-50 p-2 rounded">
                <div className="text-yellow-600 font-semibold">{pendingCount}</div>
                <div className="text-yellow-500 text-xs">Pending</div>
              </div>
            </div>
          </div>
        )}

        <Separator />

        {/* Navigation */}
        <nav className="flex-1 p-2 space-y-1">
          {items.map((item) => (
            <SidebarItem
              key={item.id}
              item={item}
              collapsed={collapsed}
              isActive={currentPath === item.href}
            />
          ))}
        </nav>

        <Separator />

        {/* Bottom Section */}
        <div className="p-2 space-y-1">
          <SidebarItem
            item={{
              id: 'notifications',
              label: 'Notifications',
              icon: Bell,
              href: '/notifications',
              badge: '5'
            }}
            collapsed={collapsed}
            isActive={currentPath === '/notifications'}
          />
          <SidebarItem
            item={{
              id: 'settings',
              label: 'Settings',
              icon: Settings,
              href: '/settings'
            }}
            collapsed={collapsed}
            isActive={currentPath === '/settings'}
          />
        </div>
      </div>
    );

    return (
      <>
        {/* Desktop Sidebar */}
        <div
          ref={ref}
          className={cn(
            "hidden lg:flex flex-col bg-white border-r border-gray-200 transition-all duration-300",
            collapsed ? "w-16" : "w-60",
            className
          )}
        >
          <SidebarContent />
        </div>

        {/* Mobile Sidebar */}
        {isMobileOpen && (
          <div className="lg:hidden fixed inset-0 z-50 flex">
            <div className="fixed inset-0 bg-black/50" onClick={() => setIsMobileOpen(false)} />
            <div className="relative flex flex-col w-60 bg-white border-r border-gray-200">
              <SidebarContent />
            </div>
          </div>
        )}

        {/* Mobile Toggle Button */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => setIsMobileOpen(true)}
          className="lg:hidden fixed top-4 left-4 z-40"
        >
          <Menu className="w-4 h-4" />
        </Button>
      </>
    );
  }
);

interface SidebarItemProps {
  item: SidebarItem;
  collapsed: boolean;
  isActive: boolean;
}

const SidebarItem: React.FC<SidebarItemProps> = ({ item, collapsed, isActive }) => {
  const Icon = item.icon;

  return (
    <Button
      variant={isActive ? "secondary" : "ghost"}
      className={cn(
        "w-full justify-start h-9",
        collapsed && "px-2 justify-center",
        isActive && "bg-primary/10 text-primary border-primary/20"
      )}
      onClick={item.onClick}
    >
      <Icon className={cn("w-4 h-4", !collapsed && "mr-2")} />
      {!collapsed && (
        <>
          <span className="flex-1 text-left">{item.label}</span>
          {item.badge && (
            <Badge variant="secondary" className="text-xs">
              {item.badge}
            </Badge>
          )}
        </>
      )}
    </Button>
  );
};

MedicalSidebar.displayName = "MedicalSidebar";

export { MedicalSidebar };