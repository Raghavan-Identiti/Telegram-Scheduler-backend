import React, { useState, useEffect } from 'react';
import { Send, Clock, CheckCircle2, AlertCircle, RefreshCw, LogOut } from 'lucide-react';
import { UserButton } from '@clerk/clerk-react';
import { AppSettings } from '../types';

interface HeaderProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  settings: AppSettings;
  userEmail?: string;
  userRole?: string;
  clerkActive?: boolean;
  onSignOut?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  settings,
  userEmail,
  userRole = 'Admin',
  clerkActive = true,
  onSignOut,
}) => {
  const [istTime, setIstTime] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setIstTime(
        now.toLocaleTimeString('en-IN', {
          timeZone: 'Asia/Kolkata',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: true,
        }) + ' IST'
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const navItems = [
    { id: 'content-reader', label: 'Content Reader', badge: '⚡ ~2s' },
    { id: 'auto-schedule', label: 'Auto Scheduler', badge: null },
    { id: 'recurring', label: 'Recurring Schedules', badge: null },
    { id: 'whatsapp', label: 'WhatsApp Hub', badge: 'Baileys' },
    { id: 'analytics', label: 'Post Analytics & Clicks', badge: null },
    { id: 'logs-sheets', label: 'Logs & GSheet Config', badge: null },
  ];

  return (
    <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/20 text-white font-bold">
              <Send className="w-5 h-5 -rotate-12 translate-x-0.5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg tracking-tight text-white">TeleQueue</span>
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded">
                  v2.5
                </span>
              </div>
              <p className="text-xs text-slate-400">Telegram & WhatsApp Dispatcher</p>
            </div>
          </div>

          {/* Center Info: Live IST Clock & Status */}
          <div className="hidden lg:flex items-center gap-5 text-xs text-slate-300">
            <div className="flex items-center gap-1.5 px-3 py-1 bg-slate-800/80 rounded-full border border-slate-700/60 font-mono">
              <Clock className="w-3.5 h-3.5 text-blue-400" />
              <span>{istTime || 'Loading IST...'}</span>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5" title="Telegram Telethon Engine">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span className="text-slate-400">Telegram:</span>
                <span className="text-emerald-400 font-medium">Ready</span>
              </div>
              <div className="flex items-center gap-1.5" title="WhatsApp Baileys Service">
                <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
                <span className="text-slate-400">WhatsApp:</span>
                <span className="text-emerald-400 font-medium">Connected</span>
              </div>
              <div className="flex items-center gap-1.5" title="Google Sheets Sync Status">
                <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
                <span className="text-slate-400">GSheets:</span>
                <span className="text-emerald-400 font-medium">Synced</span>
              </div>
            </div>
          </div>

          {/* User Profile & Auth Status */}
          <div className="flex items-center gap-3">
            {userEmail && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800/80 rounded-xl border border-slate-700/80 text-xs">
                <div className="flex flex-col text-right hidden sm:block">
                  <span className="text-[11px] font-medium text-slate-200 truncate max-w-[150px]">
                    {userEmail}
                  </span>
                  <span className="text-[10px] text-emerald-400 font-semibold tracking-wide">
                    {userRole}
                  </span>
                </div>
                <span className="px-2 py-0.5 bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-[10px] rounded-full font-bold uppercase sm:hidden">
                  {userRole}
                </span>
                {clerkActive ? (
                  <UserButton
                    afterSignOutUrl="/"
                    appearance={{
                      elements: {
                        avatarBox: 'w-7 h-7 border border-slate-600',
                      },
                    }}
                  />
                ) : (
                  onSignOut && (
                    <button
                      onClick={onSignOut}
                      title="Sign Out"
                      className="text-slate-400 hover:text-white p-1 hover:bg-slate-700/50 rounded-lg transition-colors cursor-pointer"
                    >
                      <LogOut className="w-4 h-4" />
                    </button>
                  )
                )}
              </div>
            )}
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex space-x-1 sm:space-x-4 border-t border-slate-800/80 overflow-x-auto py-2 scrollbar-none">
          {navItems.map(item => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`flex items-center gap-2 px-3 py-2 text-xs sm:text-sm font-medium rounded-lg transition-all whitespace-nowrap cursor-pointer ${
                  isActive
                    ? 'bg-blue-600/15 text-blue-400 border border-blue-500/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <span>{item.label}</span>
                {item.badge && (
                  <span className="px-1.5 py-0.2 bg-emerald-500/20 text-emerald-400 text-[10px] rounded font-semibold">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </header>
  );
};
