import { InputMode } from './enums';
import type { ThemeId } from './config';

/**
 * Chat theme configuration
 * Defines color classes for different message types and tool outputs
 * 
 * IMPORTANT: When adding new color styles (bg-[#...], text-[#...], border-[#...], shadow-[...]),
 * you MUST also add them to the safelist in tailwind.config.ts to ensure Tailwind CSS
 * includes these classes in the generated CSS. Otherwise, the styles will not be applied.
 */
export interface ChatTheme {
  toolBubbles: {
    reflectionBg: string;
    reflectionLabel: string;
    reflectionContent: string;
    defaultBg: string;
    defaultLabel: string;
    defaultContent: string;
  };
  userBubbles: {
    [InputMode.PHONE]: string;
    [InputMode.IN_PERSON]: string;
    [InputMode.INNER_VOICE]: string;
    [InputMode.COMMAND]: string;
    [InputMode.SKIP]?: string; // Skip mode doesn't create bubbles, but included for type safety
    [InputMode.NEW_MODE_2]?: string;
    [InputMode.NEW_MODE_3]?: string;
    default: string;
  };
  assistantBubbles: {
    speakInPerson: string;
    telegram: string;
    default: string;
  };
}

export interface ChatThemeOption {
  id: ThemeId;
  name: string;
  description: string;
  theme: ChatTheme;
}

const cyberNoirTheme: ChatTheme = {
  toolBubbles: {
    // Reflection (内心想法) - Neon magenta
    reflectionBg: 'bg-[#240A27] text-[#EFB5FF] border border-[#3A0F3F] shadow-[0_0_10px_rgba(239,181,255,0.15)]',
    reflectionLabel: 'text-[#EFB5FF]',
    reflectionContent: 'text-[#EFB5FF]',
    // Default tool bubbles - Blue-gray glow
    defaultBg: 'bg-[#10182A]/85 text-[#D8E4FF] border border-[#1F2D45]/70 shadow-[0_0_8px_rgba(216,228,255,0.12)]',
    defaultLabel: 'text-[#D8E4FF]',
    defaultContent: 'text-[#D8E4FF]',
  },
  userBubbles: {
    [InputMode.PHONE]: 'bg-[#223B57] text-[#F2FAFF] border border-[#335577] shadow-[0_0_8px_rgba(242,250,255,0.12)]', // Telegram blue
    [InputMode.IN_PERSON]: 'bg-[#241E1A] text-[#F4E7CE] border border-[#3A3029] shadow-[0_0_8px_rgba(244,231,206,0.1)]', // Warm print tones
    [InputMode.INNER_VOICE]: 'bg-[#2F0B32] text-[#F6C9FF] border border-[#47104A] shadow-[0_0_10px_rgba(246,201,255,0.16)]', // Neon magenta
    [InputMode.COMMAND]: 'bg-[#1A0F1A] text-[#FFD700] border border-[#3A1F3A] shadow-[0_0_12px_rgba(255,215,0,0.25)]', // System command - Deep purple with gold accent (cyberpunk style)
    default: 'bg-sky-600 text-white', // Default blue
  },
  assistantBubbles: {
    speakInPerson: 'bg-[#302822] text-[#F8ECD6] border border-[#43372F] shadow-[0_0_10px_rgba(248,236,214,0.15)]', // Warm print palette
    telegram: 'bg-[#194E40] text-[#E8FFF6] border border-[#296F5C] shadow-[0_0_9px_rgba(232,255,246,0.14)]', // Emerald chat palette
    default: 'bg-[#10182A] text-[#D8E4FF] border border-[#1F2D45] shadow-[0_0_8px_rgba(216,228,255,0.12)]', // Blue-gray glow
  },
};

export const CHAT_THEMES: Record<ThemeId, ChatThemeOption> = {
  'cyber-noir': {
    id: 'cyber-noir',
    name: '赛博夜行',
    description: '冷色赛博蓝 + 霓虹洋红高光，搭配暖色正文输出',
    theme: cyberNoirTheme,
  },
};

export function getChatTheme(themeId: ThemeId): ChatTheme {
  return CHAT_THEMES[themeId]?.theme ?? CHAT_THEMES['cyber-noir'].theme;
}

