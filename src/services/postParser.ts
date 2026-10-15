import { ParsedPost } from '../types';

export const MAX_CAPTION_LENGTH = 1024;
export const CAPTION_SAFETY_BUFFER = 50;
export const MAX_TEXT_LENGTH = 4096;

/**
 * Extract URLs including amzaff.in short links from text
 */
export function extractLinks(text: string): string[] {
  if (!text) return [];
  // Regex to match http links or amzaff.in links, even if surrounded by * or **
  const urlPattern = /[*_()<>]*\b(https?:\/\/\S+|amzaff\.in\/\S+)\b[*_()<>.]*/gi;
  const matches = text.match(urlPattern) || [];
  
  return matches
    .map(link => link.replace(/^[*_()<>]+|[*_()<>.,!?]+$/g, '').trim())
    .filter(link => link.length > 0);
}

/**
 * Validate and compute safe caption vs split text according to Telegram limits
 */
export function validateCaption(text: string): {
  canUseAsCaption: boolean;
  length: number;
  exceedsBy: number;
  safeCaption: string;
  remainingText: string;
} {
  if (!text) {
    return {
      canUseAsCaption: true,
      length: 0,
      exceedsBy: 0,
      safeCaption: '',
      remainingText: '',
    };
  }

  const trimmed = text.trim();
  const safeLimit = MAX_CAPTION_LENGTH - CAPTION_SAFETY_BUFFER;

  if (trimmed.length <= safeLimit) {
    return {
      canUseAsCaption: true,
      length: trimmed.length,
      exceedsBy: 0,
      safeCaption: trimmed,
      remainingText: '',
    };
  }

  // Find natural break point
  let truncateAt = safeLimit;
  for (let i = safeLimit - 100; i < safeLimit; i++) {
    if (i < trimmed.length && ['.', '!', '?', '\n'].includes(trimmed[i])) {
      truncateAt = i + 1;
      break;
    }
  }

  if (truncateAt === safeLimit) {
    for (let i = safeLimit - 50; i < safeLimit; i++) {
      if (i < trimmed.length && trimmed[i] === ' ') {
        truncateAt = i;
        break;
      }
    }
  }

  return {
    canUseAsCaption: false,
    length: trimmed.length,
    exceedsBy: trimmed.length - safeLimit,
    safeCaption: trimmed.slice(0, truncateAt).trim(),
    remainingText: trimmed.slice(truncateAt).trim(),
  };
}

/**
 * Port of Python extract_all_posts_from_texts
 * Matches: post-1, Post 1, **post-1**, POST_1, etc.
 * Supports AMZ_TELEGRAM prefix, category: <val>, and time: HH:MM
 */
export function extractAllPostsFromTexts(textBlocks: string[]): Record<number, { text: string; category?: string | null; customTime?: string | null }> {
  const posts: Record<number, { text: string; category?: string | null; customTime?: string | null }> = {};

  const postStartRegex = /(?:^|\n)\s*(?:\*{0,2})\s*post\s*[-_\s]*(\d+)\s*(?:\*{0,2})\s*(?:\n|$)/gi;
  const sectionStartRegex = /AMZ_TELEGRAM/i;
  const timeRegex = /(?:^|\n)\s*time\s*[:\-=]\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*(?:am|pm)?\s*(?:\n|$)/i;

  for (let text of textBlocks) {
    const secMatch = text.search(sectionStartRegex);
    if (secMatch !== -1) {
      text = text.substring(secMatch + 12);
    }

    // Collect all post starts
    const startMatches: { postNum: number; startPos: number; index: number }[] = [];
    let match: RegExpExecArray | null;
    postStartRegex.lastIndex = 0;
    while ((match = postStartRegex.exec(text)) !== null) {
      startMatches.push({
        postNum: parseInt(match[1], 10),
        startPos: match.index + match[0].length,
        index: match.index,
      });
    }

    for (let i = 0; i < startMatches.length; i++) {
      const { postNum, startPos } = startMatches[i];
      let endPos = text.length;

      // Look for specific end pattern: post <num> end / done / copy
      const specificEndRegex = new RegExp(
        `(?:^|\\n)\\s*(?:\\*{0,2})\\s*post\\s*[-_\\s]*${postNum}\\s*(?:end|copy|copies?|finish|done)\\s*(?:\\*{0,2})\\s*(?:\\n|$)`,
        'i'
      );
      const remainingText = text.slice(startPos);
      const endMatch = remainingText.search(specificEndRegex);

      if (endMatch !== -1) {
        endPos = startPos + endMatch;
      } else if (i + 1 < startMatches.length) {
        endPos = startMatches[i + 1].index;
      }

      const content = text.slice(startPos, endPos);
      const lines = content.split(/\r?\n/);
      let category: string | null = null;
      let customTime: string | null = null;
      const textLines: string[] = [];

      for (const line of lines) {
        const stripped = line.trim();
        if (stripped.toLowerCase().startsWith('category:')) {
          category = stripped.slice(9).trim();
          continue;
        }

        const tMatch = line.match(timeRegex);
        if (tMatch) {
          customTime = tMatch[1].trim();
          continue;
        }

        textLines.push(line);
      }

      const cleanText = textLines.join('\n').trim();

      posts[postNum] = {
        category,
        text: cleanText,
        customTime,
      };
    }
  }

  return posts;
}

/**
 * Match image file names to post numbers, e.g. "post1.jpg", "post-2.png", "Post_3.jpeg"
 */
export function extractPostNumberFromFilename(filename: string): number | null {
  const cleanName = filename.toLowerCase();
  const match = cleanName.match(/(?:\*{0,2})\s*post\s*[-_\s]*(\d+)/i);
  if (match) {
    return parseInt(match[1], 10);
  }
  return null;
}
