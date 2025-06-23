import DebugScrollToTop from "@/components/DebugScrollToTop";
import ScrollToTopButton from "@/components/ui/scroll-to-top-button";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Index from "./pages/Index";

import AboutBuildPage from "./pages/AboutBuildPage";
import AboutMePage from "./pages/AboutMePage";
import AnalyticsPage from "./pages/AnalyticsPage";
import ArchitecturePage from "./pages/ArchitecturePage";
import ContactPage from "./pages/ContactPage";
import DemoShowcase from "./pages/DemoShowcase";

import NewPatientPage from "./pages/NewPatientPage";
import NotificationsPage from "./pages/NotificationsPage";
import OverviewPage from "./pages/OverviewPage";
import PatientsPage from "./pages/PatientsPage";
import PricingPage from "./pages/PricingPage";
import RecordsPage from "./pages/RecordsPage";
import { SchedulePage } from "./pages/SchedulePage";
import SettingsPage from "./pages/SettingsPage";
import TryDashboardPage from "./pages/TryDashboardPage";
import UseCasesPage from "./pages/UseCasesPage";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <div className="min-h-screen bg-background">
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <DebugScrollToTop />
          <Routes>
            <Route path="/" element={<Index />} />
            <Route path="/overview" element={<OverviewPage />} />
            <Route path="/architecture" element={<ArchitecturePage />} />
            <Route path="/use-cases" element={<UseCasesPage />} />
            <Route path="/about-build" element={<AboutBuildPage />} />
            <Route path="/about-me" element={<AboutMePage />} />
            <Route path="/contact" element={<ContactPage />} />
            <Route path="/pricing" element={<PricingPage />} />

            <Route path="/try-dashboard" element={<TryDashboardPage />} />

            <Route path="/dashboard/patients" element={<PatientsPage />} />
            <Route path="/dashboard/schedule" element={<SchedulePage />} />
            <Route path="/dashboard/records" element={<RecordsPage />} />
            <Route path="/dashboard/analytics" element={<AnalyticsPage />} />
            <Route path="/dashboard/notifications" element={<NotificationsPage />} />
            <Route path="/dashboard/settings" element={<SettingsPage />} />
            <Route path="/dashboard/new-patient" element={<NewPatientPage />} />
            <Route path="/demos" element={<DemoShowcase />} />
          </Routes>
          <ScrollToTopButton />
        </BrowserRouter>
      </div>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
