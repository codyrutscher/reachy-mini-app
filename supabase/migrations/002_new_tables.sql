-- ============================================================================
-- Migration 002: New tables for teleoperation, robot events, care plans,
--                and incident reports
-- ============================================================================

-- TABLE 1: teleop_sessions
-- Logs every teleoperation session (who controlled the robot, when, how long)

CREATE TABLE IF NOT EXISTS teleop_sessions (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    commands_sent INTEGER DEFAULT 0,
    mode TEXT DEFAULT 'manual',
    notes TEXT DEFAULT ''
);



-- TABLE 2: robot_events
-- Logs every action/expression/pose the robot performs.
-- Useful for analytics: "how often does Reachy dance?" "what expressions are used most?"

CREATE TABLE IF NOT EXISTS robot_events (
    id SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL CHECK (event_type IN ('action', 'expression', 'pose', 'reset')),
    event_name TEXT NOT NULL,
    source TEXT DEFAULT 'bot',
    patient_id TEXT DEFAULT 'default',
    session_id INTEGER REFERENCES teleop_sessions(id) ON DELETE SET NULL,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- TABLE 3: care_plans + care_plan_goals
-- A care plan is a high-level treatment/activity plan for a patient.
-- Each plan can have multiple goals (one-to-many relationship).

CREATE TABLE IF NOT EXISTS care_plans (
    id SERIAL PRIMARY KEY,
    patient_id TEXT NOT NULL DEFAULT 'default',
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'paused', 'cancelled')),
    created_by TEXT NOT NULL,
    start_date DATE DEFAULT CURRENT_DATE,
    end_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS care_plan_goals (
    id SERIAL PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES care_plans(id) ON DELETE CASCADE,
    goal_text TEXT NOT NULL,
    target_date DATE,
    completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMPTZ,
    notes TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- TABLE 4: incident_reports
-- Logs falls, wandering, agitation episodes, or any safety incidents.
-- Links to a patient and tracks severity + resolution.


CREATE TABLE IF NOT EXISTS incident_reports (
    id SERIAL PRIMARY KEY,
    patient_id TEXT NOT NULL DEFAULT 'default',
    incident_type TEXT NOT NULL CHECK (incident_type IN ('fall', 'wandering', 'agitation', 'medication_error', 'injury', 'other')),
    severity TEXT DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    description TEXT NOT NULL,
    actions_taken TEXT DEFAULT '',
    reported_by TEXT NOT NULL,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ, 
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================================
-- INDEXES for new tables
-- ============================================================================

-- teleop_sessions: find sessions by user or by time
CREATE INDEX IF NOT EXISTS idx_teleop_sessions_username ON teleop_sessions(username);
CREATE INDEX IF NOT EXISTS idx_teleop_sessions_started ON teleop_sessions(started_at DESC);

-- robot_events: filter by type, by patient, or by time
CREATE INDEX IF NOT EXISTS idx_robot_events_type ON robot_events(event_type);
CREATE INDEX IF NOT EXISTS idx_robot_events_patient ON robot_events(patient_id);
CREATE INDEX IF NOT EXISTS idx_robot_events_created ON robot_events(created_at DESC);

-- care_plans: find plans by patient or by status
CREATE INDEX IF NOT EXISTS idx_care_plans_patient ON care_plans(patient_id);
CREATE INDEX IF NOT EXISTS idx_care_plans_status ON care_plans(status);

-- care_plan_goals: find goals by plan
CREATE INDEX IF NOT EXISTS idx_care_plan_goals_plan ON care_plan_goals(plan_id);

-- incident_reports: filter by patient, severity, or unresolved
CREATE INDEX IF NOT EXISTS idx_incident_reports_patient ON incident_reports(patient_id);
CREATE INDEX IF NOT EXISTS idx_incident_reports_severity ON incident_reports(severity);
CREATE INDEX IF NOT EXISTS idx_incident_reports_resolved ON incident_reports(resolved);


-- ============================================================================
-- RLS POLICIES for new tables
-- ============================================================================

-- teleop_sessions: admin/caregiver only
ALTER TABLE teleop_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "teleop_sessions_read" ON teleop_sessions FOR SELECT
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "teleop_sessions_write" ON teleop_sessions FOR ALL
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "teleop_sessions_service" ON teleop_sessions FOR ALL
  USING (auth.role() = 'service_role');

-- robot_events: patient-scoped reads, service writes
ALTER TABLE robot_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "robot_events_select" ON robot_events FOR SELECT
  USING (patient_id = public.requesting_patient_id() OR public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "robot_events_insert" ON robot_events FOR INSERT
  WITH CHECK (patient_id = public.requesting_patient_id());
CREATE POLICY "robot_events_service" ON robot_events FOR ALL
  USING (auth.role() = 'service_role');

-- care_plans: admin/caregiver write, all authenticated read
ALTER TABLE care_plans ENABLE ROW LEVEL SECURITY;
CREATE POLICY "care_plans_read" ON care_plans FOR SELECT
  USING (auth.role() = 'authenticated');
CREATE POLICY "care_plans_write" ON care_plans FOR ALL
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "care_plans_service" ON care_plans FOR ALL
  USING (auth.role() = 'service_role');

-- care_plan_goals: same as care_plans
ALTER TABLE care_plan_goals ENABLE ROW LEVEL SECURITY;
CREATE POLICY "care_plan_goals_read" ON care_plan_goals FOR SELECT
  USING (auth.role() = 'authenticated');
CREATE POLICY "care_plan_goals_write" ON care_plan_goals FOR ALL
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "care_plan_goals_service" ON care_plan_goals FOR ALL
  USING (auth.role() = 'service_role');

-- incident_reports: admin/caregiver only (sensitive)
ALTER TABLE incident_reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY "incident_reports_read" ON incident_reports FOR SELECT
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "incident_reports_write" ON incident_reports FOR ALL
  USING (public.requesting_user_role() IN ('admin', 'caregiver'));
CREATE POLICY "incident_reports_service" ON incident_reports FOR ALL
  USING (auth.role() = 'service_role');
