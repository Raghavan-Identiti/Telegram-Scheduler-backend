export interface TelegramChannel {
  id: string;
  username: string;
  name: string;
  sheetName: string;
}

export interface ChannelSheetConfig {
  sheet_id: string;
  sheet_url: string;
  sheet_tab: string;
}

export interface ParsedPost {
  postNum: number;
  text: string;
  category?: string | null;
  customTime?: string | null;
  links: string[];
  imagePath?: string | null;
  imageDataUrl?: string | null;
  captionStatus?: {
    canUseAsCaption: boolean;
    length: number;
    exceedsBy: number;
    safeCaption: string;
    remainingText: string;
  };
}

export interface TimeSlotItem {
  time: string; // ISO or HH:mm
  dateTime: Date;
  status: 'free' | 'assigned' | 'blocked';
  assignedPostNum?: number;
  channel?: string;
}

export interface ScheduledPostRecord {
  id: string;
  postNumber: number | string;
  channel: string;
  channelUsername: string;
  time: string; // e.g. "14:30" or ISO
  fullDateTime: string;
  text: string;
  category?: string;
  imageName?: string;
  imageDataUrl?: string;
  status: 'scheduled' | 'skipped' | 'failed' | 'live';
  error?: string | null;
  views?: number;
  telegramClicks?: number;
  whatsappClicks?: number;
  links?: string[];
  isRecurring?: boolean;
  recurrenceId?: string;
  createdAt: string;
}

export type RecurrenceType = 'daily' | 'weekly';

export type DayOfWeek = 'M' | 'T' | 'W' | 'TH' | 'F' | 'S' | 'SU';

export interface TimeSlot {
  hour: number;
  minute: number;
}

export interface RecurringScheduleConfig {
  id: string;
  name: string;
  recurrenceType: RecurrenceType;
  channels: string[];
  category?: string;
  startDate: string; // YYYY-MM-DD
  endDate?: string;  // YYYY-MM-DD
  dailyTimes?: TimeSlot[];
  weeklyDays?: DayOfWeek[];
  weeklyTimesPerDay?: Record<string, TimeSlot[]>;
  maxOccurrences?: number;
  skipBlockedTimes: boolean;
  postText: string;
  imageName?: string;
  imageDataUrl?: string;
  active: boolean;
  createdAt: string;
}

export interface WhatsAppRecipient {
  id: string;
  name: string;
  phone: string; // Target newsletter or phone, e.g., 120363408723243626@newsletter
  subscribers: string;
  avatar: string;
  color: string;
}

export interface WhatsAppPost {
  id: number;
  recipient_id: string;
  recipient_name: string;
  recipient_phone: string;
  message: string | null;
  image_path: string | null;
  image_url?: string | null;
  scheduled_at: string; // ISO UTC
  status: 'pending' | 'sent' | 'failed' | 'cancelled';
  attempts: number;
  next_attempt_at?: string | null;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AppSettings {
  auto_fetch_enabled: boolean;
  channel_sheets: Record<string, ChannelSheetConfig>;
  google_sheets_connected: boolean;
  whatsapp_connected: boolean;
  telegram_connected: boolean;
}

export interface PostLogItem {
  id: number | string;
  date: string;
  time: string;
  channel: string;
  postNumber: number | string;
  views: number;
  telegramClicks: number;
  whatsappClicks: number;
  links: string;
  text: string;
  status: string;
}
