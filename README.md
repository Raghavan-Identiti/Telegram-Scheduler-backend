# TeleQueue - Telegram & WhatsApp Channel Scheduler

TeleQueue is an automated multi-channel scheduling, dispatch, recurrence management, and conversion analytics platform for Telegram channels and WhatsApp newsletter broadcast groups (Amazon Associates, Amazon Influencers, Fashion & Beauty, Home & Kitchen, Consumables, and spiritual/community networks).

## Features

- **Auto Scheduler & Bulk Upload**:
  - Automatically parses `.txt` files containing numbered deals and affiliate links (`amzaff.in/...`).
  - Matches post images (`post1.jpg`, `post2.png`, etc.) to corresponding text blocks.
  - Generates 5-minute time slots in IST (Asia/Kolkata) with conflict avoidance.
  - Auto-distributes or applies fixed interval spacing (15m, 30m, 45m, 60m).
  - Validates Telegram message limits (1024-character caption limit with warning / split previews).
- **Recurring Scheduler**:
  - Daily recurrence with multiple custom execution times per day.
  - Weekly recurrence with day-of-week selection (Mon–Sun) and custom times per day.
  - Configurable max occurrences ("stop after X executions").
  - Automatic skip of blocked time slots.
- **WhatsApp Hub & Scheduler**:
  - Direct management of WhatsApp target newsletters (Amazon India Associates, Fashion & Beauty, etc.).
  - Schedule, edit, cancel, and immediately test message dispatches.
  - Pair via Baileys Web QR authentication.
- **Post Analytics & Clicks Tracker**:
  - Single-date breakdown and 31-day date range analysis.
  - Clicks tracking across Telegram and WhatsApp channels.
  - Direct Excel export (`.xlsx`) matching the original logging format.
- **Logs & Google Sheets Sync**:
  - History viewer for `post_logs.xlsx` with spreadsheet download.
  - Per-channel Google Sheet ID, URL, and Tab name configuration.
  - Daily 6:00 AM IST Auto-Fetch toggle for automated sync.

## Tech Stack

- **Framework**: React 19 + TypeScript + Vite
- **Styling**: Tailwind CSS v4
- **Spreadsheet / Export Engine**: SheetJS (`xlsx`)
- **Icons**: Lucide React
- **Date Handling**: Date-fns & Intl IST Localization

## Development

```bash
npm run dev
```

Build for production:

```bash
npm run build
```
