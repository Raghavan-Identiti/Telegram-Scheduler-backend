import { TimeSlot, DayOfWeek, RecurrenceType } from '../types';

/**
 * Rounds time to nearest 5-minute mark
 * 10:27 -> 10:25
 * 10:28 -> 10:30
 */
export function roundToNearest5(date: Date): Date {
  const result = new Date(date);
  result.setSeconds(0, 0);
  const minutes = result.getMinutes();
  const remainder = minutes % 5;
  if (remainder < 3) {
    result.setMinutes(minutes - remainder);
  } else {
    result.setMinutes(minutes + (5 - remainder));
  }
  return result;
}

export function formatTime24(date: Date): string {
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  return `${hours}:${minutes}`;
}

export function formatDateTimeIST(date: Date): string {
  return date.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  });
}

/**
 * Generate 5-minute slots between start and end time
 */
export function generate5MinGrid(startTime: Date, endTime: Date): Date[] {
  const slots: Date[] = [];
  const current = roundToNearest5(new Date(startTime));
  const end = roundToNearest5(new Date(endTime));

  while (current <= end) {
    slots.push(new Date(current));
    current.setMinutes(current.getMinutes() + 5);
  }
  return slots;
}

/**
 * Parse custom time string like "14:30", "2:30 PM", "08:15:00" and combine with base date
 */
export function parseCustomTime(timeStr: string, baseDate: Date): Date | null {
  if (!timeStr) return null;
  const clean = timeStr.trim();
  let isPM = false;
  let isAM = false;

  let timePart = clean;
  if (clean.toLowerCase().endsWith('pm')) {
    isPM = true;
    timePart = clean.slice(0, -2).trim();
  } else if (clean.toLowerCase().endsWith('am')) {
    isAM = true;
    timePart = clean.slice(0, -2).trim();
  }

  const parts = timePart.split(':');
  if (parts.length < 2) return null;

  let hours = parseInt(parts[0], 10);
  const minutes = parseInt(parts[1], 10);

  if (isNaN(hours) || isNaN(minutes) || hours < 0 || hours > 23 || minutes < 0 || minutes > 59) {
    return null;
  }

  if (isPM && hours !== 12) {
    hours += 12;
  } else if (isAM && hours === 12) {
    hours = 0;
  }

  const result = new Date(baseDate);
  result.setHours(hours, minutes, 0, 0);
  return roundToNearest5(result);
}

const DAY_MAPPING: Record<DayOfWeek, number> = {
  M: 1,  // Monday
  T: 2,  // Tuesday
  W: 3,  // Wednesday
  TH: 4, // Thursday
  F: 5,  // Friday
  S: 6,  // Saturday
  SU: 0, // Sunday
};

/**
 * Generate recurring dates for daily or weekly schedules
 */
export function generateRecurringDates(
  type: RecurrenceType,
  startDateStr: string,
  endDateStr?: string,
  dailyTimes: TimeSlot[] = [],
  weeklyDays: DayOfWeek[] = [],
  weeklyTimesPerDay: Record<string, TimeSlot[]> = {},
  maxOccurrences?: number
): Date[] {
  const scheduleTimes: Date[] = [];
  const start = new Date(`${startDateStr}T00:00:00`);
  const now = new Date();
  
  let end: Date;
  if (endDateStr) {
    end = new Date(`${endDateStr}T23:59:59`);
  } else {
    end = new Date(start);
    end.setDate(end.getDate() + 90); // default 90 days
  }

  let occurrenceCount = 0;

  if (type === 'daily') {
    const current = new Date(start);
    while (current <= end) {
      for (const slot of dailyTimes) {
        if (maxOccurrences && occurrenceCount >= maxOccurrences) {
          return scheduleTimes.sort((a, b) => a.getTime() - b.getTime());
        }

        const scheduledTime = new Date(current);
        scheduledTime.setHours(slot.hour, slot.minute, 0, 0);
        
        if (scheduledTime > now) {
          scheduleTimes.push(scheduledTime);
          occurrenceCount++;
        }
      }
      current.setDate(current.getDate() + 1);
    }
  } else if (type === 'weekly') {
    const current = new Date(start);
    while (current <= end) {
      const currentDayNum = current.getDay();

      for (const day of weeklyDays) {
        const targetDayNum = DAY_MAPPING[day];
        if (currentDayNum === targetDayNum) {
          const slotsForDay = weeklyTimesPerDay[day] || [];
          for (const slot of slotsForDay) {
            if (maxOccurrences && occurrenceCount >= maxOccurrences) {
              return scheduleTimes.sort((a, b) => a.getTime() - b.getTime());
            }

            const scheduledTime = new Date(current);
            scheduledTime.setHours(slot.hour, slot.minute, 0, 0);

            if (scheduledTime > now) {
              scheduleTimes.push(scheduledTime);
              occurrenceCount++;
            }
          }
        }
      }
      current.setDate(current.getDate() + 1);
    }
  }

  return scheduleTimes.sort((a, b) => a.getTime() - b.getTime());
}
