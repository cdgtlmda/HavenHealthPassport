import React, { useState } from 'react';
import { Sidebar, SidebarBody, SidebarLink } from "@/components/ui/sidebar";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { MedicalDataGrid, Column } from "@/components/medical/MedicalDataGrid";
import { PatientCard, PatientData } from "@/components/medical/PatientCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { 
  LayoutDashboard,
  Users,
  FileText,
  BarChart3,
  Bell,
  Settings,
  Calendar,
  MapPin,
  Plus,
  Filter,
  Download
} from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Link } from "react-router-dom";

// Extended patient data for refugee populations
const refugeePatients: PatientData[] = [
  {
    id: "1",
    name: "Ahmed Hassan",
    dateOfBirth: "1985-03-15",
    gender: "male",
    nationality: "Syrian",
    phone: "+1-555-0123",
    unhcrId: "SYR123456",
    status: "verified",
    lastVisit: "2024-01-15",
    medicalAlerts: ["Diabetes", "Hypertension"],
    location: "Camp Alpha"
  },
  {
    id: "2",
    name: "Fatima Al-Rashid",
    dateOfBirth: "1992-07-22",
    gender: "female",
    nationality: "Iraqi",
    phone: "+1-555-0124",
    unhcrId: "IRQ789012",
    status: "pending",
    lastVisit: "2024-01-10",
    location: "Camp Beta"
  },
  {
    id: "3",
    name: "Omar Kone",
    dateOfBirth: "1978-11-08",
    gender: "male",
    nationality: "Malian",
    phone: "+1-555-0125",
    unhcrId: "MLI345678",
    status: "active",
    lastVisit: "2024-01-12",
    medicalAlerts: ["Asthma"],
    location: "Camp Gamma"
  },
  {
    id: "4",
    name: "Amara Okafor",
    dateOfBirth: "1990-05-20",
    gender: "female",
    nationality: "Nigerian",
    phone: "+1-555-0126",
    unhcrId: "NGA456789",
    status: "verified",
    lastVisit: "2024-01-14",
    location: "Camp Delta"
  },
  {
    id: "5",
    name: "Hassan Al-Mahmoud",
    dateOfBirth: "1975-12-03",
    gender: "male",
    nationality: "Afghan",
    phone: "+1-555-0127",
    unhcrId: "AFG567890",
    status: "flagged",
    lastVisit: "2024-01-08",
    medicalAlerts: ["PTSD", "Chronic Pain"],
    location: "Camp Echo"
  },
  {
    id: "6",
    name: "Zara Abdullahi",
    dateOfBirth: "1988-09-12",
    gender: "female",
    nationality: "Somali",
    phone: "+1-555-0128",
    unhcrId: "SOM234567",
    status: "verified",
    lastVisit: "2024-01-13",
    medicalAlerts: ["Pregnancy - 2nd trimester"],
    location: "Camp Alpha"
  },
  {
    id: "7",
    name: "Khalil Mansour",
    dateOfBirth: "1982-06-30",
    gender: "male",
    nationality: "Lebanese",
    phone: "+1-555-0129",
    unhcrId: "LBN345678",
    status: "active",
    lastVisit: "2024-01-11",
    location: "Camp Beta"
  },
  {
    id: "8",
    name: "Aisha Traore",
    dateOfBirth: "1995-04-18",
    gender: "female",
    nationality: "Burkinabe",
    phone: "+1-555-0130",
    unhcrId: "BFA456789",
    status: "pending",
    lastVisit: "2024-01-09",
    medicalAlerts: ["Malnutrition"],
    location: "Camp Gamma"
  }
];

const patientColumns: Column<PatientData>[] = [
  {
    id: "name",
    header: "Patient Name",
    accessorKey: "name",
    sortable: true,
    cell: (patient) => (
      <div className="flex items-center space-x-2">
        <div>
          <div className="font-medium">{patient.name}</div>
          <div className="text-sm text-gray-500">{patient.unhcrId}</div>
        </div>
      </div>
    )
  },
  {
    id: "status",
    header: "Status",
    accessorKey: "status",
    sortable: true,
    cell: (patient) => {
      const statusConfig = {
        active: { color: 'bg-green-100 text-green-800', label: 'Active' },
        pending: { color: 'bg-yellow-100 text-yellow-800', label: 'Pending' },
        verified: { color: 'bg-blue-100 text-blue-800', label: 'Verified' },
        flagged: { color: 'bg-red-100 text-red-800', label: 'Flagged' },
      };
      const config = statusConfig[patient.status];
      return (
        <Badge className={config.color}>
          {config.label}
        </Badge>
      );
    }
  },
  {
    id: "nationality",
    header: "Nationality",
    accessorKey: "nationality",
    sortable: true
  },
  {
    id: "age",
    header: "Age",
    sortable: true,
    cell: (patient) => {
      const age = new Date().getFullYear() - new Date(patient.dateOfBirth).getFullYear();
      return `${age}y`;
    }
  },
  {
    id: "lastVisit",
    header: "Last Visit",
    accessorKey: "lastVisit",
    sortable: true,
    cell: (patient) => patient.lastVisit ? new Date(patient.lastVisit).toLocaleDateString() : 'Never'
  },
  {
    id: "location",
    header: "Location",
    accessorKey: "location",
    sortable: true,
    cell: (patient) => (
      <div className="flex items-center">
        <MapPin className="w-4 h-4 mr-1 text-gray-400" />
        {patient.location}
      </div>
    )
  }
];

const PatientsPage: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [selectedPatients, setSelectedPatients] = useState<PatientData[]>([]);

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
      
      {/* Main Content */}
      <div className="flex flex-1">
        <div className="p-2 md:p-10 rounded-tl-2xl border border-gray-200 bg-white flex flex-col gap-2 flex-1 w-full h-full overflow-auto">
          <div className="space-y-6">
            {/* Page Header */}
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Patient Management</h1>
                <p className="text-gray-600">Manage health records for displaced populations</p>
              </div>
              <div className="flex items-center space-x-2">
                <Button variant="outline">
                  <Filter className="w-4 h-4 mr-2" />
                  Filter
                </Button>
                <Button variant="outline">
                  <Download className="w-4 h-4 mr-2" />
                  Export
                </Button>
                <Link to="/dashboard/new-patient">
                  <Button className="bg-gradient-to-r from-primary to-[#9fa0f7] hover:opacity-90">
                    <Plus className="w-4 h-4 mr-2" />
                    New Patient
                  </Button>
                </Link>
              </div>
            </div>

            {/* Stats Overview */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Total Patients</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{refugeePatients.length}</div>
                  <div className="text-xs text-gray-500">Registered individuals</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Verified Records</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-green-600">
                    {refugeePatients.filter(p => p.status === 'verified').length}
                  </div>
                  <div className="text-xs text-gray-500">Blockchain verified</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Pending Review</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-yellow-600">
                    {refugeePatients.filter(p => p.status === 'pending').length}
                  </div>
                  <div className="text-xs text-gray-500">Awaiting verification</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Medical Alerts</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-red-600">
                    {refugeePatients.filter(p => p.medicalAlerts && p.medicalAlerts.length > 0).length}
                  </div>
                  <div className="text-xs text-gray-500">Require attention</div>
                </CardContent>
              </Card>
            </div>

            {/* Recent Patients Cards */}
            <div>
              <h2 className="text-lg font-semibold mb-4">Recent Registrations</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {refugeePatients.slice(0, 6).map((patient) => (
                  <PatientCard
                    key={patient.id}
                    patient={patient}
                    onClick={() => console.log('Patient clicked:', patient.id)}
                    onEdit={() => console.log('Edit patient:', patient.id)}
                    onDelete={() => console.log('Delete patient:', patient.id)}
                  />
                ))}
              </div>
            </div>

            {/* Patients Data Grid */}
            <div>
              <h2 className="text-lg font-semibold mb-4">All Patients</h2>
              <MedicalDataGrid
                data={refugeePatients}
                columns={patientColumns}
                onRowClick={(patient) => console.log('Row clicked:', patient)}
                onSelectionChange={setSelectedPatients}
                searchable
                filterable
                exportable
                pagination
                pageSize={10}
              />
            </div>

            {selectedPatients.length > 0 && (
              <div className="fixed bottom-4 right-4 bg-white border border-gray-200 rounded-lg shadow-lg p-4">
                <div className="text-sm font-medium mb-2">
                  {selectedPatients.length} patient(s) selected
                </div>
                <div className="flex space-x-2">
                  <Button size="sm" variant="outline">
                    Export Selected
                  </Button>
                  <Button size="sm" className="bg-gradient-to-r from-primary to-[#9fa0f7] hover:opacity-90">
                    Bulk Actions
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PatientsPage;