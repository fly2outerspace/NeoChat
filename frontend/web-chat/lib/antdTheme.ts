import { theme } from 'antd';

export const antdThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: '#3b82f6', // Tailwind sky-500
    colorInfo: '#3b82f6',
    borderRadius: 10,
    fontFamily: 'var(--font-geist-sans), system-ui, -apple-system, sans-serif',
    colorBgBase: '#0f172a', // slate-900
    colorBgContainer: '#111827', // slate-900-ish
    colorText: '#e5e7eb', // slate-200
    colorTextDescription: '#9ca3af', // slate-400
  },
  components: {
    Layout: {
      siderBg: '#0b1220',
      headerBg: '#0b1220',
      bodyBg: '#0f172a',
    },
    Menu: {
      darkItemBg: '#0b1220',
      darkItemSelectedBg: '#1d4ed8',
      darkItemSelectedColor: '#e5e7eb',
      itemBorderRadius: 8,
    },
    Button: {
      controlHeight: 36,
      borderRadius: 8,
    },
    Card: {
      borderRadius: 12,
      headerFontSize: 16,
      padding: 16,
    },
  },
};

