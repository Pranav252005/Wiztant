import { useState, useRef } from 'react';
import type { Theme } from '../shared/themes';

type Props = {
  categories: string[];
  active: string | 'all';
  onChange: (category: string | 'all') => void;
  theme: Theme['panel'];
  counts: Record<string, number>;
  onAddCategory?: (name: string) => void;
  onDropTask?: (taskId: string, category: string) => void;
};

export default function CategoryTabs({
  categories,
  active,
  onChange,
  theme,
  counts,
  onAddCategory,
  onDropTask,
}: Props) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState('');
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const tabs: Array<string | 'all'> = ['all', ...categories];

  const handleDragOver = (e: React.DragEvent, cat: string) => {
    e.preventDefault();
    setDropTarget(cat);
  };

  const handleDrop = (e: React.DragEvent, cat: string) => {
    e.preventDefault();
    setDropTarget(null);
    const taskId = e.dataTransfer.getData('text/plain');
    if (taskId && onDropTask) {
      onDropTask(taskId, cat);
    }
  };

  const submitNew = () => {
    const name = draft.trim();
    if (name && onAddCategory) {
      onAddCategory(name);
    }
    setDraft('');
    setAdding(false);
  };

  return (
    <div
      style={{
        display: 'flex',
        gap: 6,
        overflowX: 'auto',
        padding: '0 4px 8px',
        scrollbarWidth: 'none',
        alignItems: 'center',
      }}
    >
      {tabs.map((tab) => {
        const isActive = active === tab;
        const isDrop = dropTarget === tab && tab !== 'all';
        const count = counts[tab] ?? 0;
        return (
          <button
            key={tab}
            onClick={() => onChange(tab)}
            onDragOver={(e) => (tab !== 'all' ? handleDragOver(e, tab) : undefined)}
            onDragLeave={() => setDropTarget(null)}
            onDrop={(e) => (tab !== 'all' ? handleDrop(e, tab) : undefined)}
            style={{
              flexShrink: 0,
              padding: '5px 12px',
              borderRadius: 20,
              border: `1px solid ${isDrop ? theme.aiAccent : isActive ? theme.aiAccent : theme.border}`,
              background: isDrop
                ? `${theme.aiAccent}44`
                : isActive
                  ? `${theme.aiAccent}22`
                  : theme.inputBg,
              color: isActive ? theme.aiAccent : theme.textMuted,
              fontSize: 11,
              fontWeight: isActive ? 700 : 500,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'background 0.15s',
            }}
          >
            {tab === 'all' ? 'All' : tab}
            {count > 0 ? (
              <span
                style={{
                  marginLeft: 6,
                  padding: '1px 6px',
                  borderRadius: 10,
                  background: isActive ? theme.aiAccent : theme.border,
                  color: isActive ? '#0a0a0a' : theme.textMuted,
                  fontSize: 10,
                  fontWeight: 700,
                }}
              >
                {count}
              </span>
            ) : null}
          </button>
        );
      })}

      {adding ? (
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') submitNew();
            if (e.key === 'Escape') {
              setAdding(false);
              setDraft('');
            }
          }}
          onBlur={() => {
            if (!draft.trim()) setAdding(false);
          }}
          placeholder="New category"
          autoFocus
          style={{
            flexShrink: 0,
            width: 120,
            padding: '5px 10px',
            borderRadius: 20,
            border: `1px solid ${theme.aiAccent}`,
            background: theme.inputBg,
            color: theme.text,
            fontSize: 11,
            outline: 'none',
          }}
        />
      ) : (
        <button
          onClick={() => {
            setAdding(true);
            setTimeout(() => inputRef.current?.focus(), 0);
          }}
          style={{
            flexShrink: 0,
            padding: '5px 10px',
            borderRadius: 20,
            border: `1px dashed ${theme.border}`,
            background: 'transparent',
            color: theme.textMuted,
            fontSize: 11,
            cursor: 'pointer',
          }}
        >
          + Add
        </button>
      )}
    </div>
  );
}
