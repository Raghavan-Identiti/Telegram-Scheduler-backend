// src/App.tsx
import React, { useState } from 'react';
import {
  ClerkProvider,
  SignedIn,
  SignedOut,
  SignIn,
  useUser,
  useClerk,
} from '@clerk/clerk-react';
import { Header } from './components/Header';
import { AutoSchedulerTab } from './components/AutoSchedulerTab';
import { RecurringSchedulerTab } from './components/RecurringSchedulerTab';
import { WhatsAppSchedulerTab } from './components/WhatsAppSchedulerTab';
import { AnalyticsTab } from './components/AnalyticsTab';
import { LogsSheetsTab } from './components/LogsSheetsTab';
import { ContentReaderTab } from './components/ContentReaderTab';
import { AccessDenied } from './components/AccessDenied';
import { ClerkSetupGuide } from './components/ClerkSetupGuide';
import { StorageService } from './services/storage';
import { AppSettings } from './types';
import {
  CLERK_PUBLISHABLE_KEY,
  PRIMARY_ADMIN_EMAIL,
  isEmailAuthorized,
  getUserRole,
} from './services/authConfig';
import { CheckCircle2, X, Send, ShieldCheck, Lock } from 'lucide-react';

/**
 * Main application dashboard containing all tabs, workflows, and global header.
 */
interface DashboardProps {
  userEmail: string;
  userRole: string;
  clerkActive: boolean;
  onSignOut?: () => void;
}

const Dashboard: React.FC<DashboardProps> = ({
  userEmail,
  userRole,
  clerkActive,
  onSignOut,
}) => {
  const [activeTab, setActiveTab] = useState<string>('content-reader');
  const [settings, setSettings] = useState<AppSettings>(() => StorageService.getSettings());
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(prev => (prev === msg ? null : prev));
    }, 4000);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Global Header with user profile and role */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        settings={settings}
        userEmail={userEmail}
        userRole={userRole}
        clerkActive={clerkActive}
        onSignOut={onSignOut}
      />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === 'content-reader' && (
          <ContentReaderTab
            settings={settings}
            onNotify={showToast}
          />
        )}
        {activeTab === 'auto-schedule' && (
          <AutoSchedulerTab onScheduleSuccess={showToast} />
        )}
        {activeTab === 'recurring' && (
          <RecurringSchedulerTab onNotify={showToast} />
        )}
        {activeTab === 'whatsapp' && (
          <WhatsAppSchedulerTab onNotify={showToast} />
        )}
        {activeTab === 'analytics' && (
          <AnalyticsTab onNotify={showToast} />
        )}
        {activeTab === 'logs-sheets' && (
          <LogsSheetsTab
            settings={settings}
            onUpdateSettings={setSettings}
            onNotify={showToast}
          />
        )}
      </main>

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-5 right-5 z-50 bg-slate-900 border border-emerald-500/50 text-white px-4 py-3 rounded-xl shadow-2xl flex items-center gap-3 animate-in fade-in slide-in-from-bottom-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span className="text-xs font-medium">{toastMessage}</span>
          <button
            onClick={() => setToastMessage(null)}
            className="text-slate-400 hover:text-white p-0.5 rounded cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Footer */}
      <footer className="border-t border-slate-900 py-4 text-center text-xs text-slate-500">
        <p>TeleQueue &bull; Telegram &amp; WhatsApp Post Scheduler &amp; Click Analytics &bull; Multi-Channel Engine</p>
      </footer>
    </div>
  );
};

/**
 * Clerk Authenticated Router that evaluates email whitelist.
 */
const ClerkAuthGate: React.FC = () => {
  const { user, isLoaded } = useUser();

  if (!isLoaded) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-slate-300">
        <div className="h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-xs font-mono">Verifying Clerk authorization...</p>
      </div>
    );
  }

  const email = user?.primaryEmailAddress?.emailAddress || '';
  const isAuthorized = isEmailAuthorized(email);

  if (!isAuthorized) {
    return <AccessDenied />;
  }

  const role = getUserRole(email);

  return (
    <Dashboard
      userEmail={email}
      userRole={role}
      clerkActive={true}
    />
  );
};

/**
 * Centered Sign-In page when signed out from Clerk.
 */
const ClerkSignInView: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4 text-slate-100 font-sans relative overflow-hidden">
      {/* Ambient background glows */}
      <div className="absolute -top-32 -left-32 w-64 h-64 bg-blue-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-32 -right-32 w-64 h-64 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />

      {/* Brand Header */}
      <div className="mb-8 text-center space-y-2">
        <div className="inline-flex items-center justify-center h-14 w-14 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-500 shadow-xl shadow-blue-500/20 text-white mb-2">
          <Send className="w-7 h-7 -rotate-12 translate-x-0.5" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center justify-center gap-2">
          TeleQueue Portal
          <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 bg-blue-500/15 text-blue-400 border border-blue-500/30 rounded">
            v2.5
          </span>
        </h1>
        <p className="text-xs text-slate-400 flex items-center justify-center gap-1.5">
          <Lock className="w-3.5 h-3.5 text-slate-500" />
          Protected Organization Workspace &bull; Sign in with your authorized email
        </p>
      </div>

      {/* Clerk Sign In Component */}
      <div className="shadow-2xl rounded-2xl overflow-hidden border border-slate-800">
        <SignIn
          routing="hash"
          appearance={{
            elements: {
              rootBox: 'mx-auto',
              card: 'bg-slate-900 border border-slate-800 shadow-2xl text-slate-100',
              headerTitle: 'text-white text-lg font-bold',
              headerSubtitle: 'text-slate-400 text-xs',
              formButtonPrimary: 'bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold py-2.5',
              formFieldInput: 'bg-slate-950 border-slate-700 text-white placeholder-slate-500 text-xs',
              formFieldLabel: 'text-slate-300 text-xs',
              footerActionLink: 'text-blue-400 hover:text-blue-300 text-xs',
              socialButtonsBlockButton: 'bg-slate-950 border-slate-800 hover:bg-slate-800 text-white text-xs',
              dividerLine: 'bg-slate-800',
              dividerText: 'text-slate-500 text-xs',
            },
          }}
        />
      </div>

      <div className="mt-8 text-center text-xs text-slate-500 flex items-center justify-center gap-1.5">
        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
        Restricted to <span className="text-slate-400 font-mono">raghavan@identitidesign.com</span> &amp; authorized staff
      </div>
    </div>
  );
};

export const App: React.FC = () => {
  const [activeKey, setActiveKey] = useState<string>(() => {
    return CLERK_PUBLISHABLE_KEY || localStorage.getItem('clerk_temp_pub_key') || '';
  });

  const [devBypass, setDevBypass] = useState<boolean>(() => {
    // If no key is set yet, check if user had bypassed in session
    return sessionStorage.getItem('telequeue_dev_bypass') === 'true';
  });

  const handleSetTemporaryKey = (key: string) => {
    localStorage.setItem('clerk_temp_pub_key', key);
    sessionStorage.removeItem('telequeue_dev_bypass');
    setActiveKey(key);
    setDevBypass(false);
  };

  const handleBypassDevelopment = () => {
    sessionStorage.setItem('telequeue_dev_bypass', 'true');
    setDevBypass(true);
  };

  const handleDevSignOut = () => {
    sessionStorage.removeItem('telequeue_dev_bypass');
    setDevBypass(false);
  };

  // If no Clerk Publishable Key is provided and not in dev bypass mode:
  // Render setup guide to help input the key seamlessly
  if (!activeKey && !devBypass) {
    return (
      <ClerkSetupGuide
        onSetTemporaryKey={handleSetTemporaryKey}
        onBypassDevelopment={handleBypassDevelopment}
      />
    );
  }

  // If development sandbox bypass is active:
  if (devBypass) {
    return (
      <Dashboard
        userEmail={PRIMARY_ADMIN_EMAIL}
        userRole="Admin"
        clerkActive={false}
        onSignOut={handleDevSignOut}
      />
    );
  }

  // Full Clerk Auth provider wrapper
  return (
    <ClerkProvider publishableKey={activeKey}>
      <SignedIn>
        <ClerkAuthGate />
      </SignedIn>
      <SignedOut>
        <ClerkSignInView />
      </SignedOut>
    </ClerkProvider>
  );
};

export default App;
