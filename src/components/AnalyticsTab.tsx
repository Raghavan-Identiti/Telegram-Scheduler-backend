import React, { useState } from 'react';
import {
  BarChart3,
  Calendar,
  Layers,
  Download,
  Eye,
  MousePointerClick,
  Share2,
  ExternalLink,
  Search,
  Filter,
} from 'lucide-react';
import { CHANNELS } from '../services/channels';
import { exportPostsToExcel, getClickDataForLinks } from '../services/analytics';
import { StorageService } from '../services/storage';
import { ScheduledPostRecord } from '../types';

interface AnalyticsTabProps {
  onNotify: (msg: string) => void;
}

export const AnalyticsTab: React.FC<AnalyticsTabProps> = ({ onNotify }) => {
  const todayStr = new Date().toISOString().split('T')[0];

  const [mode, setMode] = useState<'single' | 'range'>('single');
  const [selectedDate, setSelectedDate] = useState<string>(todayStr);
  const [startDate, setStartDate] = useState<string>(() => {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    return d.toISOString().split('T')[0];
  });
  const [endDate, setEndDate] = useState<string>(todayStr);
  const [channelFilter, setChannelFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const allPosts = StorageService.getScheduledPosts();

  // Filter posts based on date criteria and channel
  const filteredPosts = allPosts.filter(post => {
    if (channelFilter !== 'all' && post.channel !== channelFilter) {
      return false;
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchText = post.text.toLowerCase().includes(q);
      const matchPostNum = post.postNumber.toString().includes(q);
      const matchCategory = post.category?.toLowerCase().includes(q);
      if (!matchText && !matchPostNum && !matchCategory) {
        return false;
      }
    }

    const postDate = post.fullDateTime ? post.fullDateTime.split('T')[0] : '';
    if (mode === 'single') {
      return postDate === selectedDate || !postDate;
    } else {
      return postDate >= startDate && postDate <= endDate;
    }
  });

  // Calculate Metrics
  const totalPosts = filteredPosts.length;
  const liveCount = filteredPosts.filter(p => p.status === 'live' || p.views && p.views > 0).length;
  const scheduledCount = filteredPosts.filter(p => p.status === 'scheduled').length;
  const totalViews = filteredPosts.reduce((acc, p) => acc + (p.views || 0), 0);
  const totalTgClicks = filteredPosts.reduce((acc, p) => acc + (p.telegramClicks || 0), 0);
  const totalWaClicks = filteredPosts.reduce((acc, p) => acc + (p.whatsappClicks || 0), 0);

  // Per Channel Breakdown
  const channelBreakdown = Object.values(CHANNELS).map(chan => {
    const postsForChan = filteredPosts.filter(p => p.channel === chan.id);
    const live = postsForChan.filter(p => p.status === 'live' || p.views && p.views > 0).length;
    const sched = postsForChan.filter(p => p.status === 'scheduled').length;
    const clicks = postsForChan.reduce(
      (acc, p) => acc + (p.telegramClicks || 0) + (p.whatsappClicks || 0),
      0
    );
    return {
      channel: chan,
      total: postsForChan.length,
      live,
      scheduled: sched,
      clicks,
    };
  });

  // Export to Excel
  const handleExportExcel = () => {
    if (filteredPosts.length === 0) {
      alert('No posts to export in the selected filter.');
      return;
    }
    exportPostsToExcel(filteredPosts, `TeleQueue_Posts_${selectedDate}.xlsx`);
    onNotify('Exported posts to Excel spreadsheet.');
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-gradient-to-r from-blue-900/30 via-slate-900/60 to-slate-900 border border-blue-500/30 rounded-2xl p-5 shadow-sm">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30 flex items-center justify-center font-bold">
              <BarChart3 className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white">Post Analytics & Clicks Tracker</h2>
                <span className="px-2 py-0.5 text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30 rounded-full">
                  Quic.ly & Telethon Metrics
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Monitor post impressions, link click conversions across Telegram & WhatsApp channels, and export reports.
              </p>
            </div>
          </div>

          <button
            onClick={handleExportExcel}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold shadow-sm flex items-center gap-2 cursor-pointer transition-all"
          >
            <Download className="w-4 h-4" />
            <span>Export to Excel (.xlsx)</span>
          </button>
        </div>
      </div>

      {/* Date Filter & Search Controls */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Mode Tabs: Single Date vs Date Range */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setMode('single')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                mode === 'single'
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
            >
              Single Date
            </button>
            <button
              onClick={() => setMode('range')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                mode === 'range'
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
            >
              Date Range (up to 31 days)
            </button>
          </div>

          {/* Date Picker inputs */}
          <div className="flex items-center gap-2">
            {mode === 'single' ? (
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-slate-400">Date:</span>
                <input
                  type="date"
                  value={selectedDate}
                  onChange={e => setSelectedDate(e.target.value)}
                  className="bg-slate-800 border border-slate-700 text-xs text-white rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-blue-500"
                />
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-slate-400">From:</span>
                  <input
                    type="date"
                    value={startDate}
                    onChange={e => setStartDate(e.target.value)}
                    className="bg-slate-800 border border-slate-700 text-xs text-white rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-slate-400">To:</span>
                  <input
                    type="date"
                    value={endDate}
                    onChange={e => setEndDate(e.target.value)}
                    className="bg-slate-800 border border-slate-700 text-xs text-white rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>
            )}

            {/* Channel Filter */}
            <select
              value={channelFilter}
              onChange={e => setChannelFilter(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-xs text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-blue-500"
            >
              <option value="all">All Telegram Channels</option>
              {Object.values(CHANNELS).map(c => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Search bar */}
        <div className="relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search posts by text, deal keyword, or amzaff link..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5 space-y-1">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            Total Posts
          </span>
          <p className="text-xl font-bold text-white font-mono">{totalPosts}</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5 space-y-1">
          <span className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider">
            Live Posts
          </span>
          <p className="text-xl font-bold text-emerald-400 font-mono">{liveCount}</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5 space-y-1">
          <span className="text-[11px] font-semibold text-blue-400 uppercase tracking-wider">
            Scheduled
          </span>
          <p className="text-xl font-bold text-blue-400 font-mono">{scheduledCount}</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5 space-y-1">
          <span className="text-[11px] font-semibold text-purple-400 uppercase tracking-wider">
            Views
          </span>
          <p className="text-xl font-bold text-purple-300 font-mono">{totalViews.toLocaleString()}</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5 space-y-1">
          <span className="text-[11px] font-semibold text-cyan-400 uppercase tracking-wider">
            Telegram Clicks
          </span>
          <p className="text-xl font-bold text-cyan-400 font-mono">{totalTgClicks.toLocaleString()}</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5 space-y-1">
          <span className="text-[11px] font-semibold text-green-400 uppercase tracking-wider">
            WhatsApp Clicks
          </span>
          <p className="text-xl font-bold text-green-400 font-mono">{totalWaClicks.toLocaleString()}</p>
        </div>
      </div>

      {/* Channel Breakdown Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
        <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
          Channel Activity Breakdown
        </span>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 font-medium">
                <th className="pb-2">Channel Name</th>
                <th className="pb-2">Username</th>
                <th className="pb-2 text-right">Live Posts</th>
                <th className="pb-2 text-right">Scheduled</th>
                <th className="pb-2 text-right">Total Posts</th>
                <th className="pb-2 text-right">Clicks</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {channelBreakdown.map(b => (
                <tr key={b.channel.id} className="hover:bg-slate-800/40">
                  <td className="py-2.5 font-medium text-slate-200">{b.channel.name}</td>
                  <td className="py-2.5 font-mono text-slate-400">@{b.channel.username}</td>
                  <td className="py-2.5 text-right font-mono text-emerald-400">{b.live}</td>
                  <td className="py-2.5 text-right font-mono text-blue-400">{b.scheduled}</td>
                  <td className="py-2.5 text-right font-mono font-bold text-slate-200">{b.total}</td>
                  <td className="py-2.5 text-right font-mono text-cyan-400 font-semibold">{b.clicks}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Posts Detail List */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
            Posts Log ({filteredPosts.length})
          </span>
        </div>

        {filteredPosts.length === 0 ? (
          <p className="text-xs text-slate-500 py-6 text-center">No posts match the current filter.</p>
        ) : (
          <div className="space-y-2">
            {filteredPosts.map(post => (
              <div
                key={post.id}
                className="p-3 bg-slate-800/40 border border-slate-800 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-blue-400">#{post.postNumber}</span>
                    <span className="font-medium text-white">@{post.channelUsername}</span>
                    {post.category && (
                      <span className="text-[10px] bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded border border-slate-700">
                        {post.category}
                      </span>
                    )}
                    <span className="text-slate-500 font-mono text-[11px]">{post.time} IST</span>
                  </div>
                  <p className="text-slate-300 line-clamp-1 max-w-xl">{post.text}</p>
                </div>

                {/* Right side stats */}
                <div className="flex items-center gap-4 text-xs shrink-0">
                  <div className="flex items-center gap-1 text-slate-400" title="Views">
                    <Eye className="w-3.5 h-3.5 text-purple-400" />
                    <span className="font-mono">{post.views || 0}</span>
                  </div>
                  <div className="flex items-center gap-1 text-cyan-400" title="Telegram Clicks">
                    <MousePointerClick className="w-3.5 h-3.5" />
                    <span className="font-mono">{post.telegramClicks || 0} TG</span>
                  </div>
                  <div className="flex items-center gap-1 text-green-400" title="WhatsApp Clicks">
                    <Share2 className="w-3.5 h-3.5" />
                    <span className="font-mono">{post.whatsappClicks || 0} WA</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
