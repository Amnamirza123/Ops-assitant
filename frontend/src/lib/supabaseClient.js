// src/lib/supabaseClient.js

import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

// This is the "anon" (public) key — safe to expose in frontend code,
// unlike the service_role key your backend uses. It only lets users
// act as themselves, never bypass row-level security.
export const supabase = createClient(supabaseUrl, supabaseAnonKey);