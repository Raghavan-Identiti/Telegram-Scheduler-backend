import React, { useState, useEffect, useMemo } from 'react';
import {
  format,
  addMonths,
  subMonths,
  startOfWeek,
  endOfWeek,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  isSameMonth,
  isSameDay,
  isToday,
  addDays,
  subDays,
  addWeeks,
  subWeeks,
} from 'date-fns';
import {
  Calendar as CalendarIcon,
  ChevronLeft,
  ChevronRight,
  Clock,
  Send,
  Eye,
  ExternalLink,
  Plus,
  RefreshCw,
  Filter,
  CheckCircle2,
  AlertCircle,
  X,
  FileText,
  Image as ImageIcon,
  Trash2,
} from 'lucide-react';
import { authenticatedFetch } from '../services/apiClient';
import { CHANNELS } from '../services/channels';

export interface CalendarEvent {
  id: string;
  post_number?: string | number;
  title: string;
  channel: string;
  channel_name?: string;
  channel_type?: string;
  text: string;
  category?: string;
  start: string;
  end?: string;
  date: string;
  time: string;
  status: 'scheduled' | 'booked' | 'live' | 'failed';
  image_name?: string;
  image_url?: string;
  links?: string[];
  views?: number;
  telegram_clicks?: number;
  whatsapp_clicks?: number;
  source?: string;
}

interface ScheduleCalendarTabProps {
  onNotify?: (msg: string) => void;
}

export const ScheduleCalendarTab: React.FC<ScheduleCalendarTabProps> = ({ onNotify }) => {
  const [currentDate, setCurrentDate] = useState<Date>(new Date(2026, 8, 15)); // Default to Sept 2026 as in user's view
  const [viewMode, setViewMode] = useState<'month' | 'week' | 'day'>('month');
  const [selectedChannel, setSelectedChannel] = useState<string>('all');
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState<boolean>(false);
  const [newPostChannel, setNewPostChannel] = useState<string>('amazonindiaassociates');
  const [newPostDate, setNewPostDate] = useState<string>(format(new Date(2026, 8, 15), 'yyyy-MM-dd'));
  const [newPostTime, setNewPostTime] = useState<string>('14:30');
  const [newPostText, setNewPostText] = useState<string>('');
  const [newPostCategory, setNewPostCategory] = useState<string>('Deals');

  const channelColors: Record<string, { bg: string; text: string; border: string; dot: string }> = {
    amazonindiaassociates: {
      bg: 'bg-blue-500/10',
      text: 'text-blue-400',
      border: 'border-blue-500/30',
      dot: 'bg-blue-500',
    },
    Amazon_Associates_FashionBeauty: {
      bg: 'bg-pink-500/10',
      text: 'text-pink-400',
      border: 'border-pink-500/30',
      dot: 'bg-pink-500',
    },
    Amazon_Associates_HomeKitchen: {
      bg: 'bg-amber-500/10',
      text: 'text-amber-400',
      border: 'border-amber-500/30',
      dot: 'bg-amber-500',
    },
    Amazon_Associates_Consumables: {
      bg: 'bg-emerald-500/10',
      text: 'text-emerald-400',
      border: 'border-emerald-500/30',
      dot: 'bg-emerald-500',
    },
    amazoninfluencerprogramindia: {
      bg: 'bg-purple-500/10',
      text: 'text-purple-400',
      border: 'border-purple-500/30',
      dot: 'bg-purple-500',
    },
  };

  const getChannelColor = (ch: string) => {
    return channelColors[ch] || {
      bg: 'bg-indigo-500/10',
      text: 'text-indigo-400',
      border: 'border-indigo-500/30',
      dot: 'bg-indigo-500',
    };
  };

  // Fetch calendar events from backend
  const fetchEvents = async () => {
    setIsLoading(true);
    try {
      const year = currentDate.getFullYear();
      const month = currentDate.getMonth() + 1;
      let url = `/api/calendar/events?year=${year}&month=${month}`;
      if (selectedChannel !== 'all') {
        url += `&channel=${selectedChannel}`;
      }

      const res = await authenticatedFetch(url);
      if (res.ok) {
        const data = await res.json();
        const eventList: CalendarEvent[] = Array.isArray(data)
          ? data
          : data.events || data.data || [];
        setEvents(eventList);
      } else {
        // Fallback to /api/calendar-slots if /api/calendar/events is not reachable
        const fallbackRes = await authenticatedFetch('/api/calendar-slots');
        if (fallbackRes.ok) {
          const slotsData = await fallbackRes.json();
          if (Array.isArray(slotsData)) {
            const mapped = slotsData.map((s, idx) => ({
              id: `slot_${idx}`,
              title: s.title || `Scheduled Post #${s.post || idx + 1}`,
              channel: s.channel || 'amazonindiaassociates',
              text: s.text || '',
              start: s.time,
              date: s.time ? s.time.split('T')[0] : format(currentDate, 'yyyy-MM-dd'),
              time: s.time ? s.time.split('T')[1]?.substring(0, 5) || '12:00' : '12:00',
              status: 'scheduled' as const,
            }));
            setEvents(mapped);
          }
        }
      }
    } catch (err) {
      console.warn('Notice: Error fetching calendar events:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, [currentDate, selectedChannel]);

  // Navigation handlers
  const handleToday = () => {
    // Navigate to today or default demo month
    setCurrentDate(new Date(2026, 8, 15));
  };

  const handlePrev = () => {
    if (viewMode === 'month') {
      setCurrentDate(prev => subMonths(prev, 1));
    } else if (viewMode === 'week') {
      setCurrentDate(prev => subWeeks(prev, 1));
    } else {
      setCurrentDate(prev => subDays(prev, 1));
    }
  };

  const handleNext = () => {
    if (viewMode === 'month') {
      setCurrentDate(prev => addMonths(prev, 1));
    } else if (viewMode === 'week') {
      setCurrentDate(prev => addWeeks(prev, 1));
    } else {
      setCurrentDate(prev => addDays(prev, 1));
    }
  };

  // Month grid calculations
  const monthStart = startOfMonth(currentDate);
  const monthEnd = endOfMonth(monthStart);
  const calendarStart = startOfWeek(monthStart, { weekStartsOn: 1 }); // Monday start like screenshot
  const calendarEnd = endOfWeek(monthEnd, { weekStartsOn: 1 });

  const daysGrid = useMemo(() => {
    return eachDayOfInterval({ start: calendarStart, end: calendarEnd });
  }, [calendarStart, calendarEnd]);

  // Map events to dates for fast cell lookup
  const eventsByDate = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {};
    events.forEach(ev => {
      const dStr = ev.date || (ev.start ? ev.start.split('T')[0] : '');
      if (dStr) {
        if (!map[dStr]) map[dStr] = [];
        map[dStr].push(ev);
      }
    });
    return map;
  }, [events]);

  // Handle scheduling a quick post from the calendar
  const handleCreatePost = async () => {
    if (!newPostText.trim()) {
      alert('Please enter post text');
      return;
    }
    const fullTimeIso = `${newPostDate}T${newPostTime}:00+05:30`;
    const payload = {
      id: `post_cal_${Date.now()}`,
      channel: newPostChannel,
      channel_name: CHANNELS[newPostChannel]?.sheetName || newPostChannel,
      title: `Post: ${newPostCategory} @ ${newPostTime}`,
      text: newPostText,
      category: newPostCategory,
      scheduled_time: fullTimeIso,
      date: newPostDate,
      time: newPostTime,
      status: 'scheduled',
      source: 'calendar_ui',
    };

    try {
      const res = await authenticatedFetch('/api/calendar/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        onNotify?.('✅ Scheduled post added to calendar successfully!');
        setIsScheduleModalOpen(false);
        setNewPostText('');
        fetchEvents();
      } else {
        alert('Failed to schedule post');
      }
    } catch (e) {
      alert('Error saving event: ' + e);
    }
  };

  // Handle post deletion
  const handleDeletePost = async (eventId: string) => {
    if (!confirm('Are you sure you want to remove this scheduled post from the calendar?')) return;
    try {
      const res = await authenticatedFetch(`/api/calendar/events/${eventId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        onNotify?.('🗑️ Post removed from calendar queue');
        setSelectedEvent(null);
        fetchEvents();
      }
    } catch (err) {
      alert('Failed to delete event: ' + err);
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Title & Breadcrumb header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
            <span>QPilot</span>
            <span>&gt;</span>
            <span>Overview</span>
            <span>&gt;</span>
            <span className="text-blue-400 font-medium">Schedule Calendar</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <CalendarIcon className="w-6 h-6 text-blue-400" />
            Schedule Calendar
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            View, inspect, and organize scheduled posts across all marketing channels
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => fetchEvents()}
            disabled={isLoading}
            className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium border border-slate-700 flex items-center gap-1.5 transition"
            title="Refresh Calendar"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={() => setIsScheduleModalOpen(true)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold shadow-md shadow-blue-500/20 flex items-center gap-1.5 transition"
          >
            <Plus className="w-4 h-4" />
            + Schedule Post
          </button>
        </div>
      </div>

      {/* Main Calendar Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
        {/* Calendar Top Toolbar */}
        <div className="p-4 sm:p-5 border-b border-slate-800/80 flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-slate-900/60">
          {/* Navigation Controls: Today, Back, Next */}
          <div className="flex items-center gap-2">
            <div className="inline-flex rounded-lg border border-slate-700 p-0.5 bg-slate-800/60">
              <button
                onClick={handleToday}
                className="px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-700 rounded-md transition"
              >
                Today
              </button>
              <button
                onClick={handlePrev}
                className="px-2.5 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700 rounded-md transition flex items-center gap-1"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                Back
              </button>
              <button
                onClick={handleNext}
                className="px-2.5 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700 rounded-md transition flex items-center gap-1"
              >
                Next
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Current Month & Year Display */}
            <div className="text-base sm:text-lg font-bold text-white px-2">
              {format(currentDate, 'MMMM yyyy')}
            </div>
          </div>

          {/* Right Controls: Filter & View Switcher */}
          <div className="flex items-center flex-wrap gap-3">
            {/* Channel Filter */}
            <div className="flex items-center gap-1.5 bg-slate-800 border border-slate-700 px-2.5 py-1.5 rounded-lg text-xs">
              <Filter className="w-3.5 h-3.5 text-slate-400" />
              <select
                value={selectedChannel}
                onChange={e => setSelectedChannel(e.target.value)}
                className="bg-transparent text-slate-200 text-xs focus:outline-none cursor-pointer"
              >
                <option value="all" className="bg-slate-900">All Channels</option>
                {Object.entries(CHANNELS).map(([k, v]) => (
                  <option key={k} value={k} className="bg-slate-900">
                    {v.sheetName || v.username}
                  </option>
                ))}
              </select>
            </div>

            {/* View Switcher: Month, Week, Day */}
            <div className="inline-flex rounded-lg border border-slate-700 p-0.5 bg-slate-800/60 text-xs">
              {(['month', 'week', 'day'] as const).map(mode => (
                <button
                  key={mode}
                  onClick={() => setViewMode(mode)}
                  className={`px-3 py-1.5 rounded-md font-medium capitalize transition ${
                    viewMode === mode
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
                  }`}
                >
                  {mode}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Calendar Body: Month View */}
        {viewMode === 'month' && (
          <div className="overflow-x-auto">
            <div className="min-w-[750px]">
              {/* Day of Week Headers */}
              <div className="grid grid-cols-7 border-b border-slate-800 bg-slate-950/60 text-center text-xs font-bold text-slate-400 py-3 uppercase tracking-wider">
                <div>Mon</div>
                <div>Tue</div>
                <div>Wed</div>
                <div>Thu</div>
                <div>Fri</div>
                <div>Sat</div>
                <div>Sun</div>
              </div>

              {/* Day Cells Grid */}
              <div className="grid grid-cols-7 border-l border-t border-slate-800/80 bg-slate-950/30">
                {daysGrid.map((day, idx) => {
                  const dateKey = format(day, 'yyyy-MM-dd');
                  const dayEvents = eventsByDate[dateKey] || [];
                  const isCurrentMonth = isSameMonth(day, currentDate);
                  const isTodayDate = isToday(day);

                  return (
                    <div
                      key={idx}
                      className={`min-h-[110px] p-2 border-r border-b border-slate-800/80 flex flex-col justify-between transition group hover:bg-slate-800/20 ${
                        !isCurrentMonth ? 'bg-slate-950/70 text-slate-600' : 'text-slate-200'
                      } ${isTodayDate ? 'ring-1 ring-inset ring-blue-500/60 bg-blue-950/10' : ''}`}
                    >
                      {/* Cell Header: Date Number */}
                      <div className="flex items-center justify-between mb-1.5">
                        <span
                          className={`text-xs font-semibold px-1.5 py-0.5 rounded-full ${
                            isTodayDate
                              ? 'bg-blue-600 text-white font-bold'
                              : isCurrentMonth
                              ? 'text-slate-300'
                              : 'text-slate-600'
                          }`}
                        >
                          {format(day, 'dd')}
                        </span>
                        {dayEvents.length > 0 && (
                          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-400 border border-slate-700/60">
                            {dayEvents.length} post{dayEvents.length > 1 ? 's' : ''}
                          </span>
                        )}
                      </div>

                      {/* Scheduled Posts in this day */}
                      <div className="space-y-1 flex-1 overflow-y-auto max-h-[85px] pr-0.5 scrollbar-thin">
                        {dayEvents.map(ev => {
                          const col = getChannelColor(ev.channel);
                          return (
                            <button
                              key={ev.id}
                              onClick={() => setSelectedEvent(ev)}
                              className={`w-full text-left px-2 py-1 rounded text-[11px] font-medium border truncate transition flex items-center gap-1.5 ${col.bg} ${col.text} ${col.border} hover:brightness-110 shadow-xs`}
                              title={`${ev.time} - ${ev.title}`}
                            >
                              <span className={`w-1.5 h-1.5 rounded-full ${col.dot} shrink-0`}></span>
                              <span className="font-mono text-[10px] opacity-80 shrink-0">{ev.time}</span>
                              <span className="truncate">{ev.title}</span>
                            </button>
                          );
                        })}
                      </div>

                      {/* Quick Add Button on Hover */}
                      <div className="opacity-0 group-hover:opacity-100 transition mt-1 pt-1 border-t border-slate-800/40 flex justify-end">
                        <button
                          onClick={() => {
                            setNewPostDate(dateKey);
                            setIsScheduleModalOpen(true);
                          }}
                          className="text-[10px] text-slate-400 hover:text-blue-400 flex items-center gap-0.5"
                        >
                          <Plus className="w-3 h-3" /> Add post
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Calendar Body: Week View */}
        {viewMode === 'week' && (
          <div className="p-4 sm:p-6 space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-7 gap-3">
              {eachDayOfInterval({
                start: startOfWeek(currentDate, { weekStartsOn: 1 }),
                end: endOfWeek(currentDate, { weekStartsOn: 1 }),
              }).map((day, idx) => {
                const dateKey = format(day, 'yyyy-MM-dd');
                const dayEvents = eventsByDate[dateKey] || [];
                const isTodayDate = isToday(day);

                return (
                  <div
                    key={idx}
                    className={`bg-slate-950/60 border rounded-xl p-3 flex flex-col min-h-[350px] ${
                      isTodayDate ? 'border-blue-500/50 bg-blue-950/10' : 'border-slate-800'
                    }`}
                  >
                    <div className="pb-2 border-b border-slate-800/80 mb-2.5 flex items-center justify-between">
                      <div>
                        <div className="text-[11px] uppercase font-bold text-slate-400">
                          {format(day, 'EEE')}
                        </div>
                        <div className="text-lg font-bold text-white">
                          {format(day, 'dd MMM')}
                        </div>
                      </div>
                      {isTodayDate && (
                        <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30 font-bold">
                          Today
                        </span>
                      )}
                    </div>

                    <div className="space-y-2 flex-1 overflow-y-auto">
                      {dayEvents.length === 0 ? (
                        <p className="text-xs text-slate-600 text-center py-8">No scheduled posts</p>
                      ) : (
                        dayEvents.map(ev => {
                          const col = getChannelColor(ev.channel);
                          return (
                            <div
                              key={ev.id}
                              onClick={() => setSelectedEvent(ev)}
                              className={`p-2.5 rounded-lg border cursor-pointer transition hover:scale-[1.02] ${col.bg} ${col.border}`}
                            >
                              <div className="flex items-center justify-between text-[10px] mb-1">
                                <span className={`font-mono font-bold ${col.text}`}>{ev.time} IST</span>
                                <span className="text-slate-400">{ev.category || 'Post'}</span>
                              </div>
                              <p className="text-xs font-medium text-slate-200 line-clamp-2">
                                {ev.title}
                              </p>
                              {ev.text && (
                                <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">
                                  {ev.text}
                                </p>
                              )}
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Calendar Body: Day View */}
        {viewMode === 'day' && (
          <div className="p-4 sm:p-6 max-w-4xl mx-auto">
            <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-5 mb-5 flex items-center justify-between">
              <div>
                <span className="text-xs text-blue-400 uppercase font-bold tracking-wider">
                  Day Schedule Detail
                </span>
                <h3 className="text-xl font-bold text-white mt-0.5">
                  {format(currentDate, 'EEEE, MMMM dd, yyyy')}
                </h3>
              </div>
              <div className="text-xs text-slate-400 font-mono">
                {eventsByDate[format(currentDate, 'yyyy-MM-dd')]?.length || 0} Posts Scheduled
              </div>
            </div>

            {/* Timeline slots for selected day */}
            <div className="space-y-2.5">
              {(eventsByDate[format(currentDate, 'yyyy-MM-dd')] || []).length === 0 ? (
                <div className="bg-slate-950/40 border border-slate-800/80 rounded-xl p-10 text-center">
                  <CalendarIcon className="w-10 h-10 text-slate-600 mx-auto mb-2 opacity-50" />
                  <p className="text-sm text-slate-400">No posts queued for this day.</p>
                  <button
                    onClick={() => {
                      setNewPostDate(format(currentDate, 'yyyy-MM-dd'));
                      setIsScheduleModalOpen(true);
                    }}
                    className="mt-3 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold inline-flex items-center gap-1.5"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Schedule a post now
                  </button>
                </div>
              ) : (
                (eventsByDate[format(currentDate, 'yyyy-MM-dd')] || []).map(ev => {
                  const col = getChannelColor(ev.channel);
                  return (
                    <div
                      key={ev.id}
                      onClick={() => setSelectedEvent(ev)}
                      className={`p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-4 cursor-pointer hover:bg-slate-800/40 transition ${col.bg} ${col.border}`}
                    >
                      <div className="flex items-start gap-3">
                        <div className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700/80 text-center shrink-0">
                          <span className="block text-xs font-bold text-white font-mono">{ev.time}</span>
                          <span className="text-[9px] text-slate-400 uppercase">IST</span>
                        </div>
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span className={`text-xs font-semibold ${col.text}`}>
                              {ev.channel_name || ev.channel}
                            </span>
                            <span className="text-slate-600">•</span>
                            <span className="text-xs text-slate-400">{ev.category || 'Deals'}</span>
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                              Scheduled
                            </span>
                          </div>
                          <h4 className="text-sm font-semibold text-white">{ev.title}</h4>
                          <p className="text-xs text-slate-400 mt-1 line-clamp-2 max-w-2xl">
                            {ev.text}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 self-end sm:self-center">
                        <button className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs border border-slate-700 flex items-center gap-1">
                          <Eye className="w-3.5 h-3.5" /> Inspect
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}
      </div>

      {/* Post Detail Drawer / Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between pb-3 border-b border-slate-800">
              <div>
                <div className="flex items-center gap-2 text-xs mb-1">
                  <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 font-mono font-bold">
                    {selectedEvent.channel_name || selectedEvent.channel}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-semibold">
                    Scheduled Queue
                  </span>
                </div>
                <h3 className="text-lg font-bold text-white">{selectedEvent.title}</h3>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Time & Channel summary */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                <span className="text-slate-400 block mb-0.5">Scheduled Slot (IST)</span>
                <span className="text-white font-mono font-bold text-sm">
                  {selectedEvent.date} @ {selectedEvent.time}
                </span>
              </div>
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                <span className="text-slate-400 block mb-0.5">Category</span>
                <span className="text-white font-semibold text-sm">
                  {selectedEvent.category || 'Affiliate Deals'}
                </span>
              </div>
            </div>

            {/* Post Content */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-300">Post Message Content</label>
              <div className="bg-slate-950 border border-slate-800 rounded-xl p-3.5 text-xs text-slate-200 whitespace-pre-wrap font-sans leading-relaxed">
                {selectedEvent.text}
              </div>
            </div>

            {/* Links */}
            {selectedEvent.links && selectedEvent.links.length > 0 && (
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300">Affiliate Links Detected</label>
                <div className="space-y-1">
                  {selectedEvent.links.map((link, idx) => (
                    <a
                      key={idx}
                      href={link.startsWith('http') ? link : `https://${link}`}
                      target="_blank"
                      rel="noreferrer"
                      className="px-3 py-1.5 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs flex items-center justify-between hover:underline"
                    >
                      <span className="truncate">{link}</span>
                      <ExternalLink className="w-3.5 h-3.5 shrink-0 ml-2" />
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Image attachment badge */}
            {selectedEvent.image_name && (
              <div className="flex items-center gap-2 p-2.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300">
                <ImageIcon className="w-4 h-4 text-purple-400" />
                <span>Attached Graphic: <strong>{selectedEvent.image_name}</strong></span>
              </div>
            )}

            {/* Modal Actions */}
            <div className="pt-3 border-t border-slate-800 flex items-center justify-between">
              <button
                onClick={() => handleDeletePost(selectedEvent.id)}
                className="px-3 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition"
              >
                <Trash2 className="w-3.5 h-3.5" /> Cancel Post
              </button>
              <button
                onClick={() => setSelectedEvent(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Schedule Post Modal */}
      {isScheduleModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Plus className="w-5 h-5 text-blue-400" />
                Schedule New Telegram Post
              </h3>
              <button
                onClick={() => setIsScheduleModalOpen(false)}
                className="p-1 rounded text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="text-slate-300 font-semibold block mb-1">Target Channel</label>
                <select
                  value={newPostChannel}
                  onChange={e => setNewPostChannel(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-blue-500"
                >
                  {Object.entries(CHANNELS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v.sheetName || v.username} (@{v.username})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Date</label>
                  <input
                    type="date"
                    value={newPostDate}
                    onChange={e => setNewPostDate(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Time (IST)</label>
                  <input
                    type="time"
                    value={newPostTime}
                    onChange={e => setNewPostTime(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="text-slate-300 font-semibold block mb-1">Category</label>
                <input
                  type="text"
                  value={newPostCategory}
                  onChange={e => setNewPostCategory(e.target.value)}
                  placeholder="e.g. Deals, Electronics, Fashion"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="text-slate-300 font-semibold block mb-1">Post Content & Links</label>
                <textarea
                  rows={4}
                  value={newPostText}
                  onChange={e => setNewPostText(e.target.value)}
                  placeholder="Paste your Telegram post text with affiliate links..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-slate-200 focus:outline-none focus:border-blue-500 font-sans"
                />
              </div>
            </div>

            <div className="pt-3 border-t border-slate-800 flex items-center justify-end gap-2">
              <button
                onClick={() => setIsScheduleModalOpen(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={handleCreatePost}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold shadow-md shadow-blue-500/20"
              >
                Save to Calendar Queue
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
