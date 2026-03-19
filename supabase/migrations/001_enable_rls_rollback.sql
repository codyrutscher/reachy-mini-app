-- ============================================================================
-- ROLLBACK: Disable all RLS policies
-- ============================================================================
-- Run this if you need to revert the RLS migration.
-- This drops all policies and disables RLS on every table.
-- ============================================================================

-- Bot tables
DO $$ DECLARE t TEXT;
BEGIN
  FOR t IN SELECT unnest(ARRAY[
    'bot_mood_journal', 'bot_conversation_log', 'bot_mentions', 'bot_streaks',
    'bot_patient_facts', 'bot_patient_profile', 'bot_cognitive_scores',
    'bot_exercise_log', 'bot_pain_reports', 'bot_sleep_log',
    'bot_session_summaries', 'bot_weekly_reports', 'bot_reminders',
    'bot_caregiver_alerts', 'bot_chat_history',
    'bot_knowledge_entities', 'bot_knowledge_relations',
    'bot_temporal_patterns', 'bot_memory_vectors',
    'alerts', 'messages', 'conversation', 'patient_status',
    'mood_history', 'checkin_history', 'patients', 'facilities',
    'settings', 'scheduled_messages', 'medications', 'med_log',
    'activity_log', 'users', 'daily_reports', 'caregiver_notes',
    'shift_handoffs', 'family_messages', 'vitals_log'
  ])
  LOOP
    BEGIN
      -- Drop all policies on this table
      FOR t IN SELECT policyname FROM pg_policies WHERE tablename = t
      LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON %I', t, t);
      END LOOP;
      -- Disable RLS
      EXECUTE format('ALTER TABLE %I DISABLE ROW LEVEL SECURITY', t);
    EXCEPTION WHEN undefined_table THEN NULL;
    END;
  END LOOP;
END $$;

-- Drop helper functions
DROP FUNCTION IF EXISTS public.requesting_patient_id();
DROP FUNCTION IF EXISTS public.requesting_user_role();
