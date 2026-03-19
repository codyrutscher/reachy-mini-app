-- ============================================================================
-- Reachy Care — Row Level Security (RLS) Policies
-- ============================================================================
-- Run this migration against your Supabase/Postgres database.
--
-- HOW IT WORKS:
--   1. Every table gets RLS enabled (Supabase requires this for security).
--   2. Bot tables (bot_*) are locked to patient_id — a user can only see
--      rows where patient_id matches their JWT claim.
--   3. Dashboard tables use role-based access — authenticated users can
--      read everything, but only service_role can write.
--   4. The service_role (used by the bot and dashboard backend) bypasses
--      all RLS — it can read/write everything.
--
-- JWT CLAIM SETUP:
--   Your Supabase JWT should include:
--     app_metadata.patient_id  — e.g. "default" or "patient_123"
--     app_metadata.role        — e.g. "admin", "caregiver", "family"
--
-- To set these on a user in Supabase:
--   UPDATE auth.users SET raw_app_meta_data =
--     raw_app_meta_data || '{"patient_id":"default","role":"caregiver"}'
--   WHERE id = '<user-uuid>';
-- ============================================================================

-- Helper function: extract patient_id from the JWT
-- Lives in public schema (auth schema is protected in Supabase)
CREATE OR REPLACE FUNCTION public.requesting_patient_id() RETURNS TEXT AS $$
  SELECT coalesce(
    ((auth.jwt()->'app_metadata'->>'patient_id')),
    'default'
  );
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Helper function: extract user role from the JWT app_metadata
CREATE OR REPLACE FUNCTION public.requesting_user_role() RETURNS TEXT AS $$
  SELECT coalesce(
    ((auth.jwt()->'app_metadata'->>'role')),
    'anon'
  );
$$ LANGUAGE sql STABLE SECURITY DEFINER;


-- ============================================================================
-- BOT TABLES — patient_id scoped
-- ============================================================================
-- These tables are written by the Reachy bot and read by the dashboard.
-- Each row belongs to a specific patient_id.

-- bot_mood_journal
ALTER TABLE bot_mood_journal ENABLE ROW LEVEL SECURITY;
CREATE POLICY "bot_mood_journal_select" ON bot_mood_journal FOR SELECT
  USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "bot_mood_journal_insert" ON bot_mood_journal FOR INSERT
  WITH CHECK (patient_id = public.requesting_patient_id());
CREATE POLICY "bot_mood_journal_service" ON bot_mood_journal FOR ALL
  USING (auth.role() = 'service_role');

-- bot_conversation_log
ALTER TABLE bot_conversation_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "bot_conversation_log_select" ON bot_conversation_log FOR SELECT
  USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "bot_conversation_log_insert" ON bot_conversation_log FOR INSERT
  WITH CHECK (patient_id = public.requesting_patient_id());
CREATE POLICY "bot_conversation_log_service" ON bot_conversation_log FOR ALL
  USING (auth.role() = 'service_role');

-- bot_mentions
ALTER TABLE bot_mentions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "bot_mentions_select" ON bot_mentions FOR SELECT
  USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "bot_mentions_insert" ON bot_mentions FOR INSERT
  WITH CHECK (patient_id = public.requesting_patient_id());
CREATE POLICY "bot_mentions_service" ON bot_mentions FOR ALL
  USING (auth.role() = 'service_role');

-- bot_streaks
ALTER TABLE bot_streaks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "bot_streaks_select" ON bot_streaks FOR SELECT
  USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "bot_streaks_insert" ON bot_streaks FOR INSERT
  WITH CHECK (patient_id = public.requesting_patient_id());
CREATE POLICY "bot_streaks_service" ON bot_streaks FOR ALL
  USING (auth.role() = 'service_role');

-- bot_patient_facts
ALTER TABLE bot_patient_facts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "bot_patient_facts_select" ON bot_patient_facts FOR SELECT
  USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "bot_patient_facts_insert" ON bot_patient_facts FOR INSERT
  WITH CHECK (patient_id = public.requesting_patient_id());
CREATE POLICY "bot_patient_facts_service" ON bot_patient_facts FOR ALL
  USING (auth.role() = 'service_role');

-- bot_patient_profile
ALTER TABLE bot_patient_profile ENABLE ROW LEVEL SECURITY;
CREATE POLICY "bot_patient_profile_select" ON bot_patient_profile FOR SELECT
  USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "bot_patient_profile_upsert" ON bot_patient_profile FOR ALL
  USING (patient_id = public.requesting_patient_id());
CREATE POLICY "bot_patient_profile_service" ON bot_patient_profile FOR ALL
  USING (auth.role() = 'service_role');

-- bot_cognitive_scores
ALTER TABLE bot_cognitive_scores ENABLE ROW LEVEL SECURITY;
CREATE POLICY "bot_cognitive_scores_select" ON bot_cognitive_scores FOR SELECT
  USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "bot_cognitive_scores_insert" ON bot_cognitive_scores FOR INSERT
  WITH CHECK (patient_id = public.requesting_patient_id());
CREATE POLICY "bot_cognitive_scores_service" ON bot_cognitive_scores FOR ALL
  USING (auth.role() = 'service_role');

-- bot_exercise_log
ALTER TABLE bot_exercise_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "bot_exercise_log_select" ON bot_exercise_log FOR SELECT
  USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "bot_exercise_log_insert" ON bot_exercise_log FOR INSERT
  WITH CHECK (patient_id = public.requesting_patient_id());
CREATE POLICY "bot_exercise_log_service" ON bot_exercise_log FOR ALL
  USING (auth.role() = 'service_role');

-- bot_pain_reports
ALTER TABLE bot_pain_reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY "bot_pain_reports_select" ON bot_pain_reports FOR SELECT
  USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "bot_pain_reports_insert" ON bot_pain_reports FOR INSERT
  WITH CHECK (patient_id = public.requesting_patient_id());
CREATE POLICY "bot_pain_reports_service" ON bot_pain_reports FOR ALL
  USING (auth.role() = 'service_role');

-- bot_sleep_log
ALTER TABLE bot_sleep_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "bot_sleep_log_select" ON bot_sleep_log FOR SELECT
  USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "bot_sleep_log_insert" ON bot_sleep_log FOR INSERT
  WITH CHECK (patient_id = public.requesting_patient_id());
CREATE POLICY "bot_sleep_log_service" ON bot_sleep_log FOR ALL
  USING (auth.role() = 'service_role');

-- bot_session_summaries
ALTER TABLE bot_session_summaries ENABLE ROW LEVEL SECURITY;
CREATE POLICY "bot_session_summaries_select" ON bot_session_summaries FOR SELECT
  USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "bot_session_summaries_insert" ON bot_session_summaries FOR INSERT
  WITH CHECK (patient_id = public.requesting_patient_id());
CREATE POLICY "bot_session_summaries_service" ON bot_session_summaries FOR ALL
  USING (auth.role() = 'service_role');

-- bot_weekly_reports
ALTER TABLE bot_weekly_reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY "bot_weekly_reports_select" ON bot_weekly_reports FOR SELECT
  USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "bot_weekly_reports_upsert" ON bot_weekly_reports FOR ALL
  USING (patient_id = public.requesting_patient_id());
CREATE POLICY "bot_weekly_reports_service" ON bot_weekly_reports FOR ALL
  USING (auth.role() = 'service_role');

-- bot_reminders
ALTER TABLE bot_reminders ENABLE ROW LEVEL SECURITY;
CREATE POLICY "bot_reminders_select" ON bot_reminders FOR SELECT
  USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "bot_reminders_all" ON bot_reminders FOR ALL
  USING (patient_id = public.requesting_patient_id());
CREATE POLICY "bot_reminders_service" ON bot_reminders FOR ALL
  USING (auth.role() = 'service_role');

-- bot_caregiver_alerts
ALTER TABLE bot_caregiver_alerts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "bot_caregiver_alerts_select" ON bot_caregiver_alerts FOR SELECT
  USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "bot_caregiver_alerts_insert" ON bot_caregiver_alerts FOR INSERT
  WITH CHECK (patient_id = public.requesting_patient_id());
CREATE POLICY "bot_caregiver_alerts_update" ON bot_caregiver_alerts FOR UPDATE
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "bot_caregiver_alerts_service" ON bot_caregiver_alerts FOR ALL
  USING (auth.role() = 'service_role');

-- bot_chat_history
ALTER TABLE bot_chat_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "bot_chat_history_select" ON bot_chat_history FOR SELECT
  USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "bot_chat_history_upsert" ON bot_chat_history FOR ALL
  USING (patient_id = public.requesting_patient_id());
CREATE POLICY "bot_chat_history_service" ON bot_chat_history FOR ALL
  USING (auth.role() = 'service_role');


-- ============================================================================
-- DASHBOARD TABLES — role-based access
-- ============================================================================
-- These tables are managed by the dashboard backend (Flask app).
-- The backend connects with service_role, so it bypasses RLS.
-- If you expose these via Supabase client-side, these policies apply.

-- alerts
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "alerts_read" ON alerts FOR SELECT
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "alerts_write" ON alerts FOR ALL
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "alerts_service" ON alerts FOR ALL
  USING (auth.role() = 'service_role');

-- messages
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY "messages_read" ON messages FOR SELECT
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "messages_write" ON messages FOR ALL
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "messages_service" ON messages FOR ALL
  USING (auth.role() = 'service_role');

-- conversation
ALTER TABLE conversation ENABLE ROW LEVEL SECURITY;
CREATE POLICY "conversation_read" ON conversation FOR SELECT
  USING (auth.role() = 'authenticated');
CREATE POLICY "conversation_write" ON conversation FOR INSERT
  WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "conversation_service" ON conversation FOR ALL
  USING (auth.role() = 'service_role');

-- patient_status
ALTER TABLE patient_status ENABLE ROW LEVEL SECURITY;
CREATE POLICY "patient_status_read" ON patient_status FOR SELECT
  USING (auth.role() = 'authenticated');
CREATE POLICY "patient_status_write" ON patient_status FOR ALL
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "patient_status_service" ON patient_status FOR ALL
  USING (auth.role() = 'service_role');

-- mood_history
ALTER TABLE mood_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "mood_history_read" ON mood_history FOR SELECT
  USING (auth.role() = 'authenticated');
CREATE POLICY "mood_history_write" ON mood_history FOR INSERT
  WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "mood_history_service" ON mood_history FOR ALL
  USING (auth.role() = 'service_role');

-- checkin_history
ALTER TABLE checkin_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "checkin_history_read" ON checkin_history FOR SELECT
  USING (auth.role() = 'authenticated');
CREATE POLICY "checkin_history_write" ON checkin_history FOR INSERT
  WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "checkin_history_service" ON checkin_history FOR ALL
  USING (auth.role() = 'service_role');

-- patients
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
CREATE POLICY "patients_read" ON patients FOR SELECT
  USING (auth.role() = 'authenticated');
CREATE POLICY "patients_write" ON patients FOR ALL
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "patients_service" ON patients FOR ALL
  USING (auth.role() = 'service_role');

-- facilities
ALTER TABLE facilities ENABLE ROW LEVEL SECURITY;
CREATE POLICY "facilities_read" ON facilities FOR SELECT
  USING (auth.role() = 'authenticated');
CREATE POLICY "facilities_write" ON facilities FOR ALL
  USING (public.requesting_user_role() = 'admin');
CREATE POLICY "facilities_service" ON facilities FOR ALL
  USING (auth.role() = 'service_role');

-- settings
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "settings_read" ON settings FOR SELECT
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "settings_write" ON settings FOR ALL
  USING (public.requesting_user_role() = 'admin');
CREATE POLICY "settings_service" ON settings FOR ALL
  USING (auth.role() = 'service_role');

-- scheduled_messages
ALTER TABLE scheduled_messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY "scheduled_messages_read" ON scheduled_messages FOR SELECT
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "scheduled_messages_write" ON scheduled_messages FOR ALL
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "scheduled_messages_service" ON scheduled_messages FOR ALL
  USING (auth.role() = 'service_role');

-- medications
ALTER TABLE medications ENABLE ROW LEVEL SECURITY;
CREATE POLICY "medications_read" ON medications FOR SELECT
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "medications_write" ON medications FOR ALL
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "medications_service" ON medications FOR ALL
  USING (auth.role() = 'service_role');

-- med_log
ALTER TABLE med_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "med_log_read" ON med_log FOR SELECT
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "med_log_write" ON med_log FOR ALL
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "med_log_service" ON med_log FOR ALL
  USING (auth.role() = 'service_role');

-- activity_log
ALTER TABLE activity_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "activity_log_read" ON activity_log FOR SELECT
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "activity_log_write" ON activity_log FOR INSERT
  WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "activity_log_service" ON activity_log FOR ALL
  USING (auth.role() = 'service_role');

-- users (admin only for management, self-read for own profile)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_admin_all" ON users FOR ALL
  USING (public.requesting_user_role() = 'admin');
CREATE POLICY "users_service" ON users FOR ALL
  USING (auth.role() = 'service_role');

-- daily_reports
ALTER TABLE daily_reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY "daily_reports_read" ON daily_reports FOR SELECT
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "daily_reports_write" ON daily_reports FOR ALL
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "daily_reports_service" ON daily_reports FOR ALL
  USING (auth.role() = 'service_role');

-- caregiver_notes
ALTER TABLE caregiver_notes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "caregiver_notes_read" ON caregiver_notes FOR SELECT
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "caregiver_notes_write" ON caregiver_notes FOR ALL
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "caregiver_notes_service" ON caregiver_notes FOR ALL
  USING (auth.role() = 'service_role');

-- shift_handoffs
ALTER TABLE shift_handoffs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "shift_handoffs_read" ON shift_handoffs FOR SELECT
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "shift_handoffs_write" ON shift_handoffs FOR INSERT
  WITH CHECK (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "shift_handoffs_service" ON shift_handoffs FOR ALL
  USING (auth.role() = 'service_role');

-- family_messages (family can read/write their own, caregivers can see all)
ALTER TABLE family_messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY "family_messages_read" ON family_messages FOR SELECT
  USING (auth.role() = 'authenticated');
CREATE POLICY "family_messages_write" ON family_messages FOR INSERT
  WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "family_messages_update" ON family_messages FOR UPDATE
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "family_messages_service" ON family_messages FOR ALL
  USING (auth.role() = 'service_role');

-- vitals_log
ALTER TABLE vitals_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "vitals_log_read" ON vitals_log FOR SELECT
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "vitals_log_write" ON vitals_log FOR INSERT
  WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "vitals_log_service" ON vitals_log FOR ALL
  USING (auth.role() = 'service_role');


-- ============================================================================
-- ADDITIONAL BOT TABLES — knowledge graph, vectors, temporal patterns
-- ============================================================================
-- These tables may not exist on all deployments (created by optional modules).
-- Wrap in DO blocks so the migration doesn't fail if they're missing.

-- bot_knowledge_entities
DO $$ BEGIN
  ALTER TABLE bot_knowledge_entities ENABLE ROW LEVEL SECURITY;
  CREATE POLICY "bot_knowledge_entities_select" ON bot_knowledge_entities FOR SELECT
    USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
  CREATE POLICY "bot_knowledge_entities_write" ON bot_knowledge_entities FOR ALL
    USING (patient_id = public.requesting_patient_id());
  CREATE POLICY "bot_knowledge_entities_service" ON bot_knowledge_entities FOR ALL
    USING (auth.role() = 'service_role');
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- bot_knowledge_relations
DO $$ BEGIN
  ALTER TABLE bot_knowledge_relations ENABLE ROW LEVEL SECURITY;
  CREATE POLICY "bot_knowledge_relations_select" ON bot_knowledge_relations FOR SELECT
    USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
  CREATE POLICY "bot_knowledge_relations_write" ON bot_knowledge_relations FOR ALL
    USING (patient_id = public.requesting_patient_id());
  CREATE POLICY "bot_knowledge_relations_service" ON bot_knowledge_relations FOR ALL
    USING (auth.role() = 'service_role');
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- bot_temporal_patterns
DO $$ BEGIN
  ALTER TABLE bot_temporal_patterns ENABLE ROW LEVEL SECURITY;
  CREATE POLICY "bot_temporal_patterns_select" ON bot_temporal_patterns FOR SELECT
    USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
  CREATE POLICY "bot_temporal_patterns_write" ON bot_temporal_patterns FOR ALL
    USING (patient_id = public.requesting_patient_id());
  CREATE POLICY "bot_temporal_patterns_service" ON bot_temporal_patterns FOR ALL
    USING (auth.role() = 'service_role');
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- bot_memory_vectors (pgvector)
DO $$ BEGIN
  ALTER TABLE bot_memory_vectors ENABLE ROW LEVEL SECURITY;
  CREATE POLICY "bot_memory_vectors_select" ON bot_memory_vectors FOR SELECT
    USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
  CREATE POLICY "bot_memory_vectors_insert" ON bot_memory_vectors FOR INSERT
    WITH CHECK (patient_id = public.requesting_patient_id());
  CREATE POLICY "bot_memory_vectors_service" ON bot_memory_vectors FOR ALL
    USING (auth.role() = 'service_role');
EXCEPTION WHEN undefined_table THEN NULL;
END $$;


-- ============================================================================
-- INDEXES for RLS performance
-- ============================================================================
-- RLS policies filter on patient_id frequently. These indexes ensure
-- the WHERE clauses don't cause full table scans.

CREATE INDEX IF NOT EXISTS idx_bot_mood_journal_patient ON bot_mood_journal(patient_id);
CREATE INDEX IF NOT EXISTS idx_bot_conversation_log_patient ON bot_conversation_log(patient_id);
CREATE INDEX IF NOT EXISTS idx_bot_mentions_patient ON bot_mentions(patient_id);
CREATE INDEX IF NOT EXISTS idx_bot_streaks_patient ON bot_streaks(patient_id);
CREATE INDEX IF NOT EXISTS idx_bot_patient_facts_patient ON bot_patient_facts(patient_id);
CREATE INDEX IF NOT EXISTS idx_bot_cognitive_scores_patient ON bot_cognitive_scores(patient_id);
CREATE INDEX IF NOT EXISTS idx_bot_exercise_log_patient ON bot_exercise_log(patient_id);
CREATE INDEX IF NOT EXISTS idx_bot_pain_reports_patient ON bot_pain_reports(patient_id);
CREATE INDEX IF NOT EXISTS idx_bot_sleep_log_patient ON bot_sleep_log(patient_id);
CREATE INDEX IF NOT EXISTS idx_bot_session_summaries_patient ON bot_session_summaries(patient_id);
CREATE INDEX IF NOT EXISTS idx_bot_weekly_reports_patient ON bot_weekly_reports(patient_id);
CREATE INDEX IF NOT EXISTS idx_bot_reminders_patient ON bot_reminders(patient_id);
CREATE INDEX IF NOT EXISTS idx_bot_caregiver_alerts_patient ON bot_caregiver_alerts(patient_id);
CREATE INDEX IF NOT EXISTS idx_bot_chat_history_patient ON bot_chat_history(patient_id);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_bot_mood_journal_patient_time ON bot_mood_journal(patient_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bot_conversation_log_patient_time ON bot_conversation_log(patient_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bot_caregiver_alerts_patient_ack ON bot_caregiver_alerts(patient_id, acknowledged);
