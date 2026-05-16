import { useEffect } from 'react';

export type TopTabId = 'chat' | 'wizprompt' | 'agent' | 'tasks' | 'memories';

const TAB_ORDER: TopTabId[] = ['chat', 'wizprompt', 'agent', 'tasks', 'memories'];

export function useTopTabNav(activeTab: TopTabId, setTab: (tab: TopTabId) => void) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;

      const element = document.activeElement;
      if (
        element &&
        (element.tagName === 'INPUT' ||
          element.tagName === 'TEXTAREA' ||
          (element as HTMLElement).isContentEditable)
      ) {
        return;
      }

      if (event.isComposing) return;

      const currentIndex = TAB_ORDER.indexOf(activeTab);
      if (currentIndex < 0) return;

      if (event.key === 'ArrowRight') {
        setTab(TAB_ORDER[(currentIndex + 1) % TAB_ORDER.length]);
      } else {
        setTab(TAB_ORDER[(currentIndex - 1 + TAB_ORDER.length) % TAB_ORDER.length]);
      }
      event.preventDefault();
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [activeTab, setTab]);
}
