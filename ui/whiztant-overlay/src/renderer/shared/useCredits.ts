import { useEffect, useState, useCallback, useRef } from 'react';
import { useBridgeMessage } from './useBridge';

export interface CreditTransaction {
  feature: string;
  model?: string;
  amount: number;
  balance_after: number;
  created_at: string;
}

export interface CreditState {
  balance: number;
  tier: 'free' | 'pro' | 'power';
  allocation: number;
  transactions: CreditTransaction[];
  loading: boolean;
  error: string | null;
}

const API_BASE = 'http://localhost:8765';

const TIER_ALLOCATIONS: Record<string, number> = {
  free: 50,
  pro: 1000,
  power: 5000,
};

const POLL_INTERVAL_MS = 10_000; // Poll every 10 seconds for real-time sync

function getAuthHeaders(): Record<string, string> {
  try {
    const token = localStorage.getItem('whiztant.session_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

export function useCredits() {
  const [state, setState] = useState<CreditState>({
    balance: 0,
    tier: 'free',
    allocation: 50,
    transactions: [],
    loading: true,
    error: null,
  });

  const fetchedRef = useRef(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const safeSetState = useCallback(
    (updater: (prev: CreditState) => CreditState) => {
      if (mountedRef.current) {
        setState(updater);
      }
    },
    [],
  );

  const fetchBalance = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/credits/balance`, {
        headers: { ...getAuthHeaders() },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as Record<string, unknown>;
      if (data.ok) {
        safeSetState((prev) => ({
          ...prev,
          balance: typeof data.balance === 'number' ? data.balance : 0,
          tier: ((data.tier as string) || 'free') as CreditState['tier'],
          allocation:
            typeof data.monthly_allocation === 'number'
              ? data.monthly_allocation
              : TIER_ALLOCATIONS[String(data.tier)] ?? 200,
          loading: false,
          error: null,
        }));
      }
    } catch (e) {
      safeSetState((prev) => ({
        ...prev,
        loading: false,
        error: e instanceof Error ? e.message : 'Failed to load credits',
      }));
    }
  }, [safeSetState]);

  const refreshHistory = useCallback(
    async (limit = 20) => {
      try {
        const res = await fetch(`${API_BASE}/credits/history?limit=${limit}`, {
          headers: { ...getAuthHeaders() },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as Record<string, unknown>;
        if (data.ok && Array.isArray(data.transactions)) {
          safeSetState((prev) => ({
            ...prev,
            transactions: data.transactions as CreditTransaction[],
          }));
        }
      } catch {
        // Silently fail for history — balance is the critical path
      }
    },
    [safeSetState],
  );

  // Initial fetch
  useEffect(() => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;
    fetchBalance();
    refreshHistory();
  }, [fetchBalance, refreshHistory]);

  // Poll every 10 seconds so the UI stays in sync even if WebSocket messages are missed
  useEffect(() => {
    const id = window.setInterval(() => {
      fetchBalance();
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [fetchBalance]);

  // Refetch when the overlay becomes visible (user re-opens after days)
  useEffect(() => {
    const handleVisibility = () => {
      if (!document.hidden) {
        fetchBalance();
        refreshHistory();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, [fetchBalance, refreshHistory]);

  // Listen for real-time WebSocket updates
  useBridgeMessage((msg) => {
    if (msg?.type === 'credits/update') {
      safeSetState((prev) => ({
        ...prev,
        balance: typeof msg.balance === 'number' ? msg.balance : prev.balance,
        tier: ((msg.tier as string) || prev.tier) as CreditState['tier'],
        allocation: typeof msg.allocation === 'number' ? msg.allocation : prev.allocation,
        loading: false,
      }));
    }
  });

  const usagePercent =
    state.allocation > 0
      ? Math.min(100, Math.max(0, ((state.allocation - state.balance) / state.allocation) * 100))
      : 0;

  const remainingPercent = 100 - usagePercent;

  return {
    ...state,
    usagePercent,
    remainingPercent,
    refresh: fetchBalance,
    refreshHistory,
  };
}
