import React, { useState } from 'react';
import { Header } from './components/Header';
import { AutoSchedulerTab } from './components/AutoSchedulerTab';
import { RecurringSchedulerTab } from './components/RecurringSchedulerTab';
import { WhatsAppSchedulerTab } from './components/WhatsAppSchedulerTab';
import { AnalyticsTab } from './components/AnalyticsTab';
import { LogsSheetsTab } from './components/LogsSheetsTab';
import { StorageService } from './services/storage';
import { AppSettings } from './types';
import { CheckCircle2, X } from 'lucide-react';

import { ContentReaderTab } from './components/ContentReaderTab';

export const App: React.FC = () => {
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
      {/* Global Header */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        settings={settings}
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

export default App;
