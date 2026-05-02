import { AnimatePresence, motion } from 'framer-motion';
import type { ReactNode } from 'react';
import type { TopTabId } from './useTopTabNav';

type Props = {
  activeTab: TopTabId;
  chat: ReactNode;
  wizprompt: ReactNode;
  agent: ReactNode;
  tasks: ReactNode;
  memories: ReactNode;
  tunehub: ReactNode;
};

export default function TopTabContent({ activeTab, chat, wizprompt, agent, tasks, memories, tunehub }: Props) {
  const content = { chat, wizprompt, agent, tasks, memories, tunehub }[activeTab];

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={activeTab}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={{ duration: 0.15 }}
        style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}
      >
        {content}
      </motion.div>
    </AnimatePresence>
  );
}
