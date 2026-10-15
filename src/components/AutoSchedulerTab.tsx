import React, { useState, useId } from 'react';
import {
  Upload,
  Calendar,
  Clock,
  Layers,
  CheckCircle2,
  AlertTriangle,
  FileText,
  Image as ImageIcon,
  Send,
  Trash2,
  Eye,
  Sliders,
  ExternalLink,
  Info,
} from 'lucide-react';
import { CHANNELS } from '../services/channels';
import {
  extractAllPostsFromTexts,
  extractPostNumberFromFilename,
  extractLinks,
  validateCaption,
} from '../services/postParser';
import {
  generate5MinGrid,
  roundToNearest5,
  formatTime24,
  parseCustomTime,
} from '../services/schedulerEngine';
import { StorageService } from '../services/storage';
import { ParsedPost, ScheduledPostRecord, TimeSlotItem } from '../types';

interface AutoSchedulerTabProps {
  onScheduleSuccess: (msg: string) => void;
}

export const AutoSchedulerTab: React.FC<AutoSchedulerTabProps> = ({ onScheduleSuccess }) => {
  const textInputId = useId();
  const imageInputId = useId();

  // Channel Selection
  const [selectedChannels, setSelectedChannels] = useState<string[]>([
    'amazonindiaassociates',
    'Amazon_Associates_FashionBeauty',
  ]);

  // Date and Time settings (Default: Today from 10:00 to 22:00)
  const todayStr = new Date().toISOString().split('T')[0];
  const [scheduleDate, setScheduleDate] = useState<string>(todayStr);
  const [startTime, setStartTime] = useState<string>('10:00');
  const [endTime, setEndTime] = useState<string>('22:00');

  // Scheduling options
  const [schedulingMode, setSchedulingMode] = useState<'auto' | 'interval'>('auto');
  const [intervalMinutes, setIntervalMinutes] = useState<number>(30);
  const [sendImageOnly, setSendImageOnly] = useState<boolean>(false);

  // Files & Parsed Posts
  const [textFiles, setTextFiles] = useState<{ name: string; content: string }[]>([]);
  const [imageFiles, setImageFiles] = useState<
    { name: string; postNum: number | null; dataUrl: string }[]
  >([]);
  const [parsedPosts, setParsedPosts] = useState<ParsedPost[]>([]);

  // Custom times per post (postNum -> HH:mm)
  const [customTimes, setCustomTimes] = useState<Record<number, string>>({});

  // Scheduling result feedback
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [lastResult, setLastResult] = useState<{
    status: string;
    scheduled: number;
    failed: number;
    skipped: number;
    total: number;
    blockedSlots: number;
  } | null>(null);

  // Preview modal for full post
  const [previewPost, setPreviewPost] = useState<ParsedPost | null>(null);

  // Toggle channel
  const toggleChannel = (id: string) => {
    setSelectedChannels(prev =>
      prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]
    );
  };

  const selectAllChannels = () => {
    setSelectedChannels(Object.keys(CHANNELS));
  };

  const clearChannels = () => {
    setSelectedChannels([]);
  };

  // Handle Text Files Upload
  const handleTextUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const newFiles: { name: string; content: string }[] = [];
    let readCount = 0;

    Array.from(files).forEach(file => {
      const reader = new FileReader();
      reader.onload = event => {
        const content = event.target?.result as string;
        newFiles.push({ name: file.name, content });
        readCount++;
        if (readCount === files.length) {
          setTextFiles(prev => [...prev, ...newFiles]);
          recalculatePosts([...textFiles, ...newFiles], imageFiles);
        }
      };
      reader.readAsText(file, 'utf-8');
    });
  };

  // Handle Image Files Upload
  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const newImages: { name: string; postNum: number | null; dataUrl: string }[] = [];
    let readCount = 0;

    Array.from(files).forEach(file => {
      const reader = new FileReader();
      const postNum = extractPostNumberFromFilename(file.name);
      reader.onload = event => {
        const dataUrl = event.target?.result as string;
        newImages.push({ name: file.name, postNum, dataUrl });
        readCount++;
        if (readCount === files.length) {
          setImageFiles(prev => [...prev, ...newImages]);
          recalculatePosts(textFiles, [...imageFiles, ...newImages]);
        }
      };
      reader.readAsDataURL(file);
    });
  };

  // Load Built-in Demo Post Data
  const loadDemoPosts = () => {
    const sampleText = `AMZ_TELEGRAM
*************************

Post 1
Category: Deals
⏰ 8PM DEALS 📣 LIMITED PERIOD ONLY

🔥 Unmissable deals on Top Smartphones and Smartwatches!
Grab the offers before midnight.

👉🏻 amzaff.in/1ZQZf7G
Post 1 End

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

Post 2
Category: Fashion
Time: 15:30
✨ FASHION TRENDS OF THE SEASON

Get up to 60% off on top branded footwear and ethnic collections.
Extra 10% instant bank discount on checkout.

👉🏻 amzaff.in/sd53Qad
Post 2 End

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

Post 3
Category: Home & Kitchen
🍳 Kitchen Upgrade Fest!

Air fryers, non-stick cookware & mixer grinders at best prices of the year.

👉🏻 amzaff.in/JTGc9BA
Post 3 End

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

Post 4
Category: Consumables
Time: 19:45
🛒 Monthly Grocery Stock Up

Save big on tea, coffee, nuts, and household essentials.
Prime free one-day delivery available.

👉🏻 amzaff.in/neZvUY8
Post 4 End
`;

    const demoImages = [
      {
        name: 'post1.jpg',
        postNum: 1,
        dataUrl: 'https://images.unsplash.com/photo-1546868871-7041f2a55e12?w=400&auto=format&fit=crop&q=60',
      },
      {
        name: 'post2.jpg',
        postNum: 2,
        dataUrl: 'https://images.unsplash.com/photo-1483985988355-763728e1935b?w=400&auto=format&fit=crop&q=60',
      },
      {
        name: 'post3.jpg',
        postNum: 3,
        dataUrl: 'https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=400&auto=format&fit=crop&q=60',
      },
      {
        name: 'post4.jpg',
        postNum: 4,
        dataUrl: 'https://images.unsplash.com/photo-1542838132-92c53300491e?w=400&auto=format&fit=crop&q=60',
      },
    ];

    setTextFiles([{ name: 'Demo_Deals_Batch.txt', content: sampleText }]);
    setImageFiles(demoImages);
    recalculatePosts([{ name: 'Demo_Deals_Batch.txt', content: sampleText }], demoImages);
  };

  // Parse and assemble posts
  const recalculatePosts = (
    texts: { name: string; content: string }[],
    images: { name: string; postNum: number | null; dataUrl: string }[]
  ) => {
    const rawPosts = extractAllPostsFromTexts(texts.map(t => t.content));
    const imageMap: Record<number, { name: string; dataUrl: string }> = {};

    images.forEach(img => {
      if (img.postNum !== null) {
        imageMap[img.postNum] = { name: img.name, dataUrl: img.dataUrl };
      }
    });

    const allNums = Array.from(
      new Set([...Object.keys(rawPosts).map(Number), ...Object.keys(imageMap).map(Number)])
    ).sort((a, b) => a - b);

    const posts: ParsedPost[] = allNums.map(num => {
      const postData = rawPosts[num];
      const text = postData?.text || (imageMap[num] ? '📸 Image post' : '');
      const category = postData?.category || null;
      const customTime = postData?.customTime || null;
      const links = extractLinks(text);
      const captionStatus = validateCaption(text);

      return {
        postNum: num,
        text,
        category,
        customTime,
        links,
        imagePath: imageMap[num]?.name || null,
        imageDataUrl: imageMap[num]?.dataUrl || null,
        captionStatus,
      };
    });

    setParsedPosts(posts);

    // Populate detected custom times into state if not already set
    const initCustom: Record<number, string> = {};
    posts.forEach(p => {
      if (p.customTime) {
        initCustom[p.postNum] = p.customTime;
      }
    });
    setCustomTimes(prev => ({ ...initCustom, ...prev }));
  };

  const handleCustomTimeChange = (postNum: number, value: string) => {
    setCustomTimes(prev => ({ ...prev, [postNum]: value }));
  };

  const clearAllUploads = () => {
    setTextFiles([]);
    setImageFiles([]);
    setParsedPosts([]);
    setCustomTimes({});
    setLastResult(null);
  };

  // Calculate 5-minute slots and simulate blocked times
  const computeTimeSlots = () => {
    const start = new Date(`${scheduleDate}T${startTime}:00`);
    const end = new Date(`${scheduleDate}T${endTime}:00`);

    if (isNaN(start.getTime()) || isNaN(end.getTime()) || start >= end) {
      return [];
    }

    const grid = generate5MinGrid(start, end);

    // Mock existing booked slots from storage / sheets
    const existingPosts = StorageService.getScheduledPosts();
    const bookedTimeStrings = new Set<string>();

    existingPosts.forEach(p => {
      if (p.time && p.fullDateTime.startsWith(scheduleDate)) {
        bookedTimeStrings.add(p.time);
      }
    });

    return grid.map(dt => {
      const timeStr = formatTime24(dt);
      const isBlocked = bookedTimeStrings.has(timeStr);
      return {
        time: timeStr,
        dateTime: dt,
        status: isBlocked ? ('blocked' as const) : ('free' as const),
      };
    });
  };

  const timeSlots = computeTimeSlots();

  // Execute Auto Scheduling
  const handleScheduleSubmit = () => {
    if (selectedChannels.length === 0) {
      alert('Please select at least one channel.');
      return;
    }

    if (parsedPosts.length === 0) {
      alert('No posts detected. Upload a .txt file or click "Load Demo Posts".');
      return;
    }

    setIsProcessing(true);

    // Calculate slots according to original backend algorithm
    const start = new Date(`${scheduleDate}T${startTime}:00`);
    const end = new Date(`${scheduleDate}T${endTime}:00`);
    const grid = generate5MinGrid(start, end);

    // Blocked slots
    const existingPosts = StorageService.getScheduledPosts();
    const blockedTimesSet = new Set<string>();
    existingPosts.forEach(p => {
      if (p.time && p.fullDateTime.startsWith(scheduleDate)) {
        blockedTimesSet.add(p.time);
      }
    });

    const availableSlots = grid.filter(g => !blockedTimesSet.has(formatTime24(g)));
    const assignedSlots = new Set<string>();
    const postTimesMap: Record<number, { timeStr: string; fullDate: Date } | null> = {};

    // 1. Process custom times first
    parsedPosts.forEach(post => {
      const customVal = customTimes[post.postNum] || post.customTime;
      if (customVal) {
        const parsedDt = parseCustomTime(customVal, start);
        if (parsedDt) {
          const tStr = formatTime24(parsedDt);
          if (blockedTimesSet.has(tStr)) {
            // Conflict: custom time is blocked
            postTimesMap[post.postNum] = null;
          } else {
            postTimesMap[post.postNum] = { timeStr: tStr, fullDate: parsedDt };
            assignedSlots.add(tStr);
          }
        }
      }
    });

    // Remaining slots
    const remainingSlots = availableSlots.filter(s => !assignedSlots.has(formatTime24(s)));
    const unassignedPosts = parsedPosts.filter(p => !postTimesMap[p.postNum]);

    if (schedulingMode === 'interval' && intervalMinutes > 0) {
      let currentDt = new Date(start);
      unassignedPosts.forEach(post => {
        let foundSlot: Date | null = null;
        for (let i = 0; i < remainingSlots.length; i++) {
          const candidate = remainingSlots[i];
          if (candidate >= currentDt && !assignedSlots.has(formatTime24(candidate))) {
            foundSlot = candidate;
            remainingSlots.splice(i, 1);
            break;
          }
        }
        if (foundSlot) {
          const tStr = formatTime24(foundSlot);
          postTimesMap[post.postNum] = { timeStr: tStr, fullDate: foundSlot };
          assignedSlots.add(tStr);
        } else {
          postTimesMap[post.postNum] = null;
        }
        currentDt = new Date(currentDt.getTime() + intervalMinutes * 60 * 1000);
      });
    } else {
      // Auto even distribution
      if (unassignedPosts.length > 0 && remainingSlots.length > 0) {
        const step = Math.max(1, Math.floor(remainingSlots.length / unassignedPosts.length));
        unassignedPosts.forEach((post, idx) => {
          const slotIdx = Math.min(idx * step, remainingSlots.length - 1);
          const chosenSlot = remainingSlots[slotIdx];
          if (chosenSlot && !assignedSlots.has(formatTime24(chosenSlot))) {
            const tStr = formatTime24(chosenSlot);
            postTimesMap[post.postNum] = { timeStr: tStr, fullDate: chosenSlot };
            assignedSlots.add(tStr);
          } else {
            postTimesMap[post.postNum] = null;
          }
        });
      }
    }

    // Now generate scheduled records across all selected channels
    let scheduledCount = 0;
    let failedCount = 0;
    let skippedCount = 0;
    const newRecords: ScheduledPostRecord[] = [];

    selectedChannels.forEach(chanId => {
      const channelObj = CHANNELS[chanId];
      if (!channelObj) return;

      parsedPosts.forEach(post => {
        const timeInfo = postTimesMap[post.postNum];
        if (!timeInfo) {
          skippedCount++;
          newRecords.push({
            id: `sched_${Date.now()}_${chanId}_${post.postNum}`,
            postNumber: post.postNum,
            channel: chanId,
            channelUsername: channelObj.username,
            time: 'N/A',
            fullDateTime: `${scheduleDate}T00:00:00`,
            text: post.text,
            category: post.category || 'General',
            imageName: post.imagePath || undefined,
            imageDataUrl: post.imageDataUrl || undefined,
            status: 'skipped',
            error: 'No available 5-min slot or time is blocked',
            createdAt: new Date().toISOString(),
          });
          return;
        }

        scheduledCount++;
        newRecords.push({
          id: `sched_${Date.now()}_${chanId}_${post.postNum}`,
          postNumber: post.postNum,
          channel: chanId,
          channelUsername: channelObj.username,
          time: timeInfo.timeStr,
          fullDateTime: timeInfo.fullDate.toISOString(),
          text: sendImageOnly ? '' : post.text,
          category: post.category || 'General',
          imageName: post.imagePath || undefined,
          imageDataUrl: post.imageDataUrl || undefined,
          status: 'scheduled',
          views: 0,
          telegramClicks: 0,
          whatsappClicks: 0,
          links: post.links,
          createdAt: new Date().toISOString(),
        });
      });
    });

    StorageService.addScheduledPosts(newRecords);

    // Also add to execution logs
    newRecords
      .filter(r => r.status === 'scheduled')
      .slice(0, 5)
      .forEach(r => {
        StorageService.addLog({
          date: scheduleDate,
          time: `${r.time}:00`,
          channel: r.channelUsername,
          postNumber: r.postNumber,
          views: 0,
          telegramClicks: 0,
          whatsappClicks: 0,
          links: (r.links || []).join(', '),
          text: r.text.slice(0, 60),
          status: 'Scheduled',
        });
      });

    setTimeout(() => {
      setIsProcessing(false);
      const res = {
        status: `Successfully scheduled ${scheduledCount} posts across ${selectedChannels.length} channels`,
        scheduled: scheduledCount,
        failed: failedCount,
        skipped: skippedCount,
        total: parsedPosts.length * selectedChannels.length,
        blockedSlots: blockedTimesSet.size,
      };
      setLastResult(res);
      onScheduleSuccess(res.status);
    }, 400);
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Demo Loader */}
      <div className="bg-gradient-to-r from-blue-900/40 via-slate-900/60 to-slate-900 border border-blue-500/30 rounded-2xl p-5 shadow-sm">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-white">Auto Scheduler & Bulk Upload</h2>
              <span className="px-2 py-0.5 text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30 rounded-full">
                5-Min Grid Engine
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Upload formatted text files & images. Posts are extracted automatically, assigned to free slots, and dispatched.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={loadDemoPosts}
              className="px-3.5 py-1.5 text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white rounded-lg shadow-sm transition-all flex items-center gap-1.5 cursor-pointer"
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Load Demo Posts</span>
            </button>
            {(textFiles.length > 0 || imageFiles.length > 0) && (
              <button
                onClick={clearAllUploads}
                className="px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors flex items-center gap-1 cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Clear</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Grid: Left Column (Channels & Time Window) & Right Column (Upload & Settings) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Channels & Scheduling Windows */}
        <div className="space-y-6">
          {/* Channel Selector */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-blue-400" />
                Target Channels ({selectedChannels.length})
              </label>
              <div className="flex items-center gap-2 text-xs">
                <button
                  type="button"
                  onClick={selectAllChannels}
                  className="text-blue-400 hover:underline cursor-pointer"
                >
                  Select All
                </button>
                <span className="text-slate-600">|</span>
                <button
                  type="button"
                  onClick={clearChannels}
                  className="text-slate-400 hover:underline cursor-pointer"
                >
                  Clear
                </button>
              </div>
            </div>

            <div className="space-y-2">
              {Object.values(CHANNELS).map(chan => {
                const isSelected = selectedChannels.includes(chan.id);
                return (
                  <div
                    key={chan.id}
                    onClick={() => toggleChannel(chan.id)}
                    className={`flex items-center justify-between p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-blue-600/10 border-blue-500/40 text-white'
                        : 'bg-slate-800/40 border-slate-700/50 text-slate-400 hover:bg-slate-800'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <div
                        className={`w-4 h-4 rounded border flex items-center justify-center ${
                          isSelected
                            ? 'bg-blue-600 border-blue-500 text-white'
                            : 'border-slate-600'
                        }`}
                      >
                        {isSelected && <CheckCircle2 className="w-3 h-3" />}
                      </div>
                      <span className="font-medium text-slate-200">{chan.name}</span>
                    </div>
                    <span className="text-[11px] font-mono text-slate-400">@{chan.username}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Time Window & Scheduling Mode */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-4">
            <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <Calendar className="w-4 h-4 text-blue-400" />
              Schedule Window (IST)
            </label>

            <div>
              <label className="text-xs text-slate-400 block mb-1">Target Date</label>
              <input
                type="date"
                value={scheduleDate}
                onChange={e => setScheduleDate(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Start Time</label>
                <input
                  type="time"
                  value={startTime}
                  onChange={e => setStartTime(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">End Time</label>
                <input
                  type="time"
                  value={endTime}
                  onChange={e => setEndTime(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            {/* Mode selection */}
            <div>
              <label className="text-xs text-slate-400 block mb-1">Distribution Mode</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setSchedulingMode('auto')}
                  className={`py-2 px-3 text-xs rounded-lg font-medium border text-center transition-all cursor-pointer ${
                    schedulingMode === 'auto'
                      ? 'bg-blue-600/20 border-blue-500/50 text-blue-400'
                      : 'bg-slate-800/60 border-slate-700 text-slate-400'
                  }`}
                >
                  Auto Distribute
                </button>
                <button
                  type="button"
                  onClick={() => setSchedulingMode('interval')}
                  className={`py-2 px-3 text-xs rounded-lg font-medium border text-center transition-all cursor-pointer ${
                    schedulingMode === 'interval'
                      ? 'bg-blue-600/20 border-blue-500/50 text-blue-400'
                      : 'bg-slate-800/60 border-slate-700 text-slate-400'
                  }`}
                >
                  Fixed Interval
                </button>
              </div>
            </div>

            {schedulingMode === 'interval' && (
              <div>
                <label className="text-xs text-slate-400 block mb-1">Interval (minutes)</label>
                <div className="flex items-center gap-2">
                  {[15, 30, 45, 60].map(mins => (
                    <button
                      key={mins}
                      type="button"
                      onClick={() => setIntervalMinutes(mins)}
                      className={`px-3 py-1.5 rounded text-xs font-semibold cursor-pointer ${
                        intervalMinutes === mins
                          ? 'bg-blue-600 text-white'
                          : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                      }`}
                    >
                      {mins}m
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Image-only toggle */}
            <div className="pt-2 border-t border-slate-800 flex items-center justify-between">
              <div>
                <span className="text-xs font-medium text-slate-200">Send Image Only</span>
                <p className="text-[11px] text-slate-500">Omit text message caption</p>
              </div>
              <input
                type="checkbox"
                checked={sendImageOnly}
                onChange={e => setSendImageOnly(e.target.checked)}
                className="h-4 w-4 rounded bg-slate-800 border-slate-700 text-blue-600 focus:ring-0 cursor-pointer"
              />
            </div>
          </div>
        </div>

        {/* Middle & Right Column: File Upload & Parsed Posts Table */}
        <div className="lg:col-span-2 space-y-6">
          {/* File Upload Dropzones */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Text Files Upload */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                  <FileText className="w-4 h-4 text-blue-400" />
                  Text Posts (.txt)
                </span>
                <span className="text-xs font-mono text-slate-400">{textFiles.length} uploaded</span>
              </div>
              <label
                htmlFor={textInputId}
                className="border-2 border-dashed border-slate-700 hover:border-blue-500/60 rounded-xl p-4 flex flex-col items-center justify-center gap-2 cursor-pointer transition-colors bg-slate-800/30 hover:bg-slate-800/60"
              >
                <Upload className="w-5 h-5 text-slate-400" />
                <span className="text-xs text-slate-300 font-medium">Click to upload .txt files</span>
                <span className="text-[10px] text-slate-500">Supports Post 1, Post 2, AMZ_TELEGRAM</span>
                <input
                  id={textInputId}
                  type="file"
                  accept=".txt"
                  multiple
                  onChange={handleTextUpload}
                  className="hidden"
                />
              </label>
            </div>

            {/* Image Files Upload */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                  <ImageIcon className="w-4 h-4 text-indigo-400" />
                  Post Images
                </span>
                <span className="text-xs font-mono text-slate-400">{imageFiles.length} uploaded</span>
              </div>
              <label
                htmlFor={imageInputId}
                className="border-2 border-dashed border-slate-700 hover:border-indigo-500/60 rounded-xl p-4 flex flex-col items-center justify-center gap-2 cursor-pointer transition-colors bg-slate-800/30 hover:bg-slate-800/60"
              >
                <Upload className="w-5 h-5 text-slate-400" />
                <span className="text-xs text-slate-300 font-medium">Click to upload images</span>
                <span className="text-[10px] text-slate-500">Matches post1.jpg, post-2.png, etc.</span>
                <input
                  id={imageInputId}
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleImageUpload}
                  className="hidden"
                />
              </label>
            </div>
          </div>

          {/* 5-Minute Slots Grid Bar */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-blue-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                  5-Minute Slots Grid ({timeSlots.length} Total)
                </span>
              </div>
              <div className="flex items-center gap-3 text-[11px]">
                <span className="flex items-center gap-1 text-slate-400">
                  <span className="h-2 w-2 rounded-full bg-slate-600"></span> Free
                </span>
                <span className="flex items-center gap-1 text-red-400">
                  <span className="h-2 w-2 rounded-full bg-red-500"></span> Blocked/Booked
                </span>
              </div>
            </div>
            <div className="max-h-24 overflow-y-auto flex flex-wrap gap-1.5 p-2 bg-slate-950/60 rounded-lg border border-slate-800/60">
              {timeSlots.map((slot, i) => (
                <span
                  key={i}
                  className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium ${
                    slot.status === 'blocked'
                      ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                      : 'bg-slate-800 text-slate-300 border border-slate-700/60'
                  }`}
                >
                  {slot.time}
                </span>
              ))}
            </div>
          </div>

          {/* Parsed Posts List */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                  Detected Posts ({parsedPosts.length})
                </span>
                <p className="text-[11px] text-slate-500">
                  Verify matched images, affiliate links, and caption lengths before scheduling.
                </p>
              </div>

              {parsedPosts.length > 0 && (
                <button
                  type="button"
                  disabled={isProcessing || selectedChannels.length === 0}
                  onClick={handleScheduleSubmit}
                  className="px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 text-white font-semibold text-xs rounded-xl shadow-md transition-all flex items-center gap-2 cursor-pointer"
                >
                  <Send className="w-4 h-4" />
                  <span>{isProcessing ? 'Scheduling...' : 'Schedule All Posts'}</span>
                </button>
              )}
            </div>

            {parsedPosts.length === 0 ? (
              <div className="py-12 border border-slate-800 rounded-lg text-center text-slate-500">
                <FileText className="w-8 h-8 mx-auto mb-2 opacity-40 text-blue-400" />
                <p className="text-xs">No posts loaded yet.</p>
                <p className="text-[11px] text-slate-600 mt-1">
                  Upload your .txt and image files above or click &quot;Load Demo Posts&quot; to test.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {parsedPosts.map(post => {
                  const customVal = customTimes[post.postNum] || post.customTime || '';
                  const captionValid = post.captionStatus?.canUseAsCaption ?? true;

                  return (
                    <div
                      key={post.postNum}
                      className="bg-slate-800/40 border border-slate-800 hover:border-slate-700 rounded-xl p-3.5 transition-all"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        {/* Post Header: Number, Image preview, Category */}
                        <div className="flex items-center gap-3">
                          <span className="h-8 w-8 rounded-lg bg-blue-600/20 text-blue-400 border border-blue-500/30 flex items-center justify-center font-bold text-xs font-mono">
                            #{post.postNum}
                          </span>

                          {post.imageDataUrl ? (
                            <img
                              src={post.imageDataUrl}
                              alt={`Post ${post.postNum}`}
                              className="w-10 h-10 object-cover rounded-lg border border-slate-700 cursor-pointer hover:opacity-80"
                              onClick={() => setPreviewPost(post)}
                            />
                          ) : (
                            <div className="w-10 h-10 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-[10px] text-slate-500">
                              No Img
                            </div>
                          )}

                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-semibold text-white">
                                Post {post.postNum}
                              </span>
                              {post.category && (
                                <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 border border-slate-700">
                                  {post.category}
                                </span>
                              )}
                              {post.imagePath && (
                                <span className="text-[10px] text-slate-400 font-mono">
                                  {post.imagePath}
                                </span>
                              )}
                            </div>

                            <p className="text-xs text-slate-300 line-clamp-1 mt-0.5 max-w-md">
                              {post.text || 'No text content'}
                            </p>
                          </div>
                        </div>

                        {/* Right side: Custom Time Override & Actions */}
                        <div className="flex items-center gap-3">
                          <div className="flex items-center gap-1.5 text-xs">
                            <span className="text-slate-400">Time:</span>
                            <input
                              type="text"
                              placeholder="HH:mm"
                              value={customVal}
                              onChange={e => handleCustomTimeChange(post.postNum, e.target.value)}
                              className="w-20 bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-white text-center font-mono focus:border-blue-500 focus:outline-none"
                            />
                          </div>

                          <button
                            type="button"
                            onClick={() => setPreviewPost(post)}
                            className="p-1.5 text-slate-400 hover:text-white rounded hover:bg-slate-700 transition-colors cursor-pointer"
                            title="Preview full post"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                        </div>
                      </div>

                      {/* Telegram Caption Limits & Affiliate Links Indicators */}
                      <div className="mt-2.5 pt-2 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-2 text-[11px]">
                        <div className="flex items-center gap-2">
                          {captionValid ? (
                            <span className="text-emerald-400 flex items-center gap-1">
                              <CheckCircle2 className="w-3 h-3" />
                              Telegram caption fit ({post.captionStatus?.length || 0}/1024)
                            </span>
                          ) : (
                            <span className="text-amber-400 flex items-center gap-1 font-medium">
                              <AlertTriangle className="w-3 h-3" />
                              Exceeds caption by {post.captionStatus?.exceedsBy} chars (will split with 3m delay)
                            </span>
                          )}
                        </div>

                        {post.links.length > 0 && (
                          <div className="flex items-center gap-1.5">
                            <span className="text-slate-500">Links:</span>
                            {post.links.map((link, idx) => (
                              <span
                                key={idx}
                                className="font-mono text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded text-[10px] max-w-xs truncate"
                              >
                                {link}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Last Result Box */}
          {lastResult && (
            <div className="bg-emerald-950/30 border border-emerald-500/40 rounded-xl p-4 flex items-center justify-between text-xs text-emerald-300">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                <div>
                  <span className="font-bold">{lastResult.status}</span>
                  <p className="text-[11px] text-emerald-400/80 mt-0.5">
                    {lastResult.scheduled} scheduled, {lastResult.skipped} skipped (blocked/conflict), {lastResult.total} total channel dispatches.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Post Preview Modal */}
      {previewPost && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-white text-base flex items-center gap-2">
                <span>Preview Post #{previewPost.postNum}</span>
                {previewPost.category && (
                  <span className="text-xs bg-slate-800 px-2 py-0.5 rounded border border-slate-700 text-slate-300">
                    {previewPost.category}
                  </span>
                )}
              </h3>
              <button
                onClick={() => setPreviewPost(null)}
                className="text-slate-400 hover:text-white text-xs px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 cursor-pointer"
              >
                Close
              </button>
            </div>

            {previewPost.imageDataUrl && (
              <div className="rounded-xl overflow-hidden border border-slate-800 max-h-56 bg-slate-950 flex items-center justify-center">
                <img
                  src={previewPost.imageDataUrl}
                  alt={`Post ${previewPost.postNum}`}
                  className="max-h-56 w-auto object-contain"
                />
              </div>
            )}

            <div className="space-y-2">
              <span className="text-xs font-semibold uppercase text-slate-400">Post Message Text</span>
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 font-sans text-xs text-slate-200 whitespace-pre-wrap max-h-48 overflow-y-auto">
                {previewPost.text}
              </div>
            </div>

            {previewPost.links.length > 0 && (
              <div>
                <span className="text-xs font-semibold uppercase text-slate-400">Affiliate Links Detected</span>
                <div className="mt-1 flex flex-wrap gap-2">
                  {previewPost.links.map((link, i) => (
                    <span
                      key={i}
                      className="text-xs font-mono text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2 py-1 rounded"
                    >
                      {link}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
