// src/components/AccessDenied.tsx
import React from 'react';
import { useClerk, useUser } from '@clerk/clerk-react';
import { ShieldAlert, LogOut, Mail, Lock, Building2 } from 'lucide-react';
import { PRIMARY_ADMIN_EMAIL, ALLOWED_DOMAIN } from '../services/authConfig';

export const AccessDenied: React.FC = () => {
  const { signOut } = useClerk();
  const { user } = useUser();

  const currentEmail = user?.primaryEmailAddress?.emailAddress || 'Unknown account';

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4 sm:p-6 text-slate-100 font-sans">
      <div className="max-w-md w-full bg-slate-900/90 border border-red-500/30 rounded-2xl p-6 sm:p-8 shadow-2xl backdrop-blur-xl relative overflow-hidden">
        {/* Ambient background glow */}
        <div className="absolute -top-24 -left-24 w-48 h-48 bg-red-600/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -right-24 w-48 h-48 bg-amber-600/10 rounded-full blur-3xl pointer-events-none" />

        {/* Warning Icon Badge */}
        <div className="flex justify-center mb-6">
          <div className="h-16 w-16 rounded-2xl bg-red-500/10 border border-red-500/30 flex items-center justify-center text-red-400 shadow-inner">
            <ShieldAlert className="w-8 h-8" />
          </div>
        </div>

        <div className="text-center space-y-2 mb-6">
          <span className="text-[11px] font-bold uppercase tracking-wider px-2.5 py-1 bg-red-500/15 text-red-400 border border-red-500/30 rounded-full inline-block">
            Access Restricted
          </span>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
            Unauthorized Account
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
            This workspace contains private Telegram &amp; WhatsApp marketing automation channels and is restricted to authorized personnel.
          </p>
        </div>

        {/* User Context Box */}
        <div className="bg-slate-950/80 rounded-xl p-4 border border-slate-800 text-xs space-y-2.5 mb-6">
          <div className="flex items-center justify-between text-slate-400">
            <span>Signed in as:</span>
            <span className="font-mono text-slate-200 truncate max-w-[200px]" title={currentEmail}>
              {currentEmail}
            </span>
          </div>

          <div className="flex items-center justify-between text-slate-400 border-t border-slate-800/80 pt-2.5">
            <span className="flex items-center gap-1.5">
              <Building2 className="w-3.5 h-3.5 text-slate-500" />
              Organization:
            </span>
            <span className="text-slate-300 font-medium">Identiti Design</span>
          </div>

          <div className="flex items-center justify-between text-slate-400 border-t border-slate-800/80 pt-2.5">
            <span className="flex items-center gap-1.5">
              <Lock className="w-3.5 h-3.5 text-slate-500" />
              Access Policy:
            </span>
            <span className="text-red-400 font-medium">Requires @{ALLOWED_DOMAIN}</span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="space-y-3">
          <button
            onClick={() => signOut({ redirectUrl: '/' })}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-red-600 hover:bg-red-500 text-white rounded-xl text-sm font-semibold transition-all shadow-lg shadow-red-600/20 cursor-pointer"
          >
            <LogOut className="w-4 h-4" />
            Sign Out &amp; Switch Account
          </button>

          <a
            href={`mailto:${PRIMARY_ADMIN_EMAIL}?subject=Access%20Request%20to%20TeleQueue&body=Hello%20Raghavan,%20please%20grant%20access%20to%20my%20account:%20${encodeURIComponent(currentEmail)}`}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-800/80 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white rounded-xl text-sm font-medium transition-all cursor-pointer"
          >
            <Mail className="w-4 h-4 text-slate-400" />
            Contact Administrator
          </a>
        </div>
      </div>

      <p className="mt-8 text-xs text-slate-500 text-center">
        Identiti Design Internal Platform &bull; Security Enforced via Clerk Auth
      </p>
    </div>
  );
};
