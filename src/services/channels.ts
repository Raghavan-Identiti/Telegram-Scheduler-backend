import { TelegramChannel, WhatsAppRecipient, AppSettings } from '../types';

export const CHANNELS: Record<string, TelegramChannel> = {
  amazonindiaassociates: {
    id: 'amazonindiaassociates',
    username: 'amazonindiaassociates',
    name: 'Amazon India Associates',
    sheetName: 'Amazon_India_Associates',
  },
  Amazon_Associates_FashionBeauty: {
    id: 'Amazon_Associates_FashionBeauty',
    username: 'Amazon_Associates_FashionBeauty',
    name: 'Fashion & Beauty',
    sheetName: 'Fashion_Beauty',
  },
  Amazon_Associates_HomeKitchen: {
    id: 'Amazon_Associates_HomeKitchen',
    username: 'Amazon_Associates_HomeKitchen',
    name: 'Home & Kitchen',
    sheetName: 'Home_Kitchen',
  },
  Amazon_Associates_Consumables: {
    id: 'Amazon_Associates_Consumables',
    username: 'Amazon_Associates_Consumables',
    name: 'Consumables',
    sheetName: 'Consumables',
  },
  amazoninfluencerprogramindia: {
    id: 'amazoninfluencerprogramindia',
    username: 'amazoninfluencerprogramindia',
    name: 'Amazon Influencer Program India',
    sheetName: 'Amazon Influencer Program India',
  },
};

export const DEFAULT_WHATSAPP_RECIPIENTS: WhatsAppRecipient[] = [
  {
    id: 'amazonindiaassociates',
    name: 'Amazon India Associates',
    phone: '120363408723243626@newsletter',
    subscribers: '@amazonindiaassociates',
    avatar: 'A',
    color: 'bg-amber-500',
  },
  {
    id: 'fashion_beauty',
    name: 'Fashion & Beauty',
    phone: '120363400693925981@newsletter',
    subscribers: '@amazon_fashion',
    avatar: 'F',
    color: 'bg-pink-500',
  },
  {
    id: 'whatsapp_deals_testing',
    name: 'WhatsApp Deals Testing',
    phone: '120363408723243626@newsletter',
    subscribers: 'Test Group',
    avatar: 'W',
    color: 'bg-emerald-500',
  },
  {
    id: 'bhajan_marg',
    name: 'Bhajan Marg',
    phone: '120363178482495644@newsletter',
    subscribers: 'Community',
    avatar: 'B',
    color: 'bg-orange-500',
  },
  {
    id: 'jayam_sk_gopi',
    name: 'Jayam SK Gopi (முருகன்)',
    phone: '120363311931035694@newsletter',
    subscribers: 'Spiritual Channel',
    avatar: 'J',
    color: 'bg-red-500',
  },
  {
    id: 'manguni_gamer',
    name: 'Manguni Gamer',
    phone: '120363163312669944@newsletter',
    subscribers: 'Gaming Network',
    avatar: 'M',
    color: 'bg-purple-500',
  },
  {
    id: 'thinkcraft_academy',
    name: 'Thinkcraft Academy',
    phone: '120363420592093827@newsletter',
    subscribers: 'Education Guild',
    avatar: 'T',
    color: 'bg-blue-500',
  },
  {
    id: 'art_of_living',
    name: 'Art of Living Meditation',
    phone: '120363162744866869@newsletter',
    subscribers: 'Meditation Challenge',
    avatar: 'O',
    color: 'bg-teal-500',
  },
];

export const INITIAL_SETTINGS: AppSettings = {
  auto_fetch_enabled: true,
  channel_sheets: {
    amazonindiaassociates: {
      sheet_id: '1seb2pGu1XekQmNcHC-6Ma_y9tGRyhTo33PrR8sA-EBc',
      sheet_url: 'https://docs.google.com/spreadsheets/d/1seb2pGu1XekQmNcHC-6Ma_y9tGRyhTo33PrR8sA-EBc',
      sheet_tab: 'Amazon_India_Associates',
    },
    Amazon_Associates_FashionBeauty: {
      sheet_id: '1seb2pGu1XekQmNcHC-6Ma_y9tGRyhTo33PrR8sA-EBc',
      sheet_url: 'https://docs.google.com/spreadsheets/d/1seb2pGu1XekQmNcHC-6Ma_y9tGRyhTo33PrR8sA-EBc',
      sheet_tab: 'Fashion_Beauty',
    },
    Amazon_Associates_HomeKitchen: {
      sheet_id: '1seb2pGu1XekQmNcHC-6Ma_y9tGRyhTo33PrR8sA-EBc',
      sheet_url: 'https://docs.google.com/spreadsheets/d/1seb2pGu1XekQmNcHC-6Ma_y9tGRyhTo33PrR8sA-EBc',
      sheet_tab: 'Home_Kitchen',
    },
    Amazon_Associates_Consumables: {
      sheet_id: '1seb2pGu1XekQmNcHC-6Ma_y9tGRyhTo33PrR8sA-EBc',
      sheet_url: 'https://docs.google.com/spreadsheets/d/1seb2pGu1XekQmNcHC-6Ma_y9tGRyhTo33PrR8sA-EBc',
      sheet_tab: 'Consumables',
    },
  },
  google_sheets_connected: true,
  whatsapp_connected: true,
  telegram_connected: true,
};
