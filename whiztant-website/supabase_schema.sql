-- =============================================================
--  Wiztant Website Credit System Schema
--  Run this in your website Supabase project's SQL Editor
-- =============================================================

-- 1. User credits table (stores current balance & tier)
CREATE TABLE IF NOT EXISTS public.user_credits (
  user_id UUID PRIMARY KEY REFERENCES auth.users ON DELETE CASCADE,
  balance INTEGER NOT NULL DEFAULT 0,
  tier TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'pro', 'power')),
  monthly_allocation INTEGER NOT NULL DEFAULT 50,
  provider TEXT,                                       -- 'razorpay' | 'stripe' | null
  subscription_id TEXT,                                -- Razorpay sub ID or Stripe sub ID
  subscription_status TEXT,                            -- 'active' | 'canceled' | 'past_due' | null
  current_period_end TIMESTAMPTZ,
  reset_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Credit transactions history (AI usage audit log)
CREATE TABLE IF NOT EXISTS public.credit_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users NOT NULL,
  feature TEXT NOT NULL,
  model TEXT,
  amount INTEGER NOT NULL,
  balance_after INTEGER NOT NULL,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Payment history (subscription payments audit log)
CREATE TABLE IF NOT EXISTS public.payment_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users NOT NULL,
  provider TEXT NOT NULL,
  amount INTEGER NOT NULL,           -- in smallest currency unit (cents / paise)
  currency TEXT NOT NULL,
  status TEXT NOT NULL,
  subscription_id TEXT,
  invoice_id TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Enable Row Level Security
ALTER TABLE public.user_credits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.credit_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payment_history ENABLE ROW LEVEL SECURITY;

-- 5. RLS Policies — users can only read/write their own data
DROP POLICY IF EXISTS "Users can read own credits" ON public.user_credits;
CREATE POLICY "Users can read own credits"
  ON public.user_credits FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can update own credits" ON public.user_credits;
CREATE POLICY "Users can update own credits"
  ON public.user_credits FOR UPDATE
  TO authenticated
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can insert own credits" ON public.user_credits;
CREATE POLICY "Users can insert own credits"
  ON public.user_credits FOR INSERT
  TO authenticated
  WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can read own transactions" ON public.credit_transactions;
CREATE POLICY "Users can read own transactions"
  ON public.credit_transactions FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can insert own transactions" ON public.credit_transactions;
CREATE POLICY "Users can insert own transactions"
  ON public.credit_transactions FOR INSERT
  TO authenticated
  WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can read own payments" ON public.payment_history;
CREATE POLICY "Users can read own payments"
  ON public.payment_history FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can insert own payments" ON public.payment_history;
CREATE POLICY "Users can insert own payments"
  ON public.payment_history FOR INSERT
  TO authenticated
  WITH CHECK (user_id = auth.uid());

-- 6. Function: auto-initialize credits on signup
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.user_credits (user_id, balance, tier, monthly_allocation)
  VALUES (NEW.id, 50, 'free', 50)
  ON CONFLICT (user_id) DO NOTHING;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 7. Trigger: run on every new auth user
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 8. Backfill existing users (if you already have accounts)
INSERT INTO public.user_credits (user_id, balance, tier, monthly_allocation)
SELECT id, 50, 'free', 50
FROM auth.users
ON CONFLICT (user_id) DO NOTHING;
