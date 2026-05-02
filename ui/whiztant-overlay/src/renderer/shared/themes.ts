import type { ThemeName } from './ipc';

export type Theme = {
  name: string;
  pill: {
    // Capsule background + border — defines the body of the pill itself.
    bg: string;
    border: string;
    // Ink color per state (the dot/bars rendered on top of the capsule).
    idle: string;
    recording: string;
    thinking: string;
    speaking: string;
    agent: string;
    // Outer glow halo rendered as box-shadow.
    glow: string;
  };
  panel: {
    bg: string;
    border: string;
    headerBg: string;
    inputBg: string;
    userBubble: string;
    aiBubble: string;
    aiAccent: string;
    text: string;
    textMuted: string;
    accent: string;
    scrollThumb: string;
  };
};

// Palette philosophy: pure near-black surfaces, a single near-white ink for
// the pill and AI accent, and muted chromatic accents reserved for the user
// bubble + footer badges. No saturated color in the pill itself — this keeps
// the capsule feeling like a hardware status LED and the tune feeling like a
// physical notepad, not a web app.
export const themes: Record<ThemeName, Theme> = {
  onyx: {
    name: 'Onyx',
    pill: {
      bg: 'rgba(0,0,0,0.96)',
      border: 'rgba(255,255,255,0.10)',
      idle: '#EDEDED',
      recording: '#FFFFFF',
      thinking: '#C7C7C7',
      speaking: '#E6E6E6',
      agent: '#BDBDBD',
      glow: 'rgba(255,255,255,0.12)',
    },
    panel: {
      bg: 'rgba(6,6,7,0.94)',
      border: 'rgba(255,255,255,0.06)',
      headerBg: 'rgba(10,10,11,0.98)',
      inputBg: 'rgba(16,16,18,0.9)',
      userBubble: 'rgba(242,242,245,0.96)',
      aiBubble: 'rgba(22,22,24,0.82)',
      aiAccent: '#EDEDED',
      text: '#F5F5F7',
      textMuted: 'rgba(255,255,255,0.46)',
      accent: '#F5F5F7',
      scrollThumb: 'rgba(255,255,255,0.12)',
    },
  },
  graphite: {
    name: 'Graphite',
    pill: {
      bg: 'rgba(10,12,15,0.95)',
      border: 'rgba(255,255,255,0.09)',
      idle: '#D6DBE0',
      recording: '#FFFFFF',
      thinking: '#B8BFC8',
      speaking: '#D0D6DD',
      agent: '#A8AFB8',
      glow: 'rgba(220,226,232,0.14)',
    },
    panel: {
      bg: 'rgba(12,14,17,0.94)',
      border: 'rgba(255,255,255,0.06)',
      headerBg: 'rgba(16,18,22,0.98)',
      inputBg: 'rgba(22,25,30,0.9)',
      userBubble: 'rgba(232,236,239,0.95)',
      aiBubble: 'rgba(26,30,36,0.82)',
      aiAccent: '#D6DBE0',
      text: '#E8ECEF',
      textMuted: 'rgba(200,210,220,0.42)',
      accent: '#D6DBE0',
      scrollThumb: 'rgba(255,255,255,0.1)',
    },
  },
  porcelain: {
    name: 'Porcelain',
    pill: {
      bg: 'rgba(250,250,252,0.96)',
      border: 'rgba(0,0,0,0.10)',
      idle: '#0A0A0A',
      recording: '#000000',
      thinking: '#1A1A1A',
      speaking: '#0D0D0D',
      agent: '#2A2A2A',
      glow: 'rgba(0,0,0,0.18)',
    },
    panel: {
      bg: 'rgba(248,248,250,0.94)',
      border: 'rgba(0,0,0,0.08)',
      headerBg: 'rgba(244,244,247,0.98)',
      inputBg: 'rgba(255,255,255,0.9)',
      userBubble: '#111111',
      aiBubble: 'rgba(240,240,243,0.9)',
      aiAccent: '#1A1A1A',
      text: '#0A0A0A',
      textMuted: 'rgba(0,0,0,0.5)',
      accent: '#0A0A0A',
      scrollThumb: 'rgba(0,0,0,0.18)',
    },
  },
  midnight: {
    name: 'Midnight',
    pill: {
      bg: 'rgba(6,8,14,0.96)',
      border: 'rgba(170,190,240,0.14)',
      idle: '#C9D4FF',
      recording: '#FFFFFF',
      thinking: '#A9B5E6',
      speaking: '#C0CBF0',
      agent: '#9AA5D6',
      glow: 'rgba(170,190,240,0.14)',
    },
    panel: {
      bg: 'rgba(8,10,18,0.94)',
      border: 'rgba(140,160,220,0.08)',
      headerBg: 'rgba(12,14,24,0.98)',
      inputBg: 'rgba(18,22,36,0.9)',
      userBubble: 'rgba(220,230,255,0.95)',
      aiBubble: 'rgba(20,24,38,0.82)',
      aiAccent: '#BCCAFF',
      text: '#EEF2FF',
      textMuted: 'rgba(200,215,255,0.45)',
      accent: '#BCCAFF',
      scrollThumb: 'rgba(190,205,255,0.14)',
    },
  },
  ember: {
    name: 'Ember',
    pill: {
      bg: 'rgba(10,7,5,0.96)',
      border: 'rgba(240,210,170,0.14)',
      idle: '#F5E1C8',
      recording: '#FFFFFF',
      thinking: '#E8CDAC',
      speaking: '#F1DBBE',
      agent: '#D8B88D',
      glow: 'rgba(240,210,170,0.16)',
    },
    panel: {
      bg: 'rgba(14,10,8,0.94)',
      border: 'rgba(230,200,160,0.08)',
      headerBg: 'rgba(18,13,10,0.98)',
      inputBg: 'rgba(26,20,16,0.9)',
      userBubble: 'rgba(245,225,200,0.95)',
      aiBubble: 'rgba(28,22,18,0.82)',
      aiAccent: '#F0D5B2',
      text: '#F7EEDC',
      textMuted: 'rgba(230,210,180,0.45)',
      accent: '#F0D5B2',
      scrollThumb: 'rgba(240,210,170,0.16)',
    },
  },
};

// Onyx is the default — true-black pill, near-white ink, no chromatic glow.
export const defaultTheme: ThemeName = 'onyx';
