"use client"

import { FullScreenCalendar } from "@/components/ui/fullscreen-calendar"
import { Sidebar, SidebarBody, SidebarLink } from "@/components/ui/sidebar";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { 
  LayoutDashboard,
  Users,
  FileText,
  BarChart3,
  Bell,
  Settings,
  Calendar
} from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useState } from "react";

// Medical appointment data for refugee healthcare
const medicalAppointments = [
  {
    day: new Date("2025-01-02"),
    events: [
      {
        id: 1,
        name: "Ahmed Hassan - General Checkup",
        time: "10:00 AM",
        datetime: "2025-01-02T10:00",
      },
      {
        id: 2,
        name: "Fatima Al-Rashid - Prenatal Care",
        time: "2:00 PM",
        datetime: "2025-01-02T14:00",
      },
    ],
  },
  {
    day: new Date("2025-01-07"),
    events: [
      {
        id: 3,
        name: "Omar Kone - Asthma Follow-up",
        time: "9:00 AM",
        datetime: "2025-01-07T09:00",
      },
      {
        id: 4,
        name: "Amara Okafor - Vaccination",
        time: "11:00 AM",
        datetime: "2025-01-07T11:00",
      },
      {
        id: 5,
        name: "Hassan Al-Mahmoud - Mental Health",
        time: "3:30 PM",
        datetime: "2025-01-07T15:30",
      },
    ],
  },
  {
    day: new Date("2025-01-10"),
    events: [
      {
        id: 6,
        name: "Community Health Workshop",
        time: "11:00 AM",
        datetime: "2025-01-10T11:00",
      },
    ],
  },
  {
    day: new Date("2025-01-13"),
    events: [
      {
        id: 7,
        name: "Diabetes Management Session",
        time: "3:30 PM",
        datetime: "2025-01-13T15:30",
      },
      {
        id: 8,
        name: "Pediatric Clinic",
        time: "9:00 AM",
        datetime: "2025-01-13T09:00",
      },
      {
        id: 9,
        name: "Mental Health Support Group",
        time: "1:00 PM",
        datetime: "2025-01-13T13:00",
      },
    ],
  },
  {
    day: new Date("2025-01-16"),
    events: [
      {
        id: 10,
        name: "Mobile Clinic - Camp Alpha",
        time: "10:00 AM",
        datetime: "2025-01-16T10:00",
      },
      {
        id: 11,
        name: "Nutrition Counseling",
        time: "12:30 PM",
        datetime: "2025-01-16T12:30",
      },
      {
        id: 12,
        name: "Chronic Disease Management",
        time: "2:00 PM",
        datetime: "2025-01-16T14:00",
      },
    ],
  },
]

function SchedulePage() {
  const [open, setOpen] = useState(false);

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
      
      {/* Main Calendar Content */}
      <div className="flex flex-1">
        <div className="p-2 md:p-6 rounded-tl-2xl border border-gray-200 bg-white flex flex-col gap-2 flex-1 w-full h-full overflow-hidden">
          <div className="mb-4">
            <h1 className="text-2xl font-bold text-gray-900">Medical Appointments</h1>
            <p className="text-gray-600">Schedule and manage patient appointments for displaced populations</p>
          </div>
          <div className="flex-1 overflow-hidden">
            <FullScreenCalendar data={medicalAppointments} />
          </div>
        </div>
      </div>
    </div>
  );
}

export { SchedulePage }