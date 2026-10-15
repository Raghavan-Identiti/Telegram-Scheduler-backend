import React, { useState, useId } from 'react';
import {
  Repeat,
  Calendar,
  Clock,
  Plus,
  Trash2,
  Play,
  Pause,
  Layers,
  CheckCircle2,
  AlertCircle,
  FileText,
  Upload,
} from 'lucide-react';
import { CHANNELS } from '../services/channels';
import { generateRecurringDates, formatDateTimeIST } from '../services/schedulerEngine';
import { StorageService } from '../services/storage';
import {
  DayOfWeek,
  RecurrenceType,
  RecurringScheduleConfig,
  TimeSlot,
} from '../types';

interface RecurringSchedulerTabProps {
  onNotify: (msg: string) => void;
}

const ALL_DAYS: { key: DayOfWeek; label: string }[] = [
  { key: 'M', label: 'Mon' },
  { key: 'T', label: 'Tue' },
  { key: 'W', label: 'Wed' },
  { key: 'TH', label: 'Thu' },
  { key: 'F', label: 'Fri' },
  { key: 'S', label: 'Sat' },
  { key: 'SU', label: 'Sun' },
];

export const RecurringSchedulerTab: React.FC<RecurringSchedulerTabProps> = ({ onNotify }) => {
  const recurringImageInputId = useId();

  // Storage data
  const [recurringSchedules, setRecurringSchedules] = useState<RecurringScheduleConfig[]>(() =>
    StorageService.getRecurringSchedules()
  );

  // Form State
  const [scheduleName, setScheduleName] = useState<string>('Daily Morning Deals & Steals');
  const [recurrenceType, setRecurrenceType] = useState<RecurrenceType>('daily');
  const [selectedChannels, setSelectedChannels] = useState<string[]>([
    'amazonindiaassociates',
    'Amazon_Associates_FashionBeauty',
  ]);
  const [category, setCategory] = useState<string>('Daily Deals');

  const todayStr = new Date().toISOString().split('T')[0];
  const [startDate, setStartDate] = useState<string>(todayStr);
  const [endDate, setEndDate] = useState<string>('');
  const [maxOccurrences, setMaxOccurrences] = useState<string>('30');
  const [skipBlockedTimes, setSkipBlockedTimes] = useState<boolean>(true);

  // Daily times state (default: 09:00, 14:00, 20:00)
  const [dailyTimes, setDailyTimes] = useState<TimeSlot[]>([
    { hour: 9, minute: 0 },
    { hour: 14, minute: 0 },
    { hour: 20, minute: 0 },
  ]);

  // Weekly days & times state
  const [weeklyDays, setWeeklyDays] = useState<DayOfWeek[]>(['M', 'W', 'F']);
  const [weeklyTimesPerDay, setWeeklyTimesPerDay] = useState<Record<string, TimeSlot[]>>({
    M: [{ hour: 10, minute: 30 }, { hour: 18, minute: 0 }],
    W: [{ hour: 10, minute: 30 }, { hour: 18, minute: 0 }],
    F: [{ hour: 10, minute: 30 }, { hour: 20, minute: 0 }],
  });

  // Post content template
  const [postText, setPostText] = useState<string>(
    '⚡ DAILY PRIME STEALS ⚡\n\nCheck out today\'s top price drops on fashion, electronics, and daily essentials.\n\nShop verified offers: amzaff.in/1w2ZEzB\n\n#AmazonDeals #BestOffers'
  );
  const [imageName, setImageName] = useState<string>('daily_banner.jpg');

  // Preview generated occurrences
  const maxOccNum = maxOccurrences ? parseInt(maxOccurrences, 10) : undefined;
  const previewDates = generateRecurringDates(
    recurrenceType,
    startDate,
    endDate || undefined,
    dailyTimes,
    weeklyDays,
    weeklyTimesPerDay,
    maxOccNum || 15
  );

  // Channels helpers
  const toggleChannel = (id: string) => {
    setSelectedChannels(prev =>
      prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]
    );
  };

  // Daily time slot handlers
  const addDailyTimeSlot = () => {
    setDailyTimes(prev => [...prev, { hour: 12, minute: 0 }]);
  };

  const removeDailyTimeSlot = (index: number) => {
    setDailyTimes(prev => prev.filter((_, i) => i !== index));
  };

  const updateDailyTimeSlot = (index: number, timeStr: string) => {
    const parts = timeStr.split(':');
    if (parts.length === 2) {
      const h = parseInt(parts[0], 10);
      const m = parseInt(parts[1], 10);
      setDailyTimes(prev =>
        prev.map((slot, i) => (i === index ? { hour: h, minute: m } : slot))
      );
    }
  };

  // Weekly days handlers
  const toggleWeeklyDay = (day: DayOfWeek) => {
    setWeeklyDays(prev => {
      const exists = prev.includes(day);
      if (exists) {
        return prev.filter(d => d !== day);
      } else {
        // init default time for new day
        if (!weeklyTimesPerDay[day]) {
          setWeeklyTimesPerDay(t => ({
            ...t,
            [day]: [{ hour: 10, minute: 0 }],
          }));
        }
        return [...prev, day];
      }
    });
  };

  // Submit recurring schedule
  const handleSaveRecurringSchedule = (e: React.FormEvent) => {
    e.preventDefault();

    if (selectedChannels.length === 0) {
      alert('Please select at least one channel.');
      return;
    }

    if (!postText.trim()) {
      alert('Please enter post text for the recurring template.');
      return;
    }

    const newSchedule: RecurringScheduleConfig = {
      id: `recurring_${Date.now()}`,
      name: scheduleName,
      recurrenceType,
      channels: selectedChannels,
      category,
      startDate,
      endDate: endDate || undefined,
      dailyTimes: recurrenceType === 'daily' ? dailyTimes : undefined,
      weeklyDays: recurrenceType === 'weekly' ? weeklyDays : undefined,
      weeklyTimesPerDay: recurrenceType === 'weekly' ? weeklyTimesPerDay : undefined,
      maxOccurrences: maxOccNum,
      skipBlockedTimes,
      postText,
      imageName: imageName || undefined,
      active: true,
      createdAt: new Date().toISOString(),
    };

    const updated = StorageService.addRecurringSchedule(newSchedule);
    setRecurringSchedules(updated);
    onNotify(`Saved recurring schedule: "${scheduleName}"`);
  };

  const handleToggleActive = (id: string) => {
    const updated = StorageService.toggleRecurringSchedule(id);
    setRecurringSchedules(updated);
  };

  const handleDeleteSchedule = (id: string) => {
    if (confirm('Delete this recurring schedule?')) {
      const updated = StorageService.deleteRecurringSchedule(id);
      setRecurringSchedules(updated);
      onNotify('Recurring schedule deleted.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-gradient-to-r from-indigo-900/40 via-slate-900/60 to-slate-900 border border-indigo-500/30 rounded-2xl p-5 shadow-sm">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-white">Recurring Scheduler Engine</h2>
              <span className="px-2 py-0.5 text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 rounded-full">
                Daily & Weekly Auto-Queue
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Set up automated recurrence rules for daily drops or weekly day-of-week routines. Posts auto-fill Telegram channels.
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Form Config */}
        <div className="lg:col-span-2 space-y-6">
          <form onSubmit={handleSaveRecurringSchedule} className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-5">
            <div className="border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
                <Repeat className="w-4 h-4 text-indigo-400" />
                Configure Recurrence Rule
              </h3>
            </div>

            {/* Schedule Name & Category */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Rule Name</label>
                <input
                  type="text"
                  value={scheduleName}
                  onChange={e => setScheduleName(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">Category</label>
                <input
                  type="text"
                  value={category}
                  onChange={e => setCategory(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            {/* Recurrence Type Selector */}
            <div>
              <label className="text-xs text-slate-400 block mb-1.5">Recurrence Frequency</label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setRecurrenceType('daily')}
                  className={`py-2.5 px-4 rounded-xl border text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer ${
                    recurrenceType === 'daily'
                      ? 'bg-indigo-600/20 border-indigo-500 text-indigo-300'
                      : 'bg-slate-800 border-slate-700 text-slate-400 hover:bg-slate-800/80'
                  }`}
                >
                  <Repeat className="w-4 h-4" />
                  <span>Daily Recurrence</span>
                </button>
                <button
                  type="button"
                  onClick={() => setRecurrenceType('weekly')}
                  className={`py-2.5 px-4 rounded-xl border text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer ${
                    recurrenceType === 'weekly'
                      ? 'bg-indigo-600/20 border-indigo-500 text-indigo-300'
                      : 'bg-slate-800 border-slate-700 text-slate-400 hover:bg-slate-800/80'
                  }`}
                >
                  <Calendar className="w-4 h-4" />
                  <span>Weekly Day-of-Week</span>
                </button>
              </div>
            </div>

            {/* Daily Times Configuration */}
            {recurrenceType === 'daily' && (
              <div className="bg-slate-800/40 border border-slate-800 p-4 rounded-xl space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-200">
                    Execution Times Each Day (IST)
                  </label>
                  <button
                    type="button"
                    onClick={addDailyTimeSlot}
                    className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add Slot</span>
                  </button>
                </div>

                <div className="flex flex-wrap gap-2">
                  {dailyTimes.map((slot, idx) => {
                    const timeVal = `${slot.hour.toString().padStart(2, '0')}:${slot.minute
                      .toString()
                      .padStart(2, '0')}`;
                    return (
                      <div
                        key={idx}
                        className="flex items-center gap-1.5 bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5"
                      >
                        <Clock className="w-3.5 h-3.5 text-indigo-400" />
                        <input
                          type="time"
                          value={timeVal}
                          onChange={e => updateDailyTimeSlot(idx, e.target.value)}
                          className="bg-transparent text-xs text-white font-mono focus:outline-none"
                        />
                        {dailyTimes.length > 1 && (
                          <button
                            type="button"
                            onClick={() => removeDailyTimeSlot(idx)}
                            className="text-slate-500 hover:text-red-400 cursor-pointer"
                          >
                            ×
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Weekly Days Configuration */}
            {recurrenceType === 'weekly' && (
              <div className="bg-slate-800/40 border border-slate-800 p-4 rounded-xl space-y-3">
                <label className="text-xs font-semibold text-slate-200 block">
                  Select Days of Week
                </label>
                <div className="flex flex-wrap gap-2">
                  {ALL_DAYS.map(day => {
                    const isSelected = weeklyDays.includes(day.key);
                    return (
                      <button
                        key={day.key}
                        type="button"
                        onClick={() => toggleWeeklyDay(day.key)}
                        className={`w-11 h-10 rounded-xl text-xs font-bold border transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-indigo-600 text-white border-indigo-500 shadow-sm'
                            : 'bg-slate-800 text-slate-400 border-slate-700 hover:bg-slate-700'
                        }`}
                      >
                        {day.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Date Range & Occurrence limits */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Start Date</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={e => setStartDate(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">End Date (Optional)</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={e => setEndDate(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">Stop after (Occurrences)</label>
                <input
                  type="number"
                  min="1"
                  max="365"
                  value={maxOccurrences}
                  onChange={e => setMaxOccurrences(e.target.value)}
                  placeholder="e.g. 30"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            {/* Target Channels */}
            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-2">
                Target Channels ({selectedChannels.length})
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {Object.values(CHANNELS).map(chan => {
                  const isSelected = selectedChannels.includes(chan.id);
                  return (
                    <div
                      key={chan.id}
                      onClick={() => toggleChannel(chan.id)}
                      className={`flex items-center gap-2.5 p-2 rounded-lg border text-xs cursor-pointer transition-all ${
                        isSelected
                          ? 'bg-indigo-600/15 border-indigo-500/50 text-white'
                          : 'bg-slate-800/40 border-slate-700/50 text-slate-400 hover:bg-slate-800'
                      }`}
                    >
                      <div
                        className={`w-3.5 h-3.5 rounded border flex items-center justify-center ${
                          isSelected
                            ? 'bg-indigo-600 border-indigo-500 text-white'
                            : 'border-slate-600'
                        }`}
                      >
                        {isSelected && <CheckCircle2 className="w-2.5 h-2.5" />}
                      </div>
                      <span className="font-medium text-slate-200">{chan.name}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Skip blocked times checkbox */}
            <div className="flex items-center justify-between p-3 bg-slate-800/30 rounded-xl border border-slate-800">
              <div>
                <span className="text-xs font-medium text-slate-200">Skip Blocked Times</span>
                <p className="text-[11px] text-slate-500">
                  Automatically bypass conflict slots previously scheduled in GSheet or Telegram
                </p>
              </div>
              <input
                type="checkbox"
                checked={skipBlockedTimes}
                onChange={e => setSkipBlockedTimes(e.target.checked)}
                className="h-4 w-4 rounded bg-slate-800 border-slate-700 text-indigo-600 focus:ring-0 cursor-pointer"
              />
            </div>

            {/* Template Post Text & Image */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300 block">
                Post Text Content (Markdown & Affiliate Links Supported)
              </label>
              <textarea
                rows={4}
                value={postText}
                onChange={e => setPostText(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg p-3 text-xs text-white font-sans focus:outline-none focus:border-indigo-500"
                required
              />
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <input
                  id={recurringImageInputId}
                  type="file"
                  accept="image/*"
                  onChange={e => {
                    const f = e.target.files?.[0];
                    if (f) setImageName(f.name);
                  }}
                  className="hidden"
                />
                <label
                  htmlFor={recurringImageInputId}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-xs font-medium text-slate-300 flex items-center gap-1.5 cursor-pointer"
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>Attach Image</span>
                </label>
                {imageName && (
                  <span className="text-xs font-mono text-slate-400">{imageName}</span>
                )}
              </div>

              <button
                type="submit"
                className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs rounded-xl shadow-md transition-all flex items-center gap-1.5 cursor-pointer"
              >
                <Repeat className="w-4 h-4" />
                <span>Save Recurring Schedule</span>
              </button>
            </div>
          </form>
        </div>

        {/* Right Col: Next Executions Preview & Active Recurring Rules */}
        <div className="space-y-6">
          {/* Upcoming Executions Preview */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-indigo-400" />
                Next Executions Preview
              </span>
              <span className="text-xs font-mono text-slate-400">{previewDates.length} slots</span>
            </div>

            <div className="space-y-1.5 max-h-60 overflow-y-auto">
              {previewDates.slice(0, 10).map((dt, idx) => (
                <div
                  key={idx}
                  className="p-2 bg-slate-800/40 rounded-lg border border-slate-800/80 flex items-center justify-between text-xs"
                >
                  <span className="text-slate-400 font-mono">#{idx + 1}</span>
                  <span className="font-medium text-slate-200">{formatDateTimeIST(dt)}</span>
                  <span className="px-1.5 py-0.5 rounded text-[10px] bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                    {recurrenceType}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Active Recurring Rules List */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300 block">
              Active Recurring Rules ({recurringSchedules.length})
            </span>

            {recurringSchedules.length === 0 ? (
              <p className="text-xs text-slate-500 py-4 text-center">No recurring rules configured yet.</p>
            ) : (
              <div className="space-y-2.5">
                {recurringSchedules.map(rule => (
                  <div
                    key={rule.id}
                    className="p-3 bg-slate-800/50 border border-slate-800 rounded-xl space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-xs text-white">{rule.name}</span>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => handleToggleActive(rule.id)}
                          className={`p-1 rounded cursor-pointer ${
                            rule.active ? 'text-emerald-400 hover:bg-emerald-500/10' : 'text-slate-500'
                          }`}
                          title={rule.active ? 'Pause' : 'Activate'}
                        >
                          {rule.active ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteSchedule(rule.id)}
                          className="p-1 rounded text-slate-500 hover:text-red-400 hover:bg-red-500/10 cursor-pointer"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 text-[11px] text-slate-400">
                      <span className="capitalize">{rule.recurrenceType}</span>
                      <span>•</span>
                      <span>{rule.channels.length} channels</span>
                      {rule.maxOccurrences && (
                        <>
                          <span>•</span>
                          <span>Max {rule.maxOccurrences}x</span>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
