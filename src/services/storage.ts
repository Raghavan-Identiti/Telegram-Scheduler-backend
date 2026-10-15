import {
  ScheduledPostRecord,
  RecurringScheduleConfig,
  WhatsAppRecipient,
  WhatsAppPost,
  AppSettings,
  PostLogItem,
} from '../types';
import { DEFAULT_WHATSAPP_RECIPIENTS, INITIAL_SETTINGS } from './channels';

const KEYS = {
  POSTS: 'telequeue_scheduled_posts_v1',
  RECURRING: 'telequeue_recurring_v1',
  WHATSAPP_RECIPIENTS: 'telequeue_wa_recipients_v1',
  WHATSAPP_POSTS: 'telequeue_wa_posts_v1',
  SETTINGS: 'telequeue_settings_v1',
  LOGS: 'telequeue_logs_v1',
};

// Seed initial posts & logs based on the project's actual data
const INITIAL_SCHEDULED_POSTS: ScheduledPostRecord[] = [
  {
    id: 'post_seed_1',
    postNumber: 1,
    channel: 'amazonindiaassociates',
    channelUsername: 'amazonindiaassociates',
    time: '14:30',
    fullDateTime: new Date(Date.now() + 3600 * 1000 * 2).toISOString(),
    text: '⏰ 8PM DEALS 📣 LIMITED PERIOD ONLY\n\n🔥 Unmissable deals from 8PM till midnight\n\n👉🏻 amzaff.in/1ZQZf7G',
    category: 'Deals',
    imageName: '@amazonindiaassociates_13756.jpg',
    status: 'scheduled',
    views: 1420,
    telegramClicks: 84,
    whatsappClicks: 32,
    links: ['amzaff.in/1ZQZf7G'],
    createdAt: new Date().toISOString(),
  },
  {
    id: 'post_seed_2',
    postNumber: 2,
    channel: 'Amazon_Associates_FashionBeauty',
    channelUsername: 'Amazon_Associates_FashionBeauty',
    time: '16:00',
    fullDateTime: new Date(Date.now() + 3600 * 1000 * 3.5).toISOString(),
    text: '✨ FASHION TRENDS OF THE WEEK\n\nGet up to 60% off on top branded footwear and accessories.\n\nShop here: amzaff.in/sd53Qad',
    category: 'Fashion',
    imageName: '@amazonindiaassociates_13758.jpg',
    status: 'scheduled',
    views: 890,
    telegramClicks: 45,
    whatsappClicks: 19,
    links: ['amzaff.in/sd53Qad'],
    createdAt: new Date().toISOString(),
  },
  {
    id: 'post_seed_3',
    postNumber: 3,
    channel: 'Amazon_Associates_HomeKitchen',
    channelUsername: 'Amazon_Associates_HomeKitchen',
    time: '18:15',
    fullDateTime: new Date(Date.now() + 3600 * 1000 * 5.75).toISOString(),
    text: '🍳 Kitchen Upgrade Fest!\n\nAir fryers, non-stick cookware & mixer grinders at best prices.\n\nCheck deal: amzaff.in/JTGc9BA',
    category: 'Home & Kitchen',
    imageName: '@amazonindiaassociates_13759.jpg',
    status: 'scheduled',
    views: 650,
    telegramClicks: 38,
    whatsappClicks: 12,
    links: ['amzaff.in/JTGc9BA'],
    createdAt: new Date().toISOString(),
  },
];

const INITIAL_WHATSAPP_POSTS: WhatsAppPost[] = [
  {
    id: 1,
    recipient_id: 'amazonindiaassociates',
    recipient_name: 'Amazon India Associates',
    recipient_phone: '120363408723243626@newsletter',
    message: '🔥 Flash Deal on Electronics: Save up to 40% on Smartwatches!\n\nTap to buy: amzaff.in/5n8NsAL',
    image_path: 'uploads/Post-1.jpeg',
    image_url: null,
    scheduled_at: new Date(Date.now() + 3600 * 1000 * 1.5).toISOString(),
    status: 'pending',
    attempts: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 2,
    recipient_id: 'fashion_beauty',
    recipient_name: 'Fashion & Beauty',
    recipient_phone: '120363400693925981@newsletter',
    message: '💄 Beauty Steals: Skincare essentials with instant coupon discounts.\n\namzaff.in/neZvUY8',
    image_path: null,
    image_url: null,
    scheduled_at: new Date(Date.now() + 3600 * 1000 * 4).toISOString(),
    status: 'pending',
    attempts: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

const INITIAL_LOGS: PostLogItem[] = [
  {
    id: 101,
    date: '2026-10-14',
    time: '19:30:00',
    channel: 'amazonindiaassociates',
    postNumber: 13756,
    views: 2450,
    telegramClicks: 142,
    whatsappClicks: 67,
    links: 'amzaff.in/sd53Qad',
    text: '🔥 Mega festive discounts live now!',
    status: 'Completed',
  },
  {
    id: 102,
    date: '2026-10-14',
    time: '17:15:00',
    channel: 'Amazon_Associates_FashionBeauty',
    postNumber: 13758,
    views: 1890,
    telegramClicks: 95,
    whatsappClicks: 41,
    links: 'amzaff.in/OhzaLRb',
    text: '👗 Ethnic wear flash sale starts 6 PM.',
    status: 'Completed',
  },
  {
    id: 103,
    date: '2026-10-14',
    time: '14:00:00',
    channel: 'Amazon_Associates_Consumables',
    postNumber: 13760,
    views: 1204,
    telegramClicks: 56,
    whatsappClicks: 22,
    links: 'amzaff.in/urDQgzB',
    text: '☕ Daily grocery & pantry super deals.',
    status: 'Completed',
  },
];

export const StorageService = {
  getScheduledPosts(): ScheduledPostRecord[] {
    try {
      const data = localStorage.getItem(KEYS.POSTS);
      if (!data) {
        this.saveScheduledPosts(INITIAL_SCHEDULED_POSTS);
        return INITIAL_SCHEDULED_POSTS;
      }
      return JSON.parse(data);
    } catch {
      return INITIAL_SCHEDULED_POSTS;
    }
  },

  saveScheduledPosts(posts: ScheduledPostRecord[]) {
    localStorage.setItem(KEYS.POSTS, JSON.stringify(posts));
  },

  addScheduledPosts(newPosts: ScheduledPostRecord[]) {
    const current = this.getScheduledPosts();
    const updated = [...newPosts, ...current];
    this.saveScheduledPosts(updated);
    return updated;
  },

  deleteScheduledPost(id: string) {
    const current = this.getScheduledPosts();
    const updated = current.filter(p => p.id !== id);
    this.saveScheduledPosts(updated);
    return updated;
  },

  getRecurringSchedules(): RecurringScheduleConfig[] {
    try {
      const data = localStorage.getItem(KEYS.RECURRING);
      return data ? JSON.parse(data) : [];
    } catch {
      return [];
    }
  },

  saveRecurringSchedules(schedules: RecurringScheduleConfig[]) {
    localStorage.setItem(KEYS.RECURRING, JSON.stringify(schedules));
  },

  addRecurringSchedule(schedule: RecurringScheduleConfig) {
    const current = this.getRecurringSchedules();
    const updated = [schedule, ...current];
    this.saveRecurringSchedules(updated);
    return updated;
  },

  toggleRecurringSchedule(id: string) {
    const current = this.getRecurringSchedules();
    const updated = current.map(s => (s.id === id ? { ...s, active: !s.active } : s));
    this.saveRecurringSchedules(updated);
    return updated;
  },

  deleteRecurringSchedule(id: string) {
    const current = this.getRecurringSchedules();
    const updated = current.filter(s => s.id !== id);
    this.saveRecurringSchedules(updated);
    return updated;
  },

  getWhatsAppRecipients(): WhatsAppRecipient[] {
    try {
      const data = localStorage.getItem(KEYS.WHATSAPP_RECIPIENTS);
      if (!data) {
        this.saveWhatsAppRecipients(DEFAULT_WHATSAPP_RECIPIENTS);
        return DEFAULT_WHATSAPP_RECIPIENTS;
      }
      return JSON.parse(data);
    } catch {
      return DEFAULT_WHATSAPP_RECIPIENTS;
    }
  },

  saveWhatsAppRecipients(recipients: WhatsAppRecipient[]) {
    localStorage.setItem(KEYS.WHATSAPP_RECIPIENTS, JSON.stringify(recipients));
  },

  updateWhatsAppRecipientPhone(id: string, phone: string) {
    const current = this.getWhatsAppRecipients();
    const updated = current.map(r => (r.id === id ? { ...r, phone } : r));
    this.saveWhatsAppRecipients(updated);
    return updated;
  },

  resetWhatsAppRecipients() {
    this.saveWhatsAppRecipients(DEFAULT_WHATSAPP_RECIPIENTS);
    return DEFAULT_WHATSAPP_RECIPIENTS;
  },

  getWhatsAppPosts(): WhatsAppPost[] {
    try {
      const data = localStorage.getItem(KEYS.WHATSAPP_POSTS);
      if (!data) {
        this.saveWhatsAppPosts(INITIAL_WHATSAPP_POSTS);
        return INITIAL_WHATSAPP_POSTS;
      }
      return JSON.parse(data);
    } catch {
      return INITIAL_WHATSAPP_POSTS;
    }
  },

  saveWhatsAppPosts(posts: WhatsAppPost[]) {
    localStorage.setItem(KEYS.WHATSAPP_POSTS, JSON.stringify(posts));
  },

  addWhatsAppPost(post: Omit<WhatsAppPost, 'id' | 'created_at' | 'updated_at' | 'attempts' | 'status'>): WhatsAppPost {
    const current = this.getWhatsAppPosts();
    const newPost: WhatsAppPost = {
      ...post,
      id: Date.now(),
      status: 'pending',
      attempts: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    const updated = [newPost, ...current];
    this.saveWhatsAppPosts(updated);
    return newPost;
  },

  updateWhatsAppPost(id: number, updates: Partial<WhatsAppPost>) {
    const current = this.getWhatsAppPosts();
    const updated = current.map(p =>
      p.id === id ? { ...p, ...updates, updated_at: new Date().toISOString() } : p
    );
    this.saveWhatsAppPosts(updated);
    return updated;
  },

  cancelWhatsAppPost(id: number) {
    return this.updateWhatsAppPost(id, { status: 'cancelled' });
  },

  deleteWhatsAppPost(id: number) {
    const current = this.getWhatsAppPosts();
    const updated = current.filter(p => p.id !== id);
    this.saveWhatsAppPosts(updated);
    return updated;
  },

  getSettings(): AppSettings {
    try {
      const data = localStorage.getItem(KEYS.SETTINGS);
      if (!data) {
        this.saveSettings(INITIAL_SETTINGS);
        return INITIAL_SETTINGS;
      }
      return JSON.parse(data);
    } catch {
      return INITIAL_SETTINGS;
    }
  },

  saveSettings(settings: AppSettings) {
    localStorage.setItem(KEYS.SETTINGS, JSON.stringify(settings));
  },

  getLogs(): PostLogItem[] {
    try {
      const data = localStorage.getItem(KEYS.LOGS);
      if (!data) {
        this.saveLogs(INITIAL_LOGS);
        return INITIAL_LOGS;
      }
      return JSON.parse(data);
    } catch {
      return INITIAL_LOGS;
    }
  },

  saveLogs(logs: PostLogItem[]) {
    localStorage.setItem(KEYS.LOGS, JSON.stringify(logs));
  },

  addLog(log: Omit<PostLogItem, 'id'>) {
    const current = this.getLogs();
    const newLog: PostLogItem = {
      ...log,
      id: Date.now(),
    };
    const updated = [newLog, ...current];
    this.saveLogs(updated);
    return updated;
  },
};
