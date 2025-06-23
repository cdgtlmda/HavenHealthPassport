"use client";

import React, { useState, useEffect } from "react";
import { Sidebar, SidebarBody, SidebarLink } from "@/components/ui/sidebar";
import { 
  LayoutDashboard, 
  Shield, 
  Activity, 
  BarChart3, 
  Settings, 
  AlertTriangle,
  CheckCircle,
  Clock,
  Terminal,
  FileText,
  MessageSquare,
  Database,
  Cloud,
  Server,
  Eye,
  Zap,
  Mail,
  Smartphone,
  Phone,
  ExternalLink,
  Filter,
  Search,
  Download,
  Bell,
  Users,
  Heart,
  Globe,
  Map,
  Stethoscope,
  Pill,
  UserPlus,
  Languages,
  QrCode,
  Lock,
  TrendingUp,
  MapPin,
  Calendar,
  Wifi,
  WifiOff,
  Upload,
  Scan,
  FileImage,
  RefreshCw,
  Pause,
  Play,
  CloudUpload,
  HardDrive,
  Mic,
  Volume2,
  Camera,
  ScanLine,
  Fingerprint,
  Key,
  ShieldCheck,
  Network,
  Satellite,
  Radio,
  Headphones,
  FileCheck,
  FileX,
  ScanText,
  Languages as TranslateIcon,
  Bot,
  Brain,
  Cpu,
  Workflow,
  Link,
  Unlink,
  CloudOff,
  CloudOn,
  RotateCcw,
  AlertCircle,
  Info,
  CheckCircle2,
  XCircle,
  Loader,
  Loader2,
  CreditCard
} from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// Interfaces
interface Patient {
  id: string;
  name: string;
  status: 'verified' | 'pending' | 'flagged' | 'active';
  nationality: string;
  lastVisit: string;
  location: string;
  medicalAlerts?: string[];
  blockchainHash?: string;
  languagePreference: string;
  unhcrId?: string;
  age: number;
  gender: string;
}

interface HealthRecord {
  id: string;
  patientId: string;
  patientName: string;
  recordType: string;
  date: string;
  provider: string;
  status: 'verified' | 'pending' | 'processing';
  blockchainHash: string;
  language: string;
  translationStatus: 'complete' | 'pending' | 'none';
  diagnosis?: string;
  treatment?: string;
}

interface CampInfo {
  id: string;
  name: string;
  location: string;
  population: number;
  capacity: number;
  healthFacilities: number;
  activePatients: number;
  criticalCases: number;
  lastUpdate: string;
}

interface EmergencyAlert {
  id: string;
  type: 'outbreak' | 'emergency' | 'resource_shortage' | 'system_failure';
  title: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  location: string;
  timestamp: string;
  status: 'active' | 'resolved' | 'investigating';
}

interface DocumentUpload {
  id: string;
  patientId: string;
  patientName: string;
  fileName: string;
  fileType: 'image' | 'pdf' | 'document';
  uploadStatus: 'uploading' | 'processing' | 'completed' | 'failed' | 'queued';
  syncStatus: 'synced' | 'pending' | 'offline' | 'failed';
  ocrStatus: 'pending' | 'processing' | 'completed' | 'failed';
  translationStatus: 'pending' | 'processing' | 'completed' | 'failed';
  blockchainStatus: 'pending' | 'processing' | 'verified' | 'failed';
  uploadedAt: string;
  processedAt?: string;
  extractedText?: string;
  translatedText?: string;
  detectedLanguage?: string;
  confidence?: number;
  medicalEntities?: string[];
  size: number;
  progress: number;
}

interface SyncStatus {
  isOnline: boolean;
  lastSync: string;
  pendingUploads: number;
  pendingDownloads: number;
  totalDocuments: number;
  syncedDocuments: number;
  failedSyncs: number;
  bandwidth: 'high' | 'medium' | 'low' | 'offline';
  estimatedSyncTime?: string;
}

interface VoiceRecording {
  id: string;
  patientId: string;
  patientName: string;
  duration: number;
  recordedAt: string;
  transcriptionStatus: 'pending' | 'processing' | 'completed' | 'failed';
  translationStatus: 'pending' | 'processing' | 'completed' | 'failed';
  detectedLanguage?: string;
  transcribedText?: string;
  translatedText?: string;
  confidence?: number;
  medicalTerms?: string[];
  audioQuality: 'excellent' | 'good' | 'fair' | 'poor';
}

interface BiometricVerification {
  patientId: string;
  verificationMethod: 'fingerprint' | 'facial' | 'iris' | 'voice';
  status: 'verified' | 'failed' | 'pending' | 'not_enrolled';
  confidence: number;
  verifiedAt?: string;
  attempts: number;
  lastAttempt?: string;
}

// Sample Data
const initialPatients: Patient[] = [
  {
    id: '1',
    name: 'Ahmed Hassan',
    status: 'verified',
    nationality: 'Syrian',
    lastVisit: '2024-01-15',
    location: 'Jordan - Zaatari Camp',
    medicalAlerts: ['Diabetes', 'Hypertension'],
    blockchainHash: '0x1a2b3c4d...',
    languagePreference: 'Arabic',
    unhcrId: 'SYR-901-2023-001',
    age: 34,
    gender: 'Male'
  },
  {
    id: '2',
    name: 'Fatima Al-Rashid',
    status: 'pending',
    nationality: 'Iraqi',
    lastVisit: '2024-01-10',
    location: 'Turkey - Istanbul',
    blockchainHash: '0x2b3c4d5e...',
    languagePreference: 'Kurdish',
    unhcrId: 'IRQ-445-2023-087',
    age: 28,
    gender: 'Female'
  },
  {
    id: '3',
    name: 'Omar Kone',
    status: 'active',
    nationality: 'Malian',
    lastVisit: '2024-01-12',
    location: 'Niger - Tillabéri',
    medicalAlerts: ['Asthma'],
    blockchainHash: '0x3c4d5e6f...',
    languagePreference: 'French',
    unhcrId: 'MLI-332-2023-156',
    age: 45,
    gender: 'Male'
  }
];

const campData: CampInfo[] = [
  {
    id: '1',
    name: 'Zaatari Camp',
    location: 'Jordan',
    population: 76847,
    capacity: 85000,
    healthFacilities: 8,
    activePatients: 1247,
    criticalCases: 23,
    lastUpdate: '2 minutes ago'
  },
  {
    id: '2',
    name: 'Dadaab Complex',
    location: 'Kenya',
    population: 218873,
    capacity: 250000,
    healthFacilities: 12,
    activePatients: 2891,
    criticalCases: 45,
    lastUpdate: '5 minutes ago'
  }
];

const emergencyAlerts: EmergencyAlert[] = [
  {
    id: '1',
    type: 'outbreak',
    title: 'Cholera Outbreak Detected',
    description: 'Suspected cholera cases identified in Sector 4',
    severity: 'high',
    location: 'Cox\'s Bazar, Bangladesh',
    timestamp: '2024-01-15 14:30:00',
    status: 'active'
  },
  {
    id: '2',
    type: 'resource_shortage',
    title: 'Medical Supply Shortage',
    description: 'Critical shortage of insulin and diabetes medication',
    severity: 'medium',
    location: 'Zaatari Camp, Jordan',
    timestamp: '2024-01-15 12:15:00',
    status: 'investigating'
  }
];

const documentUploads: DocumentUpload[] = [
  {
    id: '1',
    patientId: '1',
    patientName: 'Ahmed Hassan',
    fileName: 'vaccination_card_arabic.jpg',
    fileType: 'image',
    uploadStatus: 'completed',
    syncStatus: 'synced',
    ocrStatus: 'completed',
    translationStatus: 'completed',
    blockchainStatus: 'verified',
    uploadedAt: '2024-01-15 10:30:00',
    processedAt: '2024-01-15 10:32:15',
    extractedText: 'بطاقة التطعيم - لقاح كوفيد-19: فايزر',
    translatedText: 'Vaccination Card - COVID-19 Vaccine: Pfizer',
    detectedLanguage: 'Arabic',
    confidence: 0.94,
    medicalEntities: ['COVID-19', 'Pfizer', 'Vaccination'],
    size: 2.1,
    progress: 100
  },
  {
    id: '2',
    patientId: '2',
    patientName: 'Fatima Al-Rashid',
    fileName: 'medical_report_kurdish.pdf',
    fileType: 'pdf',
    uploadStatus: 'processing',
    syncStatus: 'pending',
    ocrStatus: 'processing',
    translationStatus: 'pending',
    blockchainStatus: 'pending',
    uploadedAt: '2024-01-15 11:45:00',
    detectedLanguage: 'Kurdish',
    confidence: 0.87,
    size: 4.8,
    progress: 65
  },
  {
    id: '3',
    patientId: '3',
    patientName: 'Omar Kone',
    fileName: 'prescription_french.jpg',
    fileType: 'image',
    uploadStatus: 'queued',
    syncStatus: 'offline',
    ocrStatus: 'pending',
    translationStatus: 'pending',
    blockchainStatus: 'pending',
    uploadedAt: '2024-01-15 12:20:00',
    detectedLanguage: 'French',
    size: 1.5,
    progress: 0
  }
];

const syncStatus: SyncStatus = {
  isOnline: true,
  lastSync: '2024-01-15 12:45:00',
  pendingUploads: 3,
  pendingDownloads: 1,
  totalDocuments: 847,
  syncedDocuments: 834,
  failedSyncs: 2,
  bandwidth: 'medium',
  estimatedSyncTime: '2 minutes'
};

const voiceRecordings: VoiceRecording[] = [
  {
    id: '1',
    patientId: '1',
    patientName: 'Ahmed Hassan',
    duration: 45,
    recordedAt: '2024-01-15 09:15:00',
    transcriptionStatus: 'completed',
    translationStatus: 'completed',
    detectedLanguage: 'Arabic',
    transcribedText: 'أعاني من مرض السكري منذ خمس سنوات. أتناول دواء الميتفورمين يومياً.',
    translatedText: 'I have been suffering from diabetes for five years. I take Metformin daily.',
    confidence: 0.92,
    medicalTerms: ['Diabetes', 'Metformin'],
    audioQuality: 'good'
  },
  {
    id: '2',
    patientId: '2',
    patientName: 'Fatima Al-Rashid',
    duration: 32,
    recordedAt: '2024-01-15 10:30:00',
    transcriptionStatus: 'processing',
    translationStatus: 'pending',
    detectedLanguage: 'Kurdish',
    confidence: 0.78,
    audioQuality: 'fair'
  }
];

// Logo Components
const HavenLogo = () => (
  <div className="font-normal flex space-x-2 items-center text-sm text-black py-1 relative z-20">
    <div className="h-5 w-6 bg-gradient-to-r from-primary to-[#9fa0f7] rounded-br-lg rounded-tr-sm rounded-tl-lg rounded-bl-sm flex-shrink-0" />
    <motion.span
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="font-medium text-black whitespace-pre"
    >
      HavenHealthPassport
    </motion.span>
  </div>
);

const HavenLogoIcon = () => (
  <div className="font-normal flex space-x-2 items-center text-sm text-black py-1 relative z-20">
    <div className="h-5 w-6 bg-gradient-to-r from-primary to-[#9fa0f7] rounded-br-lg rounded-tr-sm rounded-tl-lg rounded-bl-sm flex-shrink-0" />
  </div>
);

// Dashboard Components
const OverviewDashboard = () => (
  <div className="space-y-6">
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Global Health Overview</h2>
      <p className="text-gray-600">Real-time health data for displaced populations worldwide</p>
    </div>
    
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <MetricCard 
        title="Total Patients" 
        value="127,849" 
        icon={<Users className="w-6 h-6" />}
        trend="+8.2% from last month"
        color="text-blue-600"
      />
      <MetricCard 
        title="Records Verified" 
        value="98.7%" 
        icon={<Shield className="w-6 h-6" />}
        trend="+1.3% from last month"
        color="text-green-600"
      />
      <MetricCard 
        title="Languages Active" 
        value="52" 
        icon={<Languages className="w-6 h-6" />}
        trend="+3 from last month"
        color="text-purple-600"
      />
      <MetricCard 
        title="Mobile Devices" 
        value="3,421" 
        icon={<Smartphone className="w-6 h-6" />}
        trend="+12% from last month"
        color="text-orange-600"
      />
    </div>

    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg text-gray-900 flex items-center gap-2">
            <Activity className="w-5 h-5 text-green-600" />
            System Health
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Blockchain Network</span>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <Badge className="bg-green-100 text-green-800">Online</Badge>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">AI Translation Service</span>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <Badge className="bg-green-100 text-green-800">97.3%</Badge>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Offline Sync Success</span>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                <Badge className="bg-yellow-100 text-yellow-800">Syncing</Badge>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">AWS HealthLake</span>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <Badge className="bg-green-100 text-green-800">Connected</Badge>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg text-gray-900 flex items-center gap-2">
            <Clock className="w-5 h-5 text-blue-600" />
            Recent Patients
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {initialPatients.slice(0, 4).map((patient) => (
              <div key={patient.id} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div className="flex-1">
                  <p className="font-medium text-gray-900">{patient.name}</p>
                  <p className="text-sm text-gray-600">{patient.unhcrId} • {patient.nationality}</p>
                  <div className="flex items-center text-xs text-gray-500 mt-1">
                    <MapPin className="w-3 h-3 mr-1" />
                    {patient.location}
                  </div>
                </div>
                <div className="text-right">
                  <Badge variant={patient.status === 'verified' ? 'secondary' : 'outline'}>
                    {patient.status}
                  </Badge>
                  <div className="text-xs text-gray-500 mt-1">
                    {new Date(patient.lastVisit).toLocaleDateString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg text-gray-900 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-red-600" />
            Critical Alerts
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="p-3 bg-red-50 border border-red-200 rounded">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-medium text-red-900">Medical Supply Shortage</p>
                  <p className="text-sm text-red-700">Insulin shortage in Zaatari Camp</p>
                  <p className="text-xs text-red-600 mt-1">2 hours ago</p>
                </div>
                <Badge className="bg-red-100 text-red-800">High</Badge>
              </div>
            </div>
            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-medium text-yellow-900">Translation Queue</p>
                  <p className="text-sm text-yellow-700">47 records pending translation</p>
                  <p className="text-xs text-yellow-600 mt-1">15 minutes ago</p>
                </div>
                <Badge className="bg-yellow-100 text-yellow-800">Medium</Badge>
              </div>
            </div>
            <div className="p-3 bg-blue-50 border border-blue-200 rounded">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-medium text-blue-900">System Update</p>
                  <p className="text-sm text-blue-700">Blockchain verification enhanced</p>
                  <p className="text-xs text-blue-600 mt-1">1 hour ago</p>
                </div>
                <Badge className="bg-blue-100 text-blue-800">Info</Badge>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>

    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg text-gray-900 flex items-center gap-2">
            <Globe className="w-5 h-5 text-purple-600" />
            Geographic Distribution
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                <span className="text-sm text-gray-600">Middle East</span>
              </div>
              <span className="text-sm font-medium">47,892 patients</span>
            </div>
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                <span className="text-sm text-gray-600">Sub-Saharan Africa</span>
              </div>
              <span className="text-sm font-medium">38,247 patients</span>
            </div>
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                <span className="text-sm text-gray-600">South Asia</span>
              </div>
              <span className="text-sm font-medium">28,156 patients</span>
            </div>
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                <span className="text-sm text-gray-600">Latin America</span>
              </div>
              <span className="text-sm font-medium">13,554 patients</span>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg text-gray-900 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-green-600" />
            Monthly Trends
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">New Registrations</span>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">+2,847</span>
                <Badge className="bg-green-100 text-green-800">+12.5%</Badge>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Records Verified</span>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">+4,123</span>
                <Badge className="bg-green-100 text-green-800">+8.7%</Badge>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Translation Requests</span>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">+1,956</span>
                <Badge className="bg-blue-100 text-blue-800">+15.3%</Badge>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Mobile App Downloads</span>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">+892</span>
                <Badge className="bg-purple-100 text-purple-800">+22.1%</Badge>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
);

const MedicalAnalytics = () => (
  <div className="space-y-6">
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Medical Analytics</h2>
      <p className="text-gray-600">Health trends and insights across refugee populations</p>
    </div>
    
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <MetricCard 
        title="Medical Consultations" 
        value="8,947" 
        icon={<Stethoscope className="w-6 h-6" />}
        trend="+15.2% from last month"
        color="text-blue-600"
      />
      <MetricCard 
        title="Emergency Cases" 
        value="342" 
        icon={<AlertTriangle className="w-6 h-6" />}
        trend="-8.1% from last month"
        color="text-red-600"
      />
      <MetricCard 
        title="Chronic Conditions" 
        value="2,847" 
        icon={<Heart className="w-6 h-6" />}
        trend="+3.7% from last month"
        color="text-orange-600"
      />
      <MetricCard 
        title="Vaccination Rate" 
        value="94.2%" 
        icon={<Shield className="w-6 h-6" />}
        trend="+2.1% from last month"
        color="text-green-600"
      />
    </div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg text-gray-900">Common Conditions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                <span className="text-sm text-gray-600">Mental Health</span>
              </div>
              <span className="text-sm font-medium">23.1%</span>
            </div>
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                <span className="text-sm text-gray-600">Diabetes</span>
              </div>
              <span className="text-sm font-medium">18.2%</span>
            </div>
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                <span className="text-sm text-gray-600">Hypertension</span>
              </div>
              <span className="text-sm font-medium">15.7%</span>
            </div>
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                <span className="text-sm text-gray-600">Respiratory Issues</span>
              </div>
              <span className="text-sm font-medium">12.4%</span>
            </div>
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-purple-500 rounded-full"></div>
                <span className="text-sm text-gray-600">Malnutrition</span>
              </div>
                <span className="text-sm font-medium">9.8%</span>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg text-gray-900">Vaccination Coverage</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Polio</span>
              <Badge className="bg-green-100 text-green-800">97.2%</Badge>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Measles</span>
              <Badge className="bg-green-100 text-green-800">94.7%</Badge>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">COVID-19</span>
              <Badge className="bg-green-100 text-green-800">89.3%</Badge>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Hepatitis B</span>
              <Badge className="bg-yellow-100 text-yellow-800">78.5%</Badge>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Tuberculosis</span>
              <Badge className="bg-blue-100 text-blue-800">85.1%</Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg text-gray-900">Age Demographics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">0-5 years</span>
              <div className="flex items-center gap-2">
                <div className="w-16 h-2 bg-gray-200 rounded-full">
                  <div className="w-1/5 h-full bg-blue-500 rounded-full"></div>
                </div>
                <span className="text-sm font-medium">22.8%</span>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">6-17 years</span>
              <div className="flex items-center gap-2">
                <div className="w-16 h-2 bg-gray-200 rounded-full">
                  <div className="w-1/3 h-full bg-green-500 rounded-full"></div>
                </div>
                <span className="text-sm font-medium">31.5%</span>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">18-59 years</span>
              <div className="flex items-center gap-2">
                <div className="w-16 h-2 bg-gray-200 rounded-full">
                  <div className="w-2/5 h-full bg-yellow-500 rounded-full"></div>
                </div>
                <span className="text-sm font-medium">39.2%</span>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">60+ years</span>
              <div className="flex items-center gap-2">
                <div className="w-16 h-2 bg-gray-200 rounded-full">
                  <div className="w-1/12 h-full bg-red-500 rounded-full"></div>
                </div>
                <span className="text-sm font-medium">6.5%</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>

    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg text-gray-900 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-blue-600" />
            Health Facility Utilization
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Primary Care</span>
              <div className="flex items-center gap-2">
                <div className="w-24 h-2 bg-gray-200 rounded-full">
                  <div className="w-4/5 h-full bg-blue-500 rounded-full"></div>
                </div>
                <span className="text-sm font-medium">87%</span>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Mental Health Services</span>
              <div className="flex items-center gap-2">
                <div className="w-24 h-2 bg-gray-200 rounded-full">
                  <div className="w-3/5 h-full bg-purple-500 rounded-full"></div>
                </div>
                <span className="text-sm font-medium">64%</span>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Maternal Health</span>
              <div className="flex items-center gap-2">
                <div className="w-24 h-2 bg-gray-200 rounded-full">
                  <div className="w-3/4 h-full bg-pink-500 rounded-full"></div>
                </div>
                <span className="text-sm font-medium">78%</span>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Emergency Care</span>
              <div className="flex items-center gap-2">
                <div className="w-24 h-2 bg-gray-200 rounded-full">
                  <div className="w-1/2 h-full bg-red-500 rounded-full"></div>
                </div>
                <span className="text-sm font-medium">52%</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg text-gray-900 flex items-center gap-2">
            <Activity className="w-5 h-5 text-green-600" />
            Disease Surveillance
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="p-3 bg-green-50 border border-green-200 rounded">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-green-900">No Active Outbreaks</p>
                  <p className="text-sm text-green-700">All monitored diseases within normal ranges</p>
                </div>
                <Badge className="bg-green-100 text-green-800">Good</Badge>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Cholera Risk</span>
                <Badge className="bg-green-100 text-green-800">Low</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Measles Risk</span>
                <Badge className="bg-green-100 text-green-800">Low</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">COVID-19 Risk</span>
                <Badge className="bg-yellow-100 text-yellow-800">Moderate</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Malaria Risk</span>
                <Badge className="bg-yellow-100 text-yellow-800">Moderate</Badge>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
);

const CampOperations = () => (
  <div className="space-y-6">
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Camp Operations</h2>
      <p className="text-gray-600">Health operations across refugee camps and settlements</p>
    </div>
    
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {campData.map((camp) => (
        <Card key={camp.id}>
          <CardHeader>
            <CardTitle className="text-lg text-gray-900 flex items-center gap-2">
              <MapPin className="w-5 h-5 text-blue-600" />
              {camp.name}
            </CardTitle>
            <p className="text-sm text-gray-600">{camp.location}</p>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-2xl font-bold text-gray-900">{camp.population.toLocaleString()}</p>
                  <p className="text-sm text-gray-600">Population</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900">{camp.healthFacilities}</p>
                  <p className="text-sm text-gray-600">Health Facilities</p>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">Active Patients</span>
                  <span className="text-sm font-medium">{camp.activePatients}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">Critical Cases</span>
                  <Badge variant={camp.criticalCases > 30 ? 'destructive' : 'secondary'}>
                    {camp.criticalCases}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">Capacity</span>
                  <span className="text-sm font-medium">
                    {((camp.population / camp.capacity) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  </div>
);

const EmergencyResponse = () => (
  <div className="space-y-6">
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Emergency Response</h2>
      <p className="text-gray-600">Active alerts and emergency coordination</p>
    </div>
    
    <div className="space-y-4">
      {emergencyAlerts.map((alert) => (
        <Card key={alert.id} className={cn(
          "border-l-4",
          alert.severity === 'critical' && "border-l-red-500",
          alert.severity === 'high' && "border-l-orange-500",
          alert.severity === 'medium' && "border-l-yellow-500",
          alert.severity === 'low' && "border-l-blue-500"
        )}>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg text-gray-900 flex items-center gap-2">
                <AlertTriangle className={cn(
                  "w-5 h-5",
                  alert.severity === 'critical' && "text-red-600",
                  alert.severity === 'high' && "text-orange-600",
                  alert.severity === 'medium' && "text-yellow-600",
                  alert.severity === 'low' && "text-blue-600"
                )} />
                {alert.title}
              </CardTitle>
              <Badge variant={alert.status === 'active' ? 'destructive' : 'secondary'}>
                {alert.status}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-gray-700 mb-2">{alert.description}</p>
            <div className="flex items-center justify-between text-sm text-gray-600">
              <span className="flex items-center gap-1">
                <MapPin className="w-4 h-4" />
                {alert.location}
              </span>
              <span>{new Date(alert.timestamp).toLocaleString()}</span>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  </div>
);

const MobileSync = () => (
  <div className="space-y-6">
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Mobile Device Management</h2>
      <p className="text-gray-600">Offline-first mobile devices and synchronization status</p>
    </div>
    
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <MetricCard 
        title="Total Devices" 
        value="3,421" 
        icon={<Smartphone className="w-6 h-6" />}
        trend="+12% from last month"
        color="text-blue-600"
      />
      <MetricCard 
        title="Online Devices" 
        value="2,847" 
        icon={<Wifi className="w-6 h-6" />}
        trend="83.2% connectivity"
        color="text-green-600"
      />
      <MetricCard 
        title="Pending Sync" 
        value="574" 
        icon={<WifiOff className="w-6 h-6" />}
        trend="Awaiting connection"
        color="text-orange-600"
      />
    </div>

    <Card>
      <CardHeader>
        <CardTitle className="text-lg text-gray-900">Device Status by Location</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
            <div>
              <p className="font-medium text-gray-900">Zaatari Camp, Jordan</p>
              <p className="text-sm text-gray-600">247 devices • Last sync: 2 min ago</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge className="bg-green-100 text-green-800">Online</Badge>
              <div className="w-3 h-3 bg-green-400 rounded-full"></div>
            </div>
          </div>
          <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
            <div>
              <p className="font-medium text-gray-900">Cox's Bazar, Bangladesh</p>
              <p className="text-sm text-gray-600">156 devices • Last sync: 15 min ago</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge className="bg-yellow-100 text-yellow-800">Syncing</Badge>
              <div className="w-3 h-3 bg-yellow-400 rounded-full"></div>
            </div>
          </div>
          <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
            <div>
              <p className="font-medium text-gray-900">Dadaab, Kenya</p>
              <p className="text-sm text-gray-600">89 devices • Last sync: 2 hours ago</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge className="bg-red-100 text-red-800">Offline</Badge>
              <div className="w-3 h-3 bg-red-400 rounded-full"></div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  </div>
);

const PatientsManagement = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [locationFilter, setLocationFilter] = useState('all');
  const [filteredPatients, setFilteredPatients] = useState(initialPatients);
  const [isFiltering, setIsFiltering] = useState(false);

  const handleFilter = () => {
    setIsFiltering(true);
    // Simulate filtering delay
    setTimeout(() => {
      let filtered = initialPatients;
      
      if (searchTerm) {
        filtered = filtered.filter(patient => 
          patient.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          patient.unhcrId?.toLowerCase().includes(searchTerm.toLowerCase()) ||
          patient.location.toLowerCase().includes(searchTerm.toLowerCase())
        );
      }
      
      if (statusFilter !== 'all') {
        filtered = filtered.filter(patient => patient.status === statusFilter);
      }
      
      if (locationFilter !== 'all') {
        filtered = filtered.filter(patient => 
          patient.location.toLowerCase().includes(locationFilter.toLowerCase())
        );
      }
      
      setFilteredPatients(filtered);
      setIsFiltering(false);
    }, 500);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <h2 className="text-2xl font-bold text-gray-900">Patient Records Management</h2>
        <Badge className="bg-blue-100 text-blue-800 text-xs">
          <Info className="w-3 h-3 mr-1" />
          Powered by Amazon Comprehend Medical
        </Badge>
      </div>
      <p className="text-gray-600">Secure, blockchain-verified patient health records with AI-powered medical entity extraction</p>
      
      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        <div className="flex-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <Input
              placeholder="Search patients by name, UNHCR ID, or location..."
              className="pl-10"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>
        <div className="flex gap-2">
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="verified">Verified</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="active">Active</SelectItem>
            </SelectContent>
          </Select>
          <Select value={locationFilter} onValueChange={setLocationFilter}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Location" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Locations</SelectItem>
              <SelectItem value="jordan">Jordan</SelectItem>
              <SelectItem value="turkey">Turkey</SelectItem>
              <SelectItem value="niger">Niger</SelectItem>
            </SelectContent>
          </Select>
          <Button size="sm" onClick={handleFilter} disabled={isFiltering}>
            {isFiltering ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Filter className="w-4 h-4 mr-2" />
            )}
            {isFiltering ? 'Filtering...' : 'Filter'}
          </Button>
        </div>
      </div>

    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <MetricCard 
        title="Total Patients" 
        value="3,247" 
        icon={<Users className="w-6 h-6" />}
        trend="+12.5% from last month"
        color="text-blue-600"
      />
      <MetricCard 
        title="Verified Records" 
        value="2,847" 
        icon={<CheckCircle className="w-6 h-6" />}
        trend="+8.7% from last month"
        color="text-green-600"
      />
      <MetricCard 
        title="Pending Verification" 
        value="127" 
        icon={<Clock className="w-6 h-6" />}
        trend="-3.2% from last month"
        color="text-yellow-600"
      />
      <MetricCard 
        title="Critical Cases" 
        value="43" 
        icon={<AlertTriangle className="w-6 h-6" />}
        trend="+2.8% from last month"
        color="text-red-600"
      />
    </div>
    
    <div className="space-y-4">
      {filteredPatients.map((patient) => (
        <Card key={patient.id} className="hover:shadow-md transition-shadow">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-gradient-to-r from-primary to-[#9fa0f7] rounded-full flex items-center justify-center text-white font-bold">
                  {patient.name.split(' ').map(n => n[0]).join('')}
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">{patient.name}</h3>
                  <p className="text-sm text-gray-600">
                    {patient.age} years old • {patient.gender} • {patient.nationality}
                  </p>
                  <p className="text-sm text-gray-500">UNHCR ID: {patient.unhcrId}</p>
                </div>
              </div>
              <div className="text-right">
                <Badge variant={
                  patient.status === 'verified' ? 'default' : 
                  patient.status === 'pending' ? 'secondary' : 
                  'outline'
                }>
                  {patient.status}
                </Badge>
                <div className="flex items-center gap-1 mt-2">
                  <Languages className="w-3 h-3 text-gray-400" />
                  <span className="text-xs text-gray-500">{patient.languagePreference}</span>
                </div>
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <p className="text-sm font-medium text-gray-700 flex items-center gap-1">
                  <MapPin className="w-3 h-3" />
                  Current Location
                </p>
                <p className="text-sm text-gray-600">{patient.location}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-700 flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  Last Visit
                </p>
                <p className="text-sm text-gray-600">{new Date(patient.lastVisit).toLocaleDateString()}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-700 flex items-center gap-1">
                  <Activity className="w-3 h-3" />
                  Health Status
                </p>
                <Badge variant="outline" className={
                  patient.medicalAlerts && patient.medicalAlerts.length > 0 ? 
                  'text-orange-600 border-orange-200' : 
                  'text-green-600 border-green-200'
                }>
                  {patient.medicalAlerts && patient.medicalAlerts.length > 0 ? 'Requires Attention' : 'Stable'}
                </Badge>
              </div>
            </div>
            
            {patient.medicalAlerts && patient.medicalAlerts.length > 0 && (
              <div className="mb-4">
                <p className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3 text-orange-600" />
                  Medical Alerts
                </p>
                <div className="flex gap-2 flex-wrap">
                  {patient.medicalAlerts.map((alert, index) => (
                    <Badge key={index} variant="outline" className="text-red-600 border-red-200 bg-red-50">
                      <Heart className="w-3 h-3 mr-1" />
                      {alert}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
            
            <div className="pt-4 border-t border-gray-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Shield className="w-4 h-4 text-green-600" />
                  <span className="text-sm text-gray-600">Blockchain Verified</span>
                  <Badge className="bg-green-100 text-green-800 text-xs">
                    AWS Managed Blockchain
                  </Badge>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 font-mono">{patient.blockchainHash}</span>
                  <Button size="sm" variant="outline" className="h-6 px-2 text-xs">
                    <Eye className="w-3 h-3 mr-1" />
                    View Details
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>

    <div className="flex items-center justify-between pt-4">
      <p className="text-sm text-gray-600">
        Showing {filteredPatients.length} of 3,247 patients
        {(searchTerm || statusFilter !== 'all' || locationFilter !== 'all') && 
          <span className="text-blue-600"> (filtered)</span>
        }
      </p>
      <div className="flex gap-2">
        <Button size="sm" variant="outline" disabled>
          Previous
        </Button>
        <Button size="sm" variant="outline">
          Next
        </Button>
      </div>
    </div>
  </div>
  );
};

const BlockchainVerification = () => (
  <div className="space-y-6">
    <div className="flex items-center gap-2">
      <h2 className="text-2xl font-bold text-gray-900">Blockchain Verification</h2>
      <Badge className="bg-red-100 text-red-800 text-xs">
        <Info className="w-3 h-3 mr-1" />
        Amazon Managed Blockchain + QLDB
      </Badge>
    </div>
    <p className="text-gray-600">Tamper-proof health record verification system with immutable audit trails</p>
    
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <MetricCard 
        title="Records Verified" 
        value="98.7%" 
        icon={<Shield className="w-6 h-6" />}
        trend="+1.3% from last month"
        color="text-green-600"
      />
      <MetricCard 
        title="Block Height" 
        value="847,291" 
        icon={<Database className="w-6 h-6" />}
        trend="Latest block"
        color="text-blue-600"
      />
      <MetricCard 
        title="Hash Rate" 
        value="99.9%" 
        icon={<Lock className="w-6 h-6" />}
        trend="Network security"
        color="text-purple-600"
      />
      <MetricCard 
        title="Consensus" 
        value="100%" 
        icon={<CheckCircle className="w-6 h-6" />}
        trend="Network agreement"
        color="text-emerald-600"
      />
    </div>

    <Card>
      <CardHeader>
        <CardTitle className="text-lg text-gray-900">Recent Verifications</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {[
            { hash: '0x1a2b3c4d5e6f...', type: 'Medical Record', patient: 'Ahmed Hassan', time: '2 min ago' },
            { hash: '0x2b3c4d5e6f7g...', type: 'Vaccination', patient: 'Fatima Al-Rashid', time: '5 min ago' },
            { hash: '0x3c4d5e6f7g8h...', type: 'Lab Results', patient: 'Omar Kone', time: '8 min ago' }
          ].map((record, index) => (
            <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded">
              <div>
                <p className="font-mono text-sm text-gray-900">{record.hash}</p>
                <p className="text-sm text-gray-600">{record.type} • {record.patient}</p>
              </div>
              <div className="text-right">
                <Badge className="bg-green-100 text-green-800 mb-1">Verified</Badge>
                <p className="text-xs text-gray-500">{record.time}</p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  </div>
);

const AITranslationDashboard = () => (
  <div className="space-y-6">
    <div className="flex items-center gap-2">
      <h2 className="text-2xl font-bold text-gray-900">AI Translation Services</h2>
      <Badge className="bg-yellow-100 text-yellow-800 text-xs">
        <Info className="w-3 h-3 mr-1" />
        Amazon Translate + Bedrock Claude
      </Badge>
    </div>
    <p className="text-gray-600">Real-time medical translation in 47+ languages with cultural context adaptation</p>
    
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <MetricCard 
        title="Translation Accuracy" 
        value="97.3%" 
        icon={<Languages className="w-6 h-6" />}
        trend="+2.1% this month"
        color="text-blue-600"
      />
      <MetricCard 
        title="Daily Translations" 
        value="2,847" 
        icon={<MessageSquare className="w-6 h-6" />}
        trend="+15% from yesterday"
        color="text-green-600"
      />
      <MetricCard 
        title="Response Time" 
        value="1.2s" 
        icon={<Zap className="w-6 h-6" />}
        trend="Average processing"
        color="text-purple-600"
      />
    </div>

    <Card>
      <CardHeader>
        <CardTitle className="text-lg text-gray-900">Recent Translations</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {[
            {
              from: 'Arabic',
              to: 'English',
              original: 'المريض يعاني من ألم في الصدر وضيق في التنفس',
              translated: 'Patient experiencing chest pain and shortness of breath',
              confidence: 98.5
            },
            {
              from: 'French',
              to: 'English',
              original: 'Le patient a besoin d\'un traitement pour l\'asthme',
              translated: 'Patient needs treatment for asthma',
              confidence: 97.8
            }
          ].map((translation, index) => (
            <div key={index} className="p-4 bg-gray-50 rounded">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-900">
                  {translation.from} → {translation.to}
                </span>
                <Badge className="bg-green-100 text-green-800">
                  {translation.confidence}% confidence
                </Badge>
              </div>
              <p className="text-sm text-gray-700 mb-2">"{translation.original}"</p>
              <p className="text-sm text-gray-900 font-medium">"{translation.translated}"</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  </div>
);

const DocumentProcessingDashboard = () => {
  const [selectedDoc, setSelectedDoc] = useState<DocumentUpload | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': case 'synced': case 'verified': return <CheckCircle2 className="w-4 h-4 text-green-500" />;
      case 'processing': case 'pending': return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      case 'failed': return <XCircle className="w-4 h-4 text-red-500" />;
      case 'offline': case 'queued': return <Clock className="w-4 h-4 text-yellow-500" />;
      default: return <AlertCircle className="w-4 h-4 text-gray-500" />;
    }
  };

  const handleUploadDocument = () => {
    setIsUploading(true);
    setUploadProgress(0);
    
    // Simulate upload progress
    const interval = setInterval(() => {
      setUploadProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setIsUploading(false);
          setShowUploadDialog(false);
          return 100;
        }
        return prev + 10;
      });
    }, 200);
  };

  const acceptedDocumentTypes = [
    { type: 'Medical Records', formats: ['PDF', 'JPG', 'PNG'], icon: <FileText className="w-4 h-4" /> },
    { type: 'Vaccination Cards', formats: ['PDF', 'JPG', 'PNG'], icon: <Shield className="w-4 h-4" /> },
    { type: 'Lab Results', formats: ['PDF', 'DICOM'], icon: <Activity className="w-4 h-4" /> },
    { type: 'Prescription Documents', formats: ['PDF', 'JPG'], icon: <Pill className="w-4 h-4" /> },
    { type: 'Identity Documents', formats: ['PDF', 'JPG', 'PNG'], icon: <FileCheck className="w-4 h-4" /> },
    { type: 'Insurance Cards', formats: ['PDF', 'JPG', 'PNG'], icon: <CreditCard className="w-4 h-4" /> }
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-2xl font-bold text-gray-900">Document Processing & AI Pipeline</h2>
          <Badge className="bg-purple-100 text-purple-800 text-xs">
            <Info className="w-3 h-3 mr-1" />
            Amazon Textract + Comprehend Medical
          </Badge>
        </div>
        <div className="flex items-center gap-4">
          <Badge className={`${syncStatus.isOnline ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            {syncStatus.isOnline ? <Wifi className="w-3 h-3 mr-1" /> : <WifiOff className="w-3 h-3 mr-1" />}
            {syncStatus.isOnline ? 'Online' : 'Offline'}
          </Badge>
          <Dialog open={showUploadDialog} onOpenChange={setShowUploadDialog}>
            <DialogTrigger asChild>
              <Button size="sm" className="bg-blue-600 text-white">
                <Upload className="w-4 h-4 mr-2" />
                Upload Document
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Upload className="w-5 h-5" />
                  Upload Health Document - Haven Health Passport
                </DialogTitle>
              </DialogHeader>
              
              {!isUploading ? (
                <div className="space-y-6">
                  <div className="text-center p-8 border-2 border-dashed border-gray-300 rounded-lg hover:border-blue-500 transition-colors cursor-pointer">
                    <Camera className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-gray-900 mb-2">
                      Drag & drop or click to upload
                    </h3>
                    <p className="text-sm text-gray-500">
                      Maximum file size: 25MB • Supports multiple languages
                    </p>
                  </div>
                  
                  <div>
                    <h4 className="font-medium text-gray-900 mb-3">Accepted Document Types for Refugees</h4>
                    <div className="grid grid-cols-2 gap-3">
                      {acceptedDocumentTypes.map((docType, index) => (
                        <div key={index} className="flex items-center gap-3 p-3 border rounded-lg hover:bg-gray-50">
                          {docType.icon}
                          <div>
                            <div className="font-medium text-sm">{docType.type}</div>
                            <div className="text-xs text-gray-500">{docType.formats.join(', ')}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <h4 className="font-medium text-blue-900 mb-2 flex items-center gap-2">
                      <Brain className="w-4 h-4" />
                      AI Processing Pipeline
                    </h4>
                    <div className="text-sm text-blue-800 space-y-1">
                      <div>• OCR with multi-language support (Arabic, Farsi, English, French)</div>
                      <div>• Medical entity extraction using Amazon Comprehend Medical</div>
                      <div>• Real-time translation with cultural context awareness</div>
                      <div>• Blockchain verification for document authenticity</div>
                    </div>
                  </div>
                  
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={() => setShowUploadDialog(false)}>
                      Cancel
                    </Button>
                    <Button onClick={handleUploadDocument} className="bg-blue-600 text-white">
                      <Upload className="w-4 h-4 mr-2" />
                      Start Upload
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-6 text-center p-8">
                  <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto">
                    <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
                  </div>
                  <div>
                    <h3 className="text-lg font-medium text-gray-900 mb-2">Processing Document...</h3>
                    <p className="text-sm text-gray-500 mb-4">
                      AI is extracting medical information and translating content
                    </p>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div className="bg-blue-600 h-2 rounded-full transition-all duration-300" 
                           style={{ width: `${uploadProgress}%` }}></div>
                    </div>
                    <p className="text-sm text-gray-600 mt-2">{uploadProgress}% complete</p>
                  </div>
                </div>
              )}
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Document Processing Pipeline */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Workflow className="w-5 h-5" />
            Real-time Document Processing Pipeline
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {documentUploads.map((doc) => (
              <div key={doc.id} className="border rounded-lg p-4 hover:bg-gray-50 cursor-pointer">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    {doc.fileType === 'image' ? <FileImage className="w-5 h-5 text-blue-500" /> : 
                     doc.fileType === 'pdf' ? <FileText className="w-5 h-5 text-red-500" /> : 
                     <FileCheck className="w-5 h-5 text-green-500" />}
                    <div>
                      <div className="font-medium">{doc.fileName}</div>
                      <div className="text-sm text-gray-500">{doc.patientName} • {doc.size} MB</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium">{doc.progress}%</div>
                    <div className="text-xs text-gray-500">{doc.uploadedAt}</div>
                  </div>
                </div>
                
                {/* Progress Bar */}
                <div className="w-full bg-gray-200 rounded-full h-2 mb-3">
                  <div className="bg-blue-600 h-2 rounded-full transition-all duration-300" 
                       style={{ width: `${doc.progress}%` }}></div>
                </div>

                {/* Processing Stages */}
                <div className="grid grid-cols-4 gap-4 text-xs">
                  <div className="flex items-center gap-1">
                    {getStatusIcon(doc.uploadStatus)}
                    <span>Upload</span>
                  </div>
                  <div className="flex items-center gap-1">
                    {getStatusIcon(doc.ocrStatus)}
                    <span>OCR/AI</span>
                  </div>
                  <div className="flex items-center gap-1">
                    {getStatusIcon(doc.translationStatus)}
                    <span>Translation</span>
                  </div>
                  <div className="flex items-center gap-1">
                    {getStatusIcon(doc.blockchainStatus)}
                    <span>Blockchain</span>
                  </div>
                </div>

                {/* Extracted Information */}
                {doc.extractedText && (
                  <div className="mt-3 p-3 bg-blue-50 rounded border-l-4 border-blue-400">
                    <div className="text-xs font-medium text-blue-800 mb-1">
                      Extracted ({doc.detectedLanguage}) - {(doc.confidence! * 100).toFixed(1)}% confidence
                    </div>
                    <div className="text-sm text-blue-700 mb-2">{doc.extractedText}</div>
                    {doc.translatedText && (
                      <div className="text-sm text-green-700 border-t border-blue-200 pt-2">
                        <span className="font-medium">Translation: </span>{doc.translatedText}
                      </div>
                    )}
                    {doc.medicalEntities && doc.medicalEntities.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {doc.medicalEntities.map((entity, idx) => (
                          <Badge key={idx} className="bg-purple-100 text-purple-800 text-xs">
                            {entity}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Voice Processing Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mic className="w-5 h-5" />
            Voice Medical History Processing
            <Badge className="bg-green-100 text-green-800 text-xs">
              <Info className="w-3 h-3 mr-1" />
              Amazon Transcribe Medical + Polly
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {voiceRecordings.map((recording) => (
              <div key={recording.id} className="border rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <Volume2 className="w-5 h-5 text-green-500" />
                    <div>
                      <div className="font-medium">{recording.patientName}</div>
                      <div className="text-sm text-gray-500">
                        {recording.duration}s • {recording.detectedLanguage} • {recording.audioQuality} quality
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {getStatusIcon(recording.transcriptionStatus)}
                    <span className="text-sm">Amazon Transcribe Medical</span>
                  </div>
                </div>

                {recording.transcribedText && (
                  <div className="space-y-2">
                    <div className="p-3 bg-gray-50 rounded">
                      <div className="text-xs font-medium text-gray-600 mb-1">
                        Original ({recording.detectedLanguage}) - {(recording.confidence! * 100).toFixed(1)}% confidence
                      </div>
                      <div className="text-sm text-right">{recording.transcribedText}</div>
                    </div>
                    {recording.translatedText && (
                      <div className="p-3 bg-blue-50 rounded">
                        <div className="text-xs font-medium text-blue-600 mb-1">AI Translation (English)</div>
                        <div className="text-sm">{recording.translatedText}</div>
                      </div>
                    )}
                    {recording.medicalTerms && recording.medicalTerms.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        <span className="text-xs text-gray-600">Medical Terms:</span>
                        {recording.medicalTerms.map((term, idx) => (
                          <Badge key={idx} className="bg-green-100 text-green-800 text-xs">
                            {term}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

const OfflineSyncDashboard = () => {
  const [isSyncing, setIsSyncing] = useState(false);

  const handleForceSync = () => {
    setIsSyncing(true);
    setTimeout(() => {
      setIsSyncing(false);
    }, 3000);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-2xl font-bold text-gray-900">Offline Capabilities & Sync Management</h2>
          <Badge className="bg-orange-100 text-orange-800 text-xs">
            <Info className="w-3 h-3 mr-1" />
            AWS DataSync + DynamoDB Local
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Badge className={`${syncStatus.bandwidth !== 'offline' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            <Network className="w-3 h-3 mr-1" />
            {syncStatus.bandwidth.toUpperCase()} Bandwidth
          </Badge>
          <Button 
            size="sm" 
            variant="outline" 
            onClick={handleForceSync}
            disabled={isSyncing}
            className="bg-white border-gray-300 text-gray-900 hover:bg-gray-50 hover:text-gray-900 hover:border-gray-400"
          >
            {isSyncing ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4 mr-2" />
            )}
            {isSyncing ? 'Syncing...' : 'Force Sync'}
          </Button>
        </div>
      </div>

    {/* Sync Status Cards */}
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <HardDrive className="w-5 h-5 text-blue-500" />
            Local Storage
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm">Documents Cached</span>
              <span className="font-medium">847</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Storage Used</span>
              <span className="font-medium">2.4 GB</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Available Space</span>
              <span className="font-medium text-green-600">12.6 GB</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div className="bg-blue-600 h-2 rounded-full" style={{ width: '16%' }}></div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <CloudUpload className="w-5 h-5 text-green-500" />
            Cloud Sync
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm">Last Sync</span>
              <span className="font-medium">2 min ago</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Pending Uploads</span>
              <span className="font-medium text-orange-600">{syncStatus.pendingUploads}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Failed Syncs</span>
              <span className="font-medium text-red-600">{syncStatus.failedSyncs}</span>
            </div>
            <div className="flex items-center gap-2">
                          <RotateCcw className="w-4 h-4 text-green-500" />
            <span className="text-sm text-green-600">Auto-sync enabled</span>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Smartphone className="w-5 h-5 text-purple-500" />
            Mobile Offline
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm">Offline Devices</span>
              <span className="font-medium">3,421</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Pending Records</span>
              <span className="font-medium text-blue-600">156</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Queue Processing</span>
              <Badge className="bg-green-100 text-green-800">Active</Badge>
            </div>
            <div className="flex items-center gap-2">
              <Radio className="w-4 h-4 text-purple-500" />
              <span className="text-sm">Mesh networking ready</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>

    {/* Offline Capabilities */}
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Satellite className="w-5 h-5" />
          Offline-First Architecture Features
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="space-y-4">
            <h4 className="font-medium text-gray-900 flex items-center gap-2">
              <FileText className="w-4 h-4" />
              Document Management
            </h4>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-500" />
                <span className="text-sm">Local document scanning & OCR</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-500" />
                <span className="text-sm">Offline image compression</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-500" />
                <span className="text-sm">Queue-based upload system</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-500" />
                <span className="text-sm">Automatic retry mechanisms</span>
              </div>
            </div>
          </div>
          
          <div className="space-y-4">
            <h4 className="font-medium text-gray-900 flex items-center gap-2">
              <Database className="w-4 h-4" />
              Data Synchronization
            </h4>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-500" />
                <span className="text-sm">Conflict-free replicated data types (CRDTs)</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-500" />
                <span className="text-sm">Delta synchronization</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-500" />
                <span className="text-sm">Bandwidth-adaptive sync</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-500" />
                <span className="text-sm">Peer-to-peer mesh networking</span>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h4 className="font-medium text-gray-900 flex items-center gap-2">
              <TranslateIcon className="w-4 h-4" />
              AI Translation Services
            </h4>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-500" />
                <span className="text-sm">Amazon Translate (Neural MT)</span>
                <Badge className="bg-blue-100 text-blue-800 text-xs">Real-time</Badge>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-500" />
                <span className="text-sm">Amazon Bedrock (Claude/Llama)</span>
                <Badge className="bg-purple-100 text-purple-800 text-xs">Context-aware</Badge>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-500" />
                <span className="text-sm">Custom Medical Terminology</span>
                <Badge className="bg-green-100 text-green-800 text-xs">Domain-specific</Badge>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-500" />
                <span className="text-sm">Cultural Context Adaptation</span>
                <Badge className="bg-orange-100 text-orange-800 text-xs">Refugee-focused</Badge>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-500" />
                <span className="text-sm">Offline Translation Cache</span>
                <Badge className="bg-gray-100 text-gray-800 text-xs">No-internet</Badge>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>

    {/* AI Translation Services Details */}
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bot className="w-5 h-5" />
          Advanced AI Translation Pipeline
          <Badge className="bg-purple-100 text-purple-800 text-xs">
            <Info className="w-3 h-3 mr-1" />
            Amazon Bedrock + Custom Models
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <h4 className="font-medium text-gray-900">Supported Languages for Refugees</h4>
            <div className="grid grid-cols-2 gap-2">
              {[
                { lang: 'Arabic', region: 'Syria, Iraq, Lebanon', count: '15M+' },
                { lang: 'Farsi/Dari', region: 'Afghanistan, Iran', count: '8M+' },
                { lang: 'Ukrainian', region: 'Ukraine conflict', count: '6M+' },
                { lang: 'Rohingya', region: 'Myanmar', count: '2M+' },
                { lang: 'Tigrinya', region: 'Eritrea, Ethiopia', count: '1.5M+' },
                { lang: 'Somali', region: 'Somalia, Horn of Africa', count: '3M+' },
              ].map((item, index) => (
                <div key={index} className="p-3 border rounded-lg">
                  <div className="font-medium text-sm">{item.lang}</div>
                  <div className="text-xs text-gray-600">{item.region}</div>
                  <div className="text-xs text-blue-600">{item.count} speakers</div>
                </div>
              ))}
            </div>
          </div>
          
          <div className="space-y-4">
            <h4 className="font-medium text-gray-900">Medical Translation Features</h4>
            <div className="space-y-3">
              <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg">
                <Brain className="w-5 h-5 text-blue-600" />
                <div>
                  <div className="font-medium text-sm">Medical Entity Recognition</div>
                  <div className="text-xs text-gray-600">Amazon Comprehend Medical identifies symptoms, medications, procedures</div>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 bg-green-50 rounded-lg">
                <Cpu className="w-5 h-5 text-green-600" />
                <div>
                  <div className="font-medium text-sm">Cultural Context Adaptation</div>
                  <div className="text-xs text-gray-600">Adjusts medical terminology for cultural understanding</div>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 bg-purple-50 rounded-lg">
                <Workflow className="w-5 h-5 text-purple-600" />
                <div>
                  <div className="font-medium text-sm">Multi-Modal Translation</div>
                  <div className="text-xs text-gray-600">Text, voice, and image translation in real-time</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  </div>
  );
};

const SettingsDashboard = () => (
  <div className="space-y-6">
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-2">System Settings</h2>
      <p className="text-gray-600">Configure HavenHealthPassport system preferences</p>
    </div>
    
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg text-gray-900">Security Settings</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-700">Blockchain Verification</span>
              <Badge className="bg-green-100 text-green-800">Enabled</Badge>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-700">Two-Factor Authentication</span>
              <Badge className="bg-green-100 text-green-800">Required</Badge>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-700">Data Encryption</span>
              <Badge className="bg-green-100 text-green-800">AES-256</Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg text-gray-900">Language Settings</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-700">Auto-Translation</span>
              <Badge className="bg-green-100 text-green-800">Enabled</Badge>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-700">Preferred Languages</span>
              <span className="text-sm text-gray-600">Arabic, English, French</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-700">Medical Terminology</span>
              <Badge className="bg-blue-100 text-blue-800">Enhanced</Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
);

// Utility Components
const MetricCard = ({ title, value, icon, trend, color }: {
  title: string;
  value: string;
  icon: React.ReactNode;
  trend: string;
  color: string;
}) => (
  <Card>
    <CardContent className="p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          <p className={`text-sm ${color}`}>{trend}</p>
        </div>
        <div className={`${color}`}>
          {icon}
        </div>
      </div>
    </CardContent>
  </Card>
);

const DashboardContent = ({ selectedView }: { selectedView: string }) => {
  const renderContent = () => {
    switch (selectedView) {
      case "overview":
        return <OverviewDashboard />;
      case "patients":
        return <PatientsManagement />;
      case "analytics":
        return <MedicalAnalytics />;
      case "blockchain":
        return <BlockchainVerification />;
      case "translation":
        return <AITranslationDashboard />;
      case "camps":
        return <CampOperations />;
      case "emergency":
        return <EmergencyResponse />;
      case "mobile":
        return <MobileSync />;
      case "documents":
        return <DocumentProcessingDashboard />;
      case "offline":
        return <OfflineSyncDashboard />;
      case "settings":
        return <SettingsDashboard />;
      default:
        return <OverviewDashboard />;
    }
  };

  return (
    <div className="flex flex-1">
      <div className="p-4 md:p-8 rounded-tl-2xl border border-gray-200 bg-white flex flex-col gap-4 flex-1 w-full h-full overflow-y-auto relative">
        {renderContent()}
      </div>
    </div>
  );
};

export function HavenDashboardDemo() {
  const [selectedView, setSelectedView] = useState("overview");
  
  const links = [
    {
      label: "Overview",
      href: "#",
      icon: <LayoutDashboard className="text-neutral-700 dark:text-neutral-200 h-5 w-5 flex-shrink-0" />,
      id: "overview"
    },
    {
      label: "Patient Records",
      href: "#",
      icon: <Users className="text-neutral-700 dark:text-neutral-200 h-5 w-5 flex-shrink-0" />,
      id: "patients"
    },
    {
      label: "Document Processing",
      href: "#",
      icon: <Upload className="text-neutral-700 dark:text-neutral-200 h-5 w-5 flex-shrink-0" />,
      id: "documents"
    },
    {
      label: "Offline Sync",
      href: "#",
      icon: <Wifi className="text-neutral-700 dark:text-neutral-200 h-5 w-5 flex-shrink-0" />,
      id: "offline"
    },
    {
      label: "Medical Analytics",
      href: "#",
      icon: <BarChart3 className="text-neutral-700 dark:text-neutral-200 h-5 w-5 flex-shrink-0" />,
      id: "analytics"
    },
    {
      label: "Blockchain Verification",
      href: "#",
      icon: <Shield className="text-neutral-700 dark:text-neutral-200 h-5 w-5 flex-shrink-0" />,
      id: "blockchain"
    },
    {
      label: "AI Translation",
      href: "#",
      icon: <Languages className="text-neutral-700 dark:text-neutral-200 h-5 w-5 flex-shrink-0" />,
      id: "translation"
    },
    {
      label: "Camp Operations",
      href: "#",
      icon: <Map className="text-neutral-700 dark:text-neutral-200 h-5 w-5 flex-shrink-0" />,
      id: "camps"
    },
    {
      label: "Emergency Response",
      href: "#",
      icon: <AlertTriangle className="text-neutral-700 dark:text-neutral-200 h-5 w-5 flex-shrink-0" />,
      id: "emergency"
    },
    {
      label: "Mobile Sync",
      href: "#",
      icon: <Smartphone className="text-neutral-700 dark:text-neutral-200 h-5 w-5 flex-shrink-0" />,
      id: "mobile"
    },
    {
      label: "Settings",
      href: "#",
      icon: <Settings className="text-neutral-700 dark:text-neutral-200 h-5 w-5 flex-shrink-0" />,
      id: "settings"
    },
  ];

  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-lg flex flex-col md:flex-row bg-white w-full flex-1 border border-gray-200 h-[80vh] relative">
      <Sidebar open={open} setOpen={setOpen}>
        <SidebarBody className="justify-between gap-10">
          <div className="flex flex-col flex-1 overflow-y-auto overflow-x-hidden">
            {open ? <HavenLogo /> : <HavenLogoIcon />}
            <div className="mt-8 flex flex-col gap-2">
              {links.map((link, idx) => (
                <div
                  key={idx}
                  onClick={() => setSelectedView(link.id)}
                  className={cn(
                    "cursor-pointer",
                    selectedView === link.id && "bg-blue-100 border border-blue-300 rounded-md"
                  )}
                >
                  <SidebarLink link={link} />
                </div>
              ))}
            </div>
          </div>
          <div>
            <SidebarLink
              link={{
                label: "Health Admin",
                href: "#",
                icon: (
                  <div className="h-7 w-7 bg-gradient-to-r from-primary to-[#9fa0f7] rounded-full flex items-center justify-center text-white text-sm font-bold">
                    HA
                  </div>
                ),
              }}
            />
          </div>
        </SidebarBody>
      </Sidebar>
      <DashboardContent selectedView={selectedView} />
    </div>
  );
} 