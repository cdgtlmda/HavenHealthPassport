import React, { useState } from 'react';
import { Sidebar, SidebarBody, SidebarLink } from "@/components/ui/sidebar";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LayoutDashboard, Users, FileText, BarChart3, Bell, Settings, Calendar, AlertTriangle, CheckCircle, Clock, Shield, Globe, Activity, AreaChart as MarkAsUnread, Trash2, Filter } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface Notification {
  id: string;
  type: 'alert' | 'info' | 'success' | 'warning';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
  priority: 'high' | 'medium' | 'low';
  category: 'system' | 'patient' | 'blockchain' | 'translation';
}

const notifications: Notification[] = [
  {
    id: "1",
    type: "alert",
    title: "Critical Patient Alert",
    message: "Hassan Al-Mahmoud requires immediate medical attention - PTSD episode reported",
    timestamp: "2024-01-15T10:30:00Z",
    read: false,
    priority: "high",
    category: "patient"
  },
  {
    id: "2",
    type: "success",
    title: "Blockchain Verification Complete",
    message: "Ahmed Hassan's vaccination record has been successfully verified on blockchain",
    timestamp: "2024-01-15T09:15:00Z",
    read: false,
    priority: "medium",
    category: "blockchain"
  },
  {
    id: "3",
    type: "info",
    title: "Translation Quality Alert",
    message: "Arabic to English translation accuracy dropped to 97.2% - review required",
    timestamp: "2024-01-15T08:45:00Z",
    read: true,
    priority: "medium",
    category: "translation"
  },
  {
    id: "4",
    type: "warning",
    title: "System Maintenance Scheduled",
    message: "Blockchain network maintenance scheduled for tonight 2:00 AM - 4:00 AM UTC",
    timestamp: "2024-01-14T16:20:00Z",
    read: true,
    priority: "low",
    category: "system"
  },
  {
    id: "5",
    type: "info",
    title: "New Patient Registration",
    message: "Zara Abdullahi has been successfully registered in the system",
    timestamp: "2024-01-14T14:10:00Z",
    read: true,
    priority: "low",
    category: "patient"
  },
  {
    id: "6",
    type: "alert",
    title: "Offline Sync Failed",
    message: "Mobile app sync failed for Camp Alpha - 23 records pending",
    timestamp: "2024-01-14T12:30:00Z",
    read: false,
    priority: "high",
    category: "system"
  }
];

const NotificationsPage: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [selectedTab, setSelectedTab] = useState("all");

  const links = [
    {
      label: "Dashboard",
      href: "/dashboard",
      icon: (
        <LayoutDashboard className="text-gray-700 h-5 w-5 flex-shrink-0" />
      ),
    },
    {
      label: "Patients",
      href: "/dashboard/patients",
      icon: (
        <Users className="text-gray-700 h-5 w-5 flex-shrink-0" />
      ),
    },
    {
      label: "Schedule",
      href: "/dashboard/schedule",
      icon: (
        <Calendar className="text-gray-700 h-5 w-5 flex-shrink-0" />
      ),
    },
    {
      label: "Records",
      href: "/dashboard/records",
      icon: (
        <FileText className="text-gray-700 h-5 w-5 flex-shrink-0" />
      ),
    },
    {
      label: "Analytics",
      href: "/dashboard/analytics",
      icon: (
        <BarChart3 className="text-gray-700 h-5 w-5 flex-shrink-0" />
      ),
    },
    {
      label: "Notifications",
      href: "/dashboard/notifications",
      icon: (
        <Bell className="text-gray-700 h-5 w-5 flex-shrink-0" />
      ),
    },
    {
      label: "Settings",
      href: "/dashboard/settings",
      icon: (
        <Settings className="text-gray-700 h-5 w-5 flex-shrink-0" />
      ),
    },
  ];

  const Logo = () => {
    return (
      <div className="font-normal flex space-x-2 items-center text-sm text-black py-1 relative z-20">
        <div className="h-5 w-6 bg-gradient-to-r from-primary to-[#9fa0f7] rounded-br-lg rounded-tr-sm rounded-tl-lg rounded-bl-sm flex-shrink-0" />
        <motion.span
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="font-medium text-black whitespace-pre"
        >
          Haven Health
        </motion.span>
      </div>
    );
  };

  const LogoIcon = () => {
    return (
      <div className="font-normal flex space-x-2 items-center text-sm text-black py-1 relative z-20">
        <div className="h-5 w-6 bg-gradient-to-r from-primary to-[#9fa0f7] rounded-br-lg rounded-tr-sm rounded-tl-lg rounded-bl-sm flex-shrink-0" />
      </div>
    );
  };

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'alert':
        return <AlertTriangle className="w-5 h-5 text-red-500" />;
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'warning':
        return <Clock className="w-5 h-5 text-yellow-500" />;
      case 'info':
        return <Activity className="w-5 h-5 text-blue-500" />;
      default:
        return <Bell className="w-5 h-5 text-gray-500" />;
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'patient':
        return <Users className="w-4 h-4" />;
      case 'blockchain':
        return <Shield className="w-4 h-4" />;
      case 'translation':
        return <Globe className="w-4 h-4" />;
      case 'system':
        return <Activity className="w-4 h-4" />;
      default:
        return <Bell className="w-4 h-4" />;
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high':
        return 'bg-red-100 text-red-800';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800';
      case 'low':
        return 'bg-green-100 text-green-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffInHours = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60));
    
    if (diffInHours < 1) {
      return 'Just now';
    } else if (diffInHours < 24) {
      return `${diffInHours}h ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  const filteredNotifications = selectedTab === 'all' 
    ? notifications 
    : selectedTab === 'unread'
    ? notifications.filter(n => !n.read)
    : notifications.filter(n => n.category === selectedTab);

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <div className={cn(
      "flex flex-col md:flex-row bg-gray-50 w-full flex-1 mx-auto border border-gray-200 overflow-hidden",
      "h-screen"
    )}>
      <Sidebar open={open} setOpen={setOpen}>
        <SidebarBody className="justify-between gap-10">
          <div className="flex flex-col flex-1 overflow-y-auto overflow-x-hidden">
            {open ? <Logo /> : <LogoIcon />}
            <div className="mt-8 flex flex-col gap-2">
              {links.map((link, idx) => (
                <SidebarLink key={idx} link={link} />
              ))}
            </div>
          </div>
          <div>
            <SidebarLink
              link={{
                label: "Dr. Sarah Ahmed",
                href: "/dashboard/profile",
                icon: (
                  <Avatar className="h-7 w-7 flex-shrink-0">
                    <AvatarImage src="https://avatars.githubusercontent.com/u/1234567?v=4" />
                    <AvatarFallback className="bg-primary/10 text-primary">SA</AvatarFallback>
                  </Avatar>
                ),
              }}
            />
          </div>
        </SidebarBody>
      </Sidebar>
      
      {/* Main Content */}
      <div className="flex flex-1">
        <div className="p-2 md:p-10 rounded-tl-2xl border border-gray-200 bg-white flex flex-col gap-2 flex-1 w-full h-full overflow-auto">
          <div className="space-y-6">
            {/* Page Header */}
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Notifications</h1>
                <p className="text-gray-600">System alerts and updates for displaced population healthcare</p>
              </div>
              <div className="flex items-center space-x-2">
                <Button variant="outline">
                  <Filter className="w-4 h-4 mr-2" />
                  Filter
                </Button>
                <Button variant="outline">
                  <MarkAsUnread className="w-4 h-4 mr-2" />
                  Mark All Read
                </Button>
              </div>
            </div>

            {/* Notification Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Total Notifications</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{notifications.length}</div>
                  <div className="text-xs text-gray-500">All time</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Unread</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-red-600">{unreadCount}</div>
                  <div className="text-xs text-gray-500">Require attention</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">High Priority</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-orange-600">
                    {notifications.filter(n => n.priority === 'high').length}
                  </div>
                  <div className="text-xs text-gray-500">Critical alerts</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">System Health</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-green-600">99.9%</div>
                  <div className="text-xs text-gray-500">Operational</div>
                </CardContent>
              </Card>
            </div>

            {/* Notification Tabs */}
            <Tabs value={selectedTab} onValueChange={setSelectedTab}>
              <TabsList className="grid w-full grid-cols-6">
                <TabsTrigger value="all">All</TabsTrigger>
                <TabsTrigger value="unread">Unread ({unreadCount})</TabsTrigger>
                <TabsTrigger value="patient">Patient</TabsTrigger>
                <TabsTrigger value="blockchain">Blockchain</TabsTrigger>
                <TabsTrigger value="translation">Translation</TabsTrigger>
                <TabsTrigger value="system">System</TabsTrigger>
              </TabsList>

              <TabsContent value={selectedTab} className="mt-6">
                <div className="space-y-4">
                  {filteredNotifications.map((notification) => (
                    <Card 
                      key={notification.id} 
                      className={cn(
                        "hover:shadow-md transition-shadow cursor-pointer",
                        !notification.read && "border-l-4 border-l-primary bg-blue-50/30"
                      )}
                    >
                      <CardContent className="p-6">
                        <div className="flex items-start justify-between">
                          <div className="flex items-start space-x-4">
                            <div className="mt-1">
                              {getNotificationIcon(notification.type)}
                            </div>
                            <div className="flex-1">
                              <div className="flex items-center space-x-2 mb-1">
                                <h3 className={cn(
                                  "font-semibold",
                                  !notification.read ? "text-gray-900" : "text-gray-700"
                                )}>
                                  {notification.title}
                                </h3>
                                {!notification.read && (
                                  <div className="w-2 h-2 bg-primary rounded-full" />
                                )}
                              </div>
                              <p className="text-gray-600 text-sm mb-2">{notification.message}</p>
                              <div className="flex items-center space-x-4">
                                <div className="flex items-center space-x-1">
                                  {getCategoryIcon(notification.category)}
                                  <span className="text-xs text-gray-500 capitalize">
                                    {notification.category}
                                  </span>
                                </div>
                                <span className="text-xs text-gray-500">
                                  {formatTimestamp(notification.timestamp)}
                                </span>
                              </div>
                            </div>
                          </div>
                          
                          <div className="flex items-center space-x-2">
                            <Badge className={getPriorityColor(notification.priority)}>
                              {notification.priority}
                            </Badge>
                            <Button variant="ghost" size="sm">
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}

                  {filteredNotifications.length === 0 && (
                    <Card>
                      <CardContent className="text-center py-12">
                        <Bell className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                        <p className="text-gray-600">No notifications in this category</p>
                      </CardContent>
                    </Card>
                  )}
                </div>
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NotificationsPage;