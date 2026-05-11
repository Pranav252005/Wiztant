import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Theme } from './themes';

export interface DropdownOption {
  value: string;
  label: string;
  recommended_for?: string;
  icon?: React.ReactNode;
  category?: string;
}

interface CustomDropdownProps {
  value: string;
  onChange: (value: string) => void;
  options: DropdownOption[];
  theme: Theme['panel'];
  label?: string;
  placeholder?: string;
  grouped?: boolean;
  showRecommendedFor?: boolean;
  disabled?: boolean;
  id?: string;
  style?: React.CSSProperties;
}

export default function CustomDropdown({
  value,
  onChange,
  options,
  theme,
  label,
  placeholder = 'Select…',
  grouped = false,
  showRecommendedFor = false,
  disabled = false,
  id,
  style,
}: CustomDropdownProps) {
  const [open, setOpen] = useState(false);
  const [highlightedIdx, setHighlightedIdx] = useState(-1);
  const [search, setSearch] = useState('');
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const flatOptions = useMemo(() => {
    if (!grouped) return options;
    const cats = new Map<string, DropdownOption[]>();
    for (const opt of options) {
      const cat = opt.category || 'Other';
      if (!cats.has(cat)) cats.set(cat, []);
      cats.get(cat)!.push(opt);
    }
    const out: (DropdownOption | { type: 'header'; label: string; value: string })[] = [];
    for (const [cat, items] of cats) {
      out.push({ type: 'header', label: cat, value: `__header_${cat}` });
      out.push(...items);
    }
    return out;
  }, [options, grouped]);

  const isHeader = (opt: unknown): opt is { type: 'header'; label: string; value: string } =>
    typeof opt === 'object' && opt !== null && 'type' in opt && (opt as Record<string, unknown>).type === 'header';

  const selectableOptions = useMemo(
    () => flatOptions.filter((o): o is DropdownOption => !isHeader(o)),
    [flatOptions]
  );

  const selectedOption = useMemo(
    () => selectableOptions.find((o) => o.value === value) || null,
    [selectableOptions, value]
  );

  const idxOf = useCallback(
    (val: string) => selectableOptions.findIndex((o) => o.value === val),
    [selectableOptions]
  );

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  // Focus list when opened
  useEffect(() => {
    if (open && listRef.current) {
      listRef.current.focus();
      const selIdx = idxOf(value);
      setHighlightedIdx(selIdx >= 0 ? selIdx : 0);
    }
  }, [open, value, idxOf]);

  // Reset search after inactivity
  useEffect(() => {
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    if (search) {
      searchTimeoutRef.current = setTimeout(() => setSearch(''), 500);
    }
    return () => {
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    };
  }, [search]);

  const scrollToHighlighted = useCallback((idx: number) => {
    if (!listRef.current) return;
    const el = listRef.current.children[idx] as HTMLElement | undefined;
    if (el) {
      el.scrollIntoView({ block: 'nearest' });
    }
  }, []);

  const moveHighlight = useCallback(
    (delta: number) => {
      setHighlightedIdx((prev) => {
        let next = prev + delta;
        const max = selectableOptions.length - 1;
        if (next < 0) next = max;
        if (next > max) next = 0;
        // Skip headers when navigating
        const item = flatOptions[next];
        if (isHeader(item)) {
          next += delta >= 0 ? 1 : -1;
          if (next < 0) next = max;
          if (next > max) next = 0;
        }
        requestAnimationFrame(() => scrollToHighlighted(next));
        return next;
      });
    },
    [selectableOptions.length, flatOptions, scrollToHighlighted]
  );

  const selectValue = useCallback(
    (val: string) => {
      onChange(val);
      setOpen(false);
      triggerRef.current?.focus();
    },
    [onChange]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (disabled) return;

      if (!open) {
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          setOpen(true);
          return;
        }
        if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
          // type-to-open
          setOpen(true);
          setSearch(e.key.toLowerCase());
          return;
        }
        return;
      }

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          moveHighlight(1);
          break;
        case 'ArrowUp':
          e.preventDefault();
          moveHighlight(-1);
          break;
        case 'Enter':
          e.preventDefault();
          if (highlightedIdx >= 0 && highlightedIdx < selectableOptions.length) {
            selectValue(selectableOptions[highlightedIdx].value);
          }
          break;
        case 'Escape':
          e.preventDefault();
          setOpen(false);
          triggerRef.current?.focus();
          break;
        case 'Home':
          e.preventDefault();
          setHighlightedIdx(0);
          scrollToHighlighted(0);
          break;
        case 'End':
          e.preventDefault();
          setHighlightedIdx(selectableOptions.length - 1);
          scrollToHighlighted(selectableOptions.length - 1);
          break;
        default:
          if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
            const nextSearch = (search + e.key).toLowerCase();
            setSearch(nextSearch);
            const matchIdx = selectableOptions.findIndex((o) =>
              o.label.toLowerCase().startsWith(nextSearch)
            );
            if (matchIdx >= 0) {
              setHighlightedIdx(matchIdx);
              scrollToHighlighted(matchIdx);
            }
          }
          break;
      }
    },
    [open, disabled, moveHighlight, highlightedIdx, selectableOptions, selectValue, search, scrollToHighlighted]
  );

  const triggerId = id ?? 'wiz-dropdown-trigger';
  const listId = `${triggerId}-list`;

  return (
    <div ref={containerRef} style={{ display: 'flex', flexDirection: 'column', gap: 4, ...style }}>
      {label && (
        <label
          htmlFor={triggerId}
          style={{ fontSize: 10, color: theme.textMuted, fontWeight: 500 }}
        >
          {label}
        </label>
      )}
      <button
        ref={triggerRef}
        id={triggerId}
        type="button"
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={listId}
        aria-activedescendant={
          open && highlightedIdx >= 0 ? `${triggerId}-opt-${highlightedIdx}` : undefined
        }
        disabled={disabled}
        onClick={() => {
          if (!disabled) setOpen((v) => !v);
        }}
        onKeyDown={handleKeyDown}
        style={{
          width: '100%',
          padding: '8px 10px',
          borderRadius: 12,
          border: `1px solid ${theme.border}`,
          background: theme.inputBg,
          color: theme.text,
          fontSize: 12,
          fontFamily: 'inherit',
          outline: 'none',
          cursor: disabled ? 'not-allowed' : 'pointer',
          textAlign: 'left',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
          opacity: disabled ? 0.5 : 1,
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 8, overflow: 'hidden' }}>
          {selectedOption?.icon && (
            <span style={{ flexShrink: 0, display: 'flex', alignItems: 'center', color: theme.textMuted }}>
              {selectedOption.icon}
            </span>
          )}
          <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {selectedOption?.label ?? placeholder}
          </span>
        </span>
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            flexShrink: 0,
            color: theme.textMuted,
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 150ms ease-out',
          }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {showRecommendedFor && selectedOption?.recommended_for && (
        <span style={{ fontSize: 12, color: theme.textMuted, marginTop: 4, lineHeight: 1.4 }}>
          {selectedOption.recommended_for}
        </span>
      )}

      <AnimatePresence>
        {open && (
          <motion.div
            id={listId}
            ref={listRef}
            role="listbox"
            tabIndex={-1}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.15, ease: 'easeOut' }}
            style={{
              overflow: 'hidden',
              borderRadius: 8,
              background: theme.inputBg,
              border: `1px solid ${theme.border}`,
              boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
              zIndex: 100,
              maxHeight: 280,
              overflowY: 'auto',
            }}
            onKeyDown={handleKeyDown}
          >
            <div style={{ padding: '4px 0' }}>
              {flatOptions.map((opt, idx) => {
                if (isHeader(opt)) {
                  return (
                    <div
                      key={opt.value}
                      style={{
                        padding: '6px 12px 2px',
                        fontSize: 10,
                        fontWeight: 700,
                        color: theme.textMuted,
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                        pointerEvents: 'none',
                      }}
                    >
                      {opt.label}
                    </div>
                  );
                }
                const sIdx = selectableOptions.indexOf(opt);
                const isSelected = opt.value === value;
                const isHighlighted = sIdx === highlightedIdx;
                return (
                  <div
                    key={opt.value}
                    id={`${triggerId}-opt-${sIdx}`}
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => selectValue(opt.value)}
                    onMouseEnter={() => setHighlightedIdx(sIdx)}
                    style={{
                      padding: '8px 12px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 8,
                      background: isHighlighted
                        ? `${theme.aiAccent}10`
                        : isSelected
                          ? `${theme.aiAccent}08`
                          : 'transparent',
                      color: theme.text,
                      fontSize: 12,
                      transition: 'background 0.08s',
                    }}
                  >
                    {opt.icon && (
                      <span
                        style={{
                          flexShrink: 0,
                          display: 'flex',
                          alignItems: 'center',
                          marginTop: 1,
                          color: theme.textMuted,
                        }}
                      >
                        {opt.icon}
                      </span>
                    )}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                      <span style={{ fontWeight: isSelected ? 600 : 400, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {opt.label}
                      </span>
                      {opt.recommended_for && (
                        <span style={{ fontSize: 11, color: theme.textMuted, lineHeight: 1.35 }}>
                          {opt.recommended_for}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
