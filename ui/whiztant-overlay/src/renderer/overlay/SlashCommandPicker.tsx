import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Theme } from '../shared/themes';

export type SlashCommand = {
  id: string;
  label: string;
  description: string;
  category: string;
};

export const IMPPECCABLE_COMMANDS: SlashCommand[] = [
  { id: 'craft', label: '/impeccable craft', description: 'Shape, then build a feature end-to-end', category: 'Build' },
  { id: 'shape', label: '/impeccable shape', description: 'Plan UX/UI before writing code', category: 'Build' },
  { id: 'teach', label: '/impeccable teach', description: 'Set up PRODUCT.md and DESIGN.md context', category: 'Build' },
  { id: 'document', label: '/impeccable document', description: 'Generate DESIGN.md from existing project code', category: 'Build' },
  { id: 'extract', label: '/impeccable extract', description: 'Pull reusable tokens and components into design system', category: 'Build' },
  { id: 'critique', label: '/impeccable critique', description: 'UX design review with heuristic scoring', category: 'Evaluate' },
  { id: 'audit', label: '/impeccable audit', description: 'Technical quality checks (a11y, perf, responsive)', category: 'Evaluate' },
  { id: 'polish', label: '/impeccable polish', description: 'Final quality pass before shipping', category: 'Refine' },
  { id: 'bolder', label: '/impeccable bolder', description: 'Amplify safe or bland designs', category: 'Refine' },
  { id: 'quieter', label: '/impeccable quieter', description: 'Tone down aggressive or overstimulating designs', category: 'Refine' },
  { id: 'distill', label: '/impeccable distill', description: 'Strip to essence, remove complexity', category: 'Refine' },
  { id: 'harden', label: '/impeccable harden', description: 'Production-ready: errors, i18n, edge cases', category: 'Refine' },
  { id: 'onboard', label: '/impeccable onboard', description: 'Design first-run flows, empty states, activation', category: 'Refine' },
  { id: 'animate', label: '/impeccable animate', description: 'Add purposeful animations and motion', category: 'Enhance' },
  { id: 'colorize', label: '/impeccable colorize', description: 'Add strategic color to monochromatic UIs', category: 'Enhance' },
  { id: 'typeset', label: '/impeccable typeset', description: 'Improve typography hierarchy and fonts', category: 'Enhance' },
  { id: 'layout', label: '/impeccable layout', description: 'Fix spacing, rhythm, and visual hierarchy', category: 'Enhance' },
  { id: 'delight', label: '/impeccable delight', description: 'Add personality and memorable touches', category: 'Enhance' },
  { id: 'overdrive', label: '/impeccable overdrive', description: 'Push past conventional limits', category: 'Enhance' },
  { id: 'clarify', label: '/impeccable clarify', description: 'Improve UX copy, labels, and error messages', category: 'Fix' },
  { id: 'adapt', label: '/impeccable adapt', description: 'Adapt for different devices and screen sizes', category: 'Fix' },
  { id: 'optimize', label: '/impeccable optimize', description: 'Diagnose and fix UI performance', category: 'Fix' },
  { id: 'live', label: '/impeccable live', description: 'Visual variant mode: pick elements in the browser', category: 'Iterate' },
];

const CATEGORY_COLORS: Record<string, string> = {
  Build: '#c0c1ff',
  Evaluate: '#4cd7f6',
  Refine: '#d0bcff',
  Enhance: '#fbbf24',
  Fix: '#f87171',
  Iterate: '#34d399',
};

type Props = {
  theme: Theme['panel'];
  query: string;
  onSelect: (command: SlashCommand) => void;
  onClose: () => void;
};

export default function SlashCommandPicker({ theme, query, onSelect, onClose }: Props) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const filtered = query.length <= 1
    ? IMPPECCABLE_COMMANDS
    : IMPPECCABLE_COMMANDS.filter((c) =>
        c.id.toLowerCase().includes(query.slice(1).toLowerCase()) ||
        c.description.toLowerCase().includes(query.slice(1).toLowerCase())
      );

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    const el = itemRefs.current[selectedIndex];
    if (el) {
      el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [selectedIndex]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((i) => (i + 1) % filtered.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((i) => (i - 1 + filtered.length) % filtered.length);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const cmd = filtered[selectedIndex];
        if (cmd) onSelect(cmd);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [filtered, selectedIndex, onSelect, onClose]);

  if (filtered.length === 0) return null;

  return (
    <motion.div
      ref={listRef}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 6 }}
      transition={{ duration: 0.15 }}
      style={{
        position: 'absolute',
        bottom: '100%',
        left: 0,
        right: 0,
        marginBottom: 6,
        maxHeight: 260,
        overflowY: 'auto',
        background: theme.headerBg,
        border: `1px solid ${theme.border}`,
        borderRadius: 10,
        padding: '6px 4px',
        zIndex: 50,
        boxShadow: '0 8px 24px rgba(0,0,0,0.35)',
      }}
    >
      {filtered.map((cmd, idx) => {
        const isSelected = idx === selectedIndex;
        const catColor = CATEGORY_COLORS[cmd.category] ?? theme.textMuted;
        return (
          <button
            key={cmd.id}
            ref={(el) => { itemRefs.current[idx] = el; }}
            onMouseEnter={() => setSelectedIndex(idx)}
            onClick={() => onSelect(cmd)}
            style={{
              width: '100%',
              textAlign: 'left',
              padding: '7px 10px',
              borderRadius: 8,
              border: 'none',
              background: isSelected ? `${theme.accent}22` : 'transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              outline: 'none',
            }}
          >
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                color: catColor,
                minWidth: 60,
                flexShrink: 0,
              }}
            >
              {cmd.category}
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 0 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: theme.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {cmd.label}
              </span>
              <span style={{ fontSize: 11, color: theme.textMuted, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {cmd.description}
              </span>
            </div>
          </button>
        );
      })}
    </motion.div>
  );
}
