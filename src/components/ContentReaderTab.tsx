import React, { useState, useEffect, useMemo } from 'react';
import {
  Zap,
  Calendar,
  Layers,
  FileSpreadsheet,
  RefreshCw,
  ExternalLink,
  Download,
  Eye,
  MousePointerClick,
  Share2,
  CheckCircle2,
  AlertCircle,
  Clock,
  Sparkles,
  Link as LinkIcon,
  ChevronRight,
  Table,
  Plus
} from 'lucide-react';
import * as XLSX from 'xlsx';
import { CHANNELS } from '../services/channels';
import { AppSettings } from '../types';

interface ContentReaderTabProps {
  settings: AppSettings;
  onNotify: (msg: string) => void;
}

interface ScrapedPost {
  id: number | string;
  time: string;
  views: number;
  text: string;
  links: string[];
  channel: string;
  status: string;
  media_type: string;
  telegram_clicks?: number;
  whatsapp_clicks?: number;
  'Telegram-clicks'?: number;
  'Whatsapp-clicks'?: number;
}

export const ContentReaderTab: React.FC<ContentReaderTabProps> = ({
  settings,
  onNotify,
}) => {
  const [selectedChannel, setSelectedChannel] = useState<string>('amazonindiaassociates');
  const [datePreset, setDatePreset] = useState<'range' | 'yesterday' | 'today' | 'custom'>('range');
  
  // Default date range: 10 days back to today (e.g., Oct 1 to Oct 15)
  const [startDate, setStartDate] = useState<string>(() => {
    const d = new Date();
    d.setDate(d.getDate() - 9);
    return d.toISOString().split('T')[0];
  });
  const [endDate, setEndDate] = useState<string>(() => {
    return new Date().toISOString().split('T')[0];
  });

  // Dynamic channel sheet config
  const channelConfig = settings.channel_sheets[selectedChannel] || {
    sheet_id: '',
    sheet_url: '',
    sheet_tab: '',
  };
  const [customSheetUrl, setCustomSheetUrl] = useState<string>(channelConfig.sheet_url || '');

  // Keep custom sheet in sync if channel changes
  useEffect(() => {
    const conf = settings.channel_sheets[selectedChannel];
    if (conf) {
      setCustomSheetUrl(conf.sheet_url || '');
    } else {
      setCustomSheetUrl('');
    }
  }, [selectedChannel, settings.channel_sheets]);

  // Loading & results state
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [executionTime, setExecutionTime] = useState<number | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState<boolean>(true);
  const [posts, setPosts] = useState<ScrapedPost[]>([]);

  // Active subsheet date tab (matches Google Sheets tabs at bottom)
  const [activeDateTab, setActiveDateTab] = useState<string>('');

  const handlePresetChange = (preset: 'range' | 'yesterday' | 'today' | 'custom') => {
    setDatePreset(preset);
    const now = new Date();
    if (preset === 'today') {
      const todayStr = now.toISOString().split('T')[0];
      setStartDate(todayStr);
      setEndDate(todayStr);
    } else if (preset === 'yesterday') {
      const y = new Date();
      y.setDate(y.getDate() - 1);
      const yStr = y.toISOString().split('T')[0];
      setStartDate(yStr);
      setEndDate(yStr);
    } else if (preset === 'range') {
      const start = new Date();
      start.setDate(start.getDate() - 9);
      setStartDate(start.toISOString().split('T')[0]);
      setEndDate(now.toISOString().split('T')[0]);
    }
  };

  // Suffix helper (e.g. 1st, 2nd, 3rd, 15th)
  const getOrdinalSuffix = (day: number): string => {
    if (day >= 11 && day <= 13) return 'th';
    switch (day % 10) {
      case 1: return 'st';
      case 2: return 'nd';
      case 3: return 'rd';
      default: return 'th';
    }
  };

  // Format date helper: "YYYY-MM-DD" -> "15th Oct 2026", "1st Oct 2026"
  const formatDateToTabName = (dateStr: string): string => {
    try {
      const parts = dateStr.split('-');
      if (parts.length === 3) {
        const d = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
        const day = d.getDate();
        const suffix = getOrdinalSuffix(day);
        const month = d.toLocaleString('en-US', { month: 'short' });
        const year = d.getFullYear();
        return `${day}${suffix} ${month} ${year}`;
      }
    } catch {
      // fallback
    }
    return dateStr;
  };

  // Group posts by date for individual subsheets
  const postsByDate = useMemo(() => {
    const map: Record<string, ScrapedPost[]> = {};
    posts.forEach(p => {
      let dKey = '';
      if (p.time) {
        const match = p.time.match(/(\d{4}-\d{2}-\d{2})/);
        if (match) {
          dKey = formatDateToTabName(match[1]);
        }
      }
      if (!dKey) {
        dKey = formatDateToTabName(startDate);
      }
      if (!map[dKey]) {
        map[dKey] = [];
      }
      map[dKey].push(p);
    });
    return map;
  }, [posts, startDate]);

  // Helper to parse "15th Oct 2026" to timestamp for proper chronological tab ordering
  const parseTabNameToTime = (tabName: string): number => {
    try {
      const clean = tabName.replace(/(st|nd|rd|th)/i, '');
      const t = Date.parse(clean);
      if (!isNaN(t)) return t;
    } catch {
      // fallback
    }
    return 0;
  };

  // Available date tabs sorted chronologically
  const dateTabs = useMemo(() => {
    return Object.keys(postsByDate).sort((a, b) => parseTabNameToTime(a) - parseTabNameToTime(b));
  }, [postsByDate]);

  // Set default active tab
  useEffect(() => {
    if (dateTabs.length > 0 && (!activeDateTab || !dateTabs.includes(activeDateTab))) {
      setActiveDateTab(dateTabs[dateTabs.length - 1]); // default to latest day tab
    }
  }, [dateTabs, activeDateTab]);

  const activeDayPosts = useMemo(() => {
    return postsByDate[activeDateTab] || [];
  }, [postsByDate, activeDateTab]);

  // Format 12-hour time (e.g. "7:11 PM")
  const formatTime12Hr = (timeStr: string) => {
    if (!timeStr) return '';
    try {
      const match = timeStr.match(/(\d{1,2}):(\d{2})(?::\d{2})?/);
      if (match) {
        let hour = parseInt(match[1], 10);
        const minute = match[2];
        const ampm = hour >= 12 ? 'PM' : 'AM';
        hour = hour % 12 || 12;
        return `${hour}:${minute} ${ampm}`;
      }
    } catch {
      // fallback
    }
    return timeStr;
  };

  // Calculate day totals
  const dayTotals = useMemo(() => {
    let views = 0;
    let tgClicks = 0;
    let waClicks = 0;

    activeDayPosts.forEach(p => {
      views += p.views || 0;
      tgClicks += p.telegram_clicks || p['Telegram-clicks'] || 0;
      waClicks += p.whatsapp_clicks || p['Whatsapp-clicks'] || 0;
    });

    return { views, tgClicks, waClicks };
  }, [activeDayPosts]);

  const handleRunContentReader = async () => {
    setIsLoading(true);
    setStatusMessage(null);
    const startTime = performance.now();

    try {
      const payload: Record<string, any> = {
        channel: selectedChannel,
        start_time: startDate ? `${startDate} 00:00:00` : undefined,
        end_time: endDate ? `${endDate} 23:59:59` : undefined,
        date: startDate,
      };

      if (customSheetUrl.trim()) {
        payload.sheet_url = customSheetUrl.trim();
      }

      const response = await fetch('/api/read-posts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
      setExecutionTime(parseFloat(elapsed));

      if (response.ok && data.status === 'success') {
        const fetchedPosts: ScrapedPost[] = data.posts || data.data || data.messages || [];
        setPosts(fetchedPosts);
        setIsSuccess(true);
        setStatusMessage(
          `Scraped ${fetchedPosts.length} posts across date range. Google Sheets synced into individual date subsheets (${elapsed}s)!`
        );
        onNotify(`Successfully read ${fetchedPosts.length} posts and synced daily subsheets!`);
      } else {
        setIsSuccess(false);
        setStatusMessage(data.message || data.detail || 'Failed to scrape posts from channel.');
      }
    } catch (err: any) {
      const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
      setExecutionTime(parseFloat(elapsed));
      setIsSuccess(false);
      setStatusMessage(`Scraping error: ${err.message || 'Server connection failed'}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Export to Excel with multiple subsheets (one tab per date!)
  const handleExportExcel = () => {
    if (posts.length === 0) return;

    const workbook = XLSX.utils.book_new();

    // Create a tab for each date exactly like Google Sheets
    Object.keys(postsByDate).forEach(dKey => {
      const dayList = postsByDate[dKey];
      let tViews = 0;
      let tTg = 0;
      let tWa = 0;

      const rows = dayList.map((p, idx) => {
        const tg = p.telegram_clicks || p['Telegram-clicks'] || 0;
        const wa = p.whatsapp_clicks || p['Whatsapp-clicks'] || 0;
        tViews += p.views || 0;
        tTg += tg;
        tWa += wa;

        const tgLinks = (p.links || []).filter(l => l.includes('amzaff') || l.includes('t.me') || l.includes('amazon')).join(' ');
        const waLinks = (p.links || []).filter(l => l.includes('amzaff') || l.includes('wa.me')).join(' ');

        return {
          '': '',
          'Post Number': idx + 1,
          'Time': formatTime12Hr(p.time),
          'Status': p.status || 'Live',
          'Message': p.text || 'Image post (no text or links)',
          'Telegram Links': tgLinks,
          'WhatsApp Links': waLinks,
          'Views': p.views || 0,
          'Telegram Clicks': tg,
          'WhatsApp Clicks': wa,
        };
      });

      // Append Total row
      rows.push({
        '': '',
        'Post Number': '' as any,
        'Time': '',
        'Status': '',
        'Message': '',
        'Telegram Links': '',
        'WhatsApp Links': 'Total',
        'Views': tViews,
        'Telegram Clicks': tTg,
        'WhatsApp Clicks': tWa,
      });

      const worksheet = XLSX.utils.json_to_sheet(rows);
      XLSX.utils.book_append_sheet(workbook, worksheet, dKey.slice(0, 31));
    });

    const fileName = `@${selectedChannel}_posts_${startDate}_to_${endDate}.xlsx`;
    XLSX.writeFile(workbook, fileName);
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
              <Zap className="w-5 h-5 text-emerald-400" />
              <span>Multi-Day Telegram Post Reader & Sheet Sync</span>
            </h2>
            <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-emerald-500/20 text-emerald-300 font-semibold border border-emerald-500/30">
              1 Channel = 1 Sheet with Daily Subsheets
            </span>
          </div>
          <p className="text-xs text-slate-400 max-w-2xl">
            Scrapes channel posts for any date range (e.g. Oct 1 to Oct 15) and organizes them into individual daily subsheets at the bottom of your channel Google Sheet.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleRunContentReader}
            disabled={isLoading}
            className="px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white rounded-xl text-xs font-bold flex items-center gap-2 shadow-lg shadow-emerald-600/25 cursor-pointer disabled:opacity-50 transition-all active:scale-95 shrink-0"
          >
            {isLoading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Reading & Syncing Subsheets...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Run Post Reader</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Control Configuration Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Channel Selection */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <Layers className="w-4 h-4 text-blue-400" />
            <span>Target Telegram Channel</span>
          </label>

          <select
            value={selectedChannel}
            onChange={e => setSelectedChannel(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500 cursor-pointer font-medium"
          >
            {Object.keys(CHANNELS).map(key => (
              <option key={key} value={key}>
                {CHANNELS[key].name} (@{CHANNELS[key].username})
              </option>
            ))}
          </select>
        </div>

        {/* Date Range Selection */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Calendar className="w-4 h-4 text-purple-400" />
              <span>Scrape Date Range (IST)</span>
            </label>
            <div className="flex items-center gap-1">
              {(['range', 'yesterday', 'today'] as const).map(preset => (
                <button
                  key={preset}
                  onClick={() => handlePresetChange(preset)}
                  className={`px-2 py-0.5 text-[10px] rounded font-semibold capitalize transition-all cursor-pointer ${
                    datePreset === preset
                      ? 'bg-purple-600 text-white'
                      : 'bg-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  {preset === 'range' ? '10 Days' : preset}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-[10px] text-slate-400 block mb-0.5">From Date</span>
              <input
                type="date"
                value={startDate}
                onChange={e => {
                  setStartDate(e.target.value);
                  setDatePreset('custom');
                }}
                className="w-full bg-slate-800 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-purple-500"
              />
            </div>
            <div>
              <span className="text-[10px] text-slate-400 block mb-0.5">To Date</span>
              <input
                type="date"
                value={endDate}
                onChange={e => {
                  setEndDate(e.target.value);
                  setDatePreset('custom');
                }}
                className="w-full bg-slate-800 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>
        </div>

        {/* Dynamic Channel Google Sheet Link */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <FileSpreadsheet className="w-4 h-4 text-emerald-400" />
              <span>Channel Spreadsheet Link</span>
            </span>
            <span className="text-[10px] text-emerald-400 font-normal">Dedicated Sheet</span>
          </label>

          <div className="flex items-center gap-2">
            <input
              type="text"
              value={customSheetUrl}
              onChange={e => setCustomSheetUrl(e.target.value)}
              placeholder="Google Sheet URL or ID for this channel"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white font-mono placeholder:text-slate-600 focus:outline-none focus:border-emerald-500"
            />
            {customSheetUrl && (
              <a
                href={customSheetUrl.startsWith('http') ? customSheetUrl : `https://docs.google.com/spreadsheets/d/${customSheetUrl}`}
                target="_blank"
                rel="noreferrer"
                className="p-2 bg-slate-800 hover:bg-slate-700 text-emerald-400 rounded-lg shrink-0 border border-slate-700"
                title="Open Google Sheet in new tab"
              >
                <ExternalLink className="w-4 h-4" />
              </a>
            )}
          </div>
          <p className="text-[10px] text-slate-400">
            One Google Sheet link per channel. Each day in the range becomes a separate subsheet tab!
          </p>
        </div>
      </div>

      {/* Execution Status Message */}
      {statusMessage && (
        <div
          className={`p-4 rounded-xl border flex items-start sm:items-center justify-between gap-3 ${
            isSuccess
              ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-200'
              : 'bg-amber-950/30 border-amber-500/40 text-amber-200'
          }`}
        >
          <div className="flex items-center gap-2.5">
            {isSuccess ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 text-amber-400 shrink-0" />
            )}
            <div>
              <p className="text-xs font-semibold">{statusMessage}</p>
              {executionTime !== null && (
                <p className="text-[11px] opacity-80 font-mono">
                  Finished in {executionTime}s. Subsheets created: {dateTabs.join(', ')}
                </p>
              )}
            </div>
          </div>

          {posts.length > 0 && (
            <button
              onClick={handleExportExcel}
              className="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 cursor-pointer shadow-sm shrink-0"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export Multi-Tab .xlsx</span>
            </button>
          )}
        </div>
      )}

      {/* Google Sheets Simulation Container (Matches Screenshot EXACTLY!) */}
      {posts.length > 0 ? (
        <div className="bg-slate-900 border border-slate-700 rounded-xl overflow-hidden shadow-xl">
          {/* Top Title Bar (Green Sheets Logo + Channel Title) */}
          <div className="bg-slate-950 px-4 py-2.5 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-6 h-6 rounded bg-emerald-600 flex items-center justify-center text-white font-bold text-xs shadow-sm">
                <FileSpreadsheet className="w-4 h-4" />
              </div>
              <span className="text-sm font-bold text-white tracking-wide">
                @{selectedChannel}
              </span>
              <span className="text-xs text-slate-400 font-mono">
                ({posts.length} total posts across {dateTabs.length} daily subsheets)
              </span>
            </div>

            <div className="flex items-center gap-3">
              {customSheetUrl && (
                <a
                  href={customSheetUrl.startsWith('http') ? customSheetUrl : `https://docs.google.com/spreadsheets/d/${customSheetUrl}`}
                  target="_blank"
                  rel="noreferrer"
                  className="px-3 py-1 bg-emerald-950/60 hover:bg-emerald-900/60 border border-emerald-500/40 text-emerald-300 rounded text-xs font-semibold flex items-center gap-1.5"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  <span>Open in Google Sheets</span>
                </a>
              )}
              <button
                onClick={handleExportExcel}
                className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded text-xs font-semibold flex items-center gap-1"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Export Excel</span>
              </button>
            </div>
          </div>

          {/* Subsheet Table Content */}
          <div className="overflow-x-auto max-h-[520px] bg-white text-slate-900">
            <table className="w-full text-left text-xs border-collapse">
              <thead className="bg-slate-100 text-slate-700 font-semibold border-b border-slate-300 sticky top-0 z-10 select-none">
                <tr className="h-9">
                  <th className="w-8 border-r border-slate-200 px-2 text-center text-slate-400 font-mono text-[10px]">A</th>
                  <th className="border-r border-slate-200 px-3 font-semibold text-slate-800">Post Number</th>
                  <th className="border-r border-slate-200 px-3 font-semibold text-slate-800">Time</th>
                  <th className="border-r border-slate-200 px-3 font-semibold text-slate-800">Status</th>
                  <th className="border-r border-slate-200 px-3 font-semibold text-slate-800 min-w-[280px]">Message</th>
                  <th className="border-r border-slate-200 px-3 font-semibold text-slate-800">Telegram Links</th>
                  <th className="border-r border-slate-200 px-3 font-semibold text-slate-800">WhatsApp Links</th>
                  <th className="border-r border-slate-200 px-3 text-right font-semibold text-slate-800">Views</th>
                  <th className="border-r border-slate-200 px-3 text-right font-semibold text-slate-800">Telegram Clicks</th>
                  <th className="px-3 text-right font-semibold text-slate-800">WhatsApp Clicks</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 text-[11px] font-sans">
                {activeDayPosts.map((p, idx) => {
                  const tg = p.telegram_clicks || p['Telegram-clicks'] || 0;
                  const wa = p.whatsapp_clicks || p['Whatsapp-clicks'] || 0;
                  const tgLinks = (p.links || []).filter(l => l.includes('amzaff') || l.includes('t.me') || l.includes('amazon')).join(' ');
                  const waLinks = (p.links || []).filter(l => l.includes('amzaff') || l.includes('wa.me')).join(' ');

                  return (
                    <tr key={idx} className="hover:bg-slate-50 transition-colors">
                      <td className="w-8 border-r border-slate-200 text-center text-slate-400 font-mono text-[10px] bg-slate-50">
                        {idx + 2}
                      </td>
                      <td className="border-r border-slate-200 px-3 py-1.5 font-bold text-slate-800 font-mono">
                        {idx + 1}
                      </td>
                      <td className="border-r border-slate-200 px-3 py-1.5 whitespace-nowrap text-slate-700 font-mono">
                        {formatTime12Hr(p.time)}
                      </td>
                      <td className="border-r border-slate-200 px-3 py-1.5">
                        <span className="font-semibold text-slate-800">
                          {p.status || 'Live'}
                        </span>
                      </td>
                      <td className="border-r border-slate-200 px-3 py-1.5 max-w-sm truncate text-slate-800" title={p.text}>
                        {p.text || 'Image post (no text or links)'}
                      </td>
                      <td className="border-r border-slate-200 px-3 py-1.5 max-w-xs truncate text-blue-700 font-mono">
                        {tgLinks || '-'}
                      </td>
                      <td className="border-r border-slate-200 px-3 py-1.5 max-w-xs truncate text-emerald-700 font-mono">
                        {waLinks || '-'}
                      </td>
                      <td className="border-r border-slate-200 px-3 py-1.5 text-right font-semibold text-slate-800 font-mono">
                        {p.views || 0}
                      </td>
                      <td className="border-r border-slate-200 px-3 py-1.5 text-right font-semibold text-slate-800 font-mono">
                        {tg}
                      </td>
                      <td className="px-3 py-1.5 text-right font-semibold text-slate-800 font-mono">
                        {wa}
                      </td>
                    </tr>
                  );
                })}

                {/* Bottom Total Row (Green Highlighted Exactly like Screenshot!) */}
                <tr className="bg-[#b6d7a8] text-slate-900 font-bold border-t-2 border-slate-400 h-8">
                  <td className="w-8 border-r border-slate-300 text-center text-slate-500 font-mono text-[10px] bg-slate-100">
                    {activeDayPosts.length + 2}
                  </td>
                  <td className="border-r border-slate-300 px-3"></td>
                  <td className="border-r border-slate-300 px-3"></td>
                  <td className="border-r border-slate-300 px-3"></td>
                  <td className="border-r border-slate-300 px-3"></td>
                  <td className="border-r border-slate-300 px-3"></td>
                  <td className="border-r border-slate-300 px-3 font-extrabold text-right">Total</td>
                  <td className="border-r border-slate-300 px-3 text-right font-mono font-extrabold text-black">
                    {dayTotals.views.toLocaleString()}
                  </td>
                  <td className="border-r border-slate-300 px-3 text-right font-mono font-extrabold text-black">
                    {dayTotals.tgClicks.toLocaleString()}
                  </td>
                  <td className="px-3 text-right font-mono font-extrabold text-black">
                    {dayTotals.waClicks.toLocaleString()}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Bottom Google Sheets Subsheet Tabs Bar (Matches Screenshot Exactly!) */}
          <div className="bg-slate-200 border-t border-slate-300 px-3 py-1.5 flex items-center overflow-x-auto gap-1 scrollbar-none select-none">
            <div className="flex items-center gap-1.5 pr-2 border-r border-slate-300 text-slate-600">
              <Plus className="w-4 h-4 cursor-pointer hover:text-slate-900" />
              <Layers className="w-4 h-4 cursor-pointer hover:text-slate-900" />
            </div>

            {/* Scheduled Posts Tab */}
            <button
              onClick={() => setActiveDateTab('Scheduled Posts')}
              className={`px-3 py-1 text-xs font-semibold rounded-t flex items-center gap-1.5 transition-all cursor-pointer whitespace-nowrap border-b-2 ${
                activeDateTab === 'Scheduled Posts'
                  ? 'bg-white text-emerald-800 border-emerald-600 shadow-sm'
                  : 'text-slate-600 hover:bg-slate-300/70 border-transparent'
              }`}
            >
              <span>17 May 2026 - Scheduled Posts</span>
            </button>

            {/* Individual Daily Subsheet Tabs */}
            {dateTabs.map(tabName => (
              <button
                key={tabName}
                onClick={() => setActiveDateTab(tabName)}
                className={`px-3.5 py-1 text-xs font-semibold rounded-t flex items-center gap-1.5 transition-all cursor-pointer whitespace-nowrap border-b-2 ${
                  activeDateTab === tabName
                    ? 'bg-white text-emerald-800 border-emerald-600 shadow-sm'
                    : 'text-slate-700 hover:bg-slate-300/70 border-transparent'
                }`}
              >
                <span>{tabName}</span>
                <span className="text-[10px] text-slate-400 font-mono font-normal">
                  ({postsByDate[tabName]?.length || 0})
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-10 text-center space-y-3">
          <Clock className="w-10 h-10 text-slate-600 mx-auto" />
          <h3 className="text-sm font-semibold text-slate-300">Ready to Read Posts</h3>
          <p className="text-xs text-slate-500 max-w-lg mx-auto">
            Choose your target channel and date range (e.g., Oct 1 to Oct 15) and click &ldquo;Run Post Reader&rdquo;. It will fetch the posts and organize them into individual daily subsheets at the bottom of the channel Google Sheet.
          </p>
        </div>
      )}
    </div>
  );
};
