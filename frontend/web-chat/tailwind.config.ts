import type { Config } from 'tailwindcss';

const config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  // IMPORTANT: When adding new color styles in themes.ts (bg-[#...], text-[#...], border-[#...], shadow-[...]),
  // you MUST add them to this safelist to ensure Tailwind CSS includes them in the generated CSS.
  // Otherwise, the styles will not be applied at runtime.
  safelist: [
    'bg-[#240A27]',
    'bg-[#10182A]/85',
    'bg-[#223B57]',
    'bg-[#241E1A]',
    'bg-[#2F0B32]',
    'bg-[#1A0F1A]', // COMMAND mode background
    'bg-[#302822]',
    'bg-[#194E40]',
    'bg-[#10182A]',
    'text-[#EFB5FF]',
    'text-[#D8E4FF]',
    'text-[#F2FAFF]',
    'text-[#F4E7CE]',
    'text-[#F6C9FF]',
    'text-[#FFD700]', // COMMAND mode gold text
    'text-[#F8ECD6]',
    'text-[#E8FFF6]',
    'border',
    'border-[#3A0F3F]',
    'border-[#1F2D45]/70',
    'border-[#335577]',
    'border-[#3A3029]',
    'border-[#47104A]',
    'border-[#3A1F3A]', // COMMAND mode border
    'border-[#43372F]',
    'border-[#296F5C]',
    'border-[#1F2D45]',
    'shadow-[0_0_10px_rgba(239,181,255,0.15)]',
    'shadow-[0_0_8px_rgba(242,250,255,0.12)]',
    'shadow-[0_0_8px_rgba(244,231,206,0.1)]',
    'shadow-[0_0_10px_rgba(246,201,255,0.16)]',
    'shadow-[0_0_12px_rgba(255,215,0,0.25)]', // COMMAND mode gold shadow
    'shadow-[0_0_10px_rgba(248,236,214,0.15)]',
    'shadow-[0_0_9px_rgba(232,255,246,0.14)]',
    'shadow-[0_0_8px_rgba(216,228,255,0.12)]',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
} satisfies Config;

export default config;

