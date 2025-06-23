import React, { useState } from 'react';
import { Sidebar, SidebarBody, SidebarLink } from "@/components/ui/sidebar";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { 
  LayoutDashboard,
  Users,
  FileText,
  BarChart3,
  Bell,
  Settings,
  Calendar,
  Shield,
  Upload,
  Download,
  Search,
  Filter,
  Eye,
  Edit,
  Trash2,
  CheckCircle,
  Clock,
  AlertTriangle
} from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface MedicalRecord {
  id: string;
  patientName: string;
  patientId: string;
  recordType: string;
  date: string;
  provider: string;
  status: 'verified' | 'pending' | 'flagged';
  blockchainHash?: string;
  fileSize: string;
  language: string;
}

const medicalRecords: MedicalRecord[] = [
  {
    id: "1",
    patientName: "Ahmed Hassan",
    patientId: "SYR123456",
    recordType: "Vaccination Record",
    date: "2024-01-15",
    provider: "MSF Clinic",
    status: "verified",
    blockchainHash: "0x1a2b3c4d...",
    fileSize: "2.3 MB",
    language: "Arabic"
  },
  {
    id: "2",
    patientName: "Fatima Al-Rashid",
    patientId: "IRQ789012",
    recordType: "Prenatal Care Report",
    date: "2024-01-14",
    provider: "UNHCR Health Unit",
    status: "verified",
    blockchainHash: "0x5e6f7g8h...",
    fileSize: "1.8 MB",
    language: "Arabic"
  },
  {
    id: "3",
    patientName: "Omar Kone",
    patientId: "MLI345678",
    recordType: "Prescription",
    date: "2024-01-13",
    provider: "Camp Alpha Clinic",
    status: "pending",
    fileSize: "0.5 MB",
    language: "French"
  },
  {
    id: "4",
    patientName: "Amara Okafor",
    patientId: "NGA456789",
    recordType: "Lab Results",
    date: "2024-01-12",
    provider: "Mobile Health Unit",
    status: "verified",
    blockchainHash: "0x9i0j1k2l...",
    fileSize: "3.1 MB",
    language: "English"
  },
  {
    id: "5",
    patientName: "Hassan Al-Mahmoud",
    patientId: "AFG567890",
    recordType: "Mental Health Assessment",
    date: "2024-01-11",
    provider: "Psychological Support Unit",
    status: "flagged",
    fileSize: "1.2 MB",
    language: "Dari"
  }
];

const RecordsPage: React.FC = () => {
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

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'verified':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'pending':
        return <Clock className="w-4 h-4 text-yellow-500" />;
      case 'flagged':
        return <AlertTriangle className="w-4 h-4 text-red-500" />;
      default:
        return null;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'verified':
        return 'bg-green-100 text-green-800';
      case 'pending':
        return 'bg-yellow-100 text-yellow-800';
      case 'flagged':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const filteredRecords = selectedTab === 'all' 
    ? medicalRecords 
    : medicalRecords.filter(record => record.status === selectedTab);

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
                <h1 className="text-2xl font-bold text-gray-900">Medical Records</h1>
                <p className="text-gray-600">Blockchain-verified health records for displaced populations</p>
              </div>
              <div className="flex items-center space-x-2">
                <Button variant="outline">
                  <Search className="w-4 h-4 mr-2" />
                  Search
                </Button>
                <Button variant="outline">
                  <Filter className="w-4 h-4 mr-2" />
                  Filter
                </Button>
                <Button className="bg-gradient-to-r from-primary to-[#9fa0f7] hover:opacity-90">
                  <Upload className="w-4 h-4 mr-2" />
                  Upload Record
                </Button>
              </div>
            </div>

            {/* Stats Overview */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Total Records</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{medicalRecords.length}</div>
                  <div className="text-xs text-gray-500">Digital health records</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Blockchain Verified</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-green-600">
                    {medicalRecords.filter(r => r.status === 'verified').length}
                  </div>
                  <div className="text-xs text-gray-500">Tamper-proof records</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Pending Verification</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-yellow-600">
                    {medicalRecords.filter(r => r.status === 'pending').length}
                  </div>
                  <div className="text-xs text-gray-500">Awaiting blockchain verification</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">Languages Supported</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-purple-600">
                    {new Set(medicalRecords.map(r => r.language)).size}
                  </div>
                  <div className="text-xs text-gray-500">Multi-language support</div>
                </CardContent>
              </Card>
            </div>

            {/* Records Tabs */}
            <Tabs value={selectedTab} onValueChange={setSelectedTab}>
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="all">All Records</TabsTrigger>
                <TabsTrigger value="verified">Verified</TabsTrigger>
                <TabsTrigger value="pending">Pending</TabsTrigger>
                <TabsTrigger value="flagged">Flagged</TabsTrigger>
              </TabsList>

              <TabsContent value={selectedTab} className="mt-6">
                <div className="space-y-4">
                  {filteredRecords.map((record) => (
                    <Card key={record.id} className="hover:shadow-md transition-shadow">
                      <CardContent className="p-6">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-4">
                            <div className="p-2 bg-blue-100 rounded-lg">
                              <FileText className="w-6 h-6 text-blue-600" />
                            </div>
                            <div>
                              <h3 className="font-semibold text-gray-900">{record.recordType}</h3>
                              <p className="text-sm text-gray-600">{record.patientName} ({record.patientId})</p>
                              <div className="flex items-center space-x-4 mt-1">
                                <span className="text-xs text-gray-500">Provider: {record.provider}</span>
                                <span className="text-xs text-gray-500">Date: {new Date(record.date).toLocaleDateString()}</span>
                                <span className="text-xs text-gray-500">Size: {record.fileSize}</span>
                                <span className="text-xs text-gray-500">Language: {record.language}</span>
                              </div>
                            </div>
                          </div>
                          
                          <div className="flex items-center space-x-4">
                            <div className="flex items-center space-x-2">
                              {getStatusIcon(record.status)}
                              <Badge className={getStatusColor(record.status)}>
                                {record.status.charAt(0).toUpperCase() + record.status.slice(1)}
                              </Badge>
                            </div>
                            
                            {record.blockchainHash && (
                              <div className="flex items-center space-x-1">
                                <Shield className="w-4 h-4 text-green-500" />
                                <span className="text-xs text-gray-500 font-mono">
                                  {record.blockchainHash}
                                </span>
                              </div>
                            )}
                            
                            <div className="flex items-center space-x-1">
                              <Button variant="ghost" size="sm">
                                <Eye className="w-4 h-4" />
                              </Button>
                              <Button variant="ghost" size="sm">
                                <Download className="w-4 h-4" />
                              </Button>
                              <Button variant="ghost" size="sm">
                                <Edit className="w-4 h-4" />
                              </Button>
                              <Button variant="ghost" size="sm">
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </TabsContent>
            </Tabs>

            {/* Blockchain Verification Info */}
            <Card className="bg-gradient-to-r from-blue-50 to-purple-50 border-blue-200">
              <CardHeader>
                <CardTitle className="flex items-center text-blue-800">
                  <Shield className="w-5 h-5 mr-2" />
                  Blockchain Verification Status
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600">
                      {medicalRecords.filter(r => r.blockchainHash).length}
                    </div>
                    <div className="text-sm text-gray-600">Records on Blockchain</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">100%</div>
                    <div className="text-sm text-gray-600">Tamper-Proof Guarantee</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-purple-600">&lt; 2s</div>
                    <div className="text-sm text-gray-600">Verification Time</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RecordsPage;