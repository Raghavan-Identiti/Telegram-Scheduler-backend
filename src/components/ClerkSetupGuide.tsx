// src/components/ClerkSetupGuide.tsx
import React, { useState } from 'react';
import { KeyRound, ShieldCheck, ExternalLink, ArrowRight, Check, Copy } from 'lucide-react';
import { PRIMARY_ADMIN_EMAIL } from '../services/authConfig';

interface ClerkSetupGuideProps {
  onSetTemporaryKey: (key: string) => void;
  onBypassDevelopment: () => void;
}

export const ClerkSetupGuide: React.FC<ClerkSetupGuideProps> = ({
  onSetTemporaryKey,
  onBypassDevelopment,
}) => {
  const [manualKey, setManualKey] = useState('');
  const [copied, setCopied] = useState<string | null>(null);

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2500);
  };

  const sampleEnv = `# Clerk Authentication Credentials (Add to .env or Render Environment)
VITE_CLERK_PUBLISHABLE_KEY=pk_test_your_publishable_key_here
CLERK_SECRET_KEY=sk_test_your_secret_key_here
ALLOWED_EMAILS=${PRIMARY_ADMIN_EMAIL}
ALLOWED_DOMAINS=identitidesign.com`;

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4 sm:p-6 text-slate-100 font-sans">
      <div className="max-w-xl w-full bg-slate-900/90 border border-blue-500/30 rounded-2xl p-6 sm:p-8 shadow-2xl backdrop-blur-xl relative overflow-hidden">
        {/* Glow */}
        <div className="absolute -top-24 -left-24 w-48 h-48 bg-blue-600/15 rounded-full blur-3xl pointer-events-none" />

        {/* Icon & Title */}
        <div className="flex items-center gap-3 mb-6">
          <div className="h-12 w-12 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
            <KeyRound className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              Clerk Authentication Integration
              <span className="text-[10px] uppercase font-bold px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded-md border border-blue-500/30">
                Ready
              </span>
            </h1>
            <p className="text-xs text-slate-400">
              Frontend &amp; backend Clerk security modules are installed and configured.
            </p>
          </div>
        </div>

        {/* Instructions */}
        <div className="space-y-4 text-xs text-slate-300 mb-6">
          <div className="p-3.5 bg-slate-950/80 rounded-xl border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-white flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                Step 1: Obtain Keys from Clerk Dashboard
              </span>
              <a
                href="https://dashboard.clerk.com"
                target="_blank"
                rel="noreferrer"
                className="text-blue-400 hover:text-blue-300 flex items-center gap-1 font-medium"
              >
                Open Dashboard <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <p className="text-slate-400">
              Create an application in Clerk, navigate to <strong>API Keys</strong>, and copy your <strong>Publishable key</strong> (starts with <code className="text-blue-300">pk_test_</code> or <code className="text-blue-300">pk_live_</code>).
            </p>
          </div>

          <div className="p-3.5 bg-slate-950/80 rounded-xl border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-white">Step 2: Add Environment Variables</span>
              <button
                onClick={() => handleCopy(sampleEnv, 'env')}
                className="text-slate-400 hover:text-white flex items-center gap-1 text-[11px] cursor-pointer"
              >
                {copied === 'env' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                {copied === 'env' ? 'Copied' : 'Copy Template'}
              </button>
            </div>
            <pre className="bg-slate-900 p-2.5 rounded-lg border border-slate-800/80 font-mono text-[11px] text-slate-300 overflow-x-auto">
              {sampleEnv}
            </pre>
          </div>

          {/* Quick paste in UI for immediate testing */}
          <div className="p-3.5 bg-slate-950/80 rounded-xl border border-slate-800 space-y-2.5">
            <span className="font-semibold text-white">Step 3: Quick Test Key in Browser</span>
            <p className="text-slate-400 text-[11px]">
              Paste your Publishable Key below to test the live Clerk login modal immediately:
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="pk_test_..."
                value={manualKey}
                onChange={e => setManualKey(e.target.value)}
                className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
              <button
                disabled={!manualKey.trim().startsWith('pk_')}
                onClick={() => onSetTemporaryKey(manualKey.trim())}
                className="px-3.5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer"
              >
                Apply <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>

        {/* Development sandbox bypass */}
        <div className="border-t border-slate-800 pt-5 flex items-center justify-between">
          <div className="text-[11px] text-slate-400">
            Previewing in AI Studio development sandbox?
          </div>
          <button
            onClick={onBypassDevelopment}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white rounded-lg text-xs font-medium transition-all cursor-pointer"
          >
            Launch as {PRIMARY_ADMIN_EMAIL} &rarr;
          </button>
        </div>
      </div>
    </div>
  );
};
