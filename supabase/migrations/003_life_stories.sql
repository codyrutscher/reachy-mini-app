-- Life stories table: stores compiled life narratives per patient
CREATE TABLE IF NOT EXISTS life_stories (
    patient_id TEXT PRIMARY KEY,
    story JSONB NOT NULL DEFAULT '{}',
    compiled_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE life_stories ENABLE ROW LEVEL SECURITY;

-- Daily journal table: auto-generated journal entries from conversations
CREATE TABLE IF NOT EXISTS daily_journal (
    id SERIAL PRIMARY KEY,
    patient_id TEXT NOT NULL DEFAULT 'default',
    entry_date DATE NOT NULL DEFAULT CURRENT_DATE,
    entry TEXT NOT NULL DEFAULT '',
    mood TEXT DEFAULT 'neutral',
    topics JSONB DEFAULT '[]',
    interactions INTEGER DEFAULT 0,
    duration_minutes REAL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(patient_id, entry_date)
);

ALTER TABLE daily_journal ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_daily_journal_patient ON daily_journal(patient_id);
CREATE INDEX IF NOT EXISTS idx_daily_journal_date ON daily_journal(entry_date DESC);

-- Dream journal table: patient-described dreams
CREATE TABLE IF NOT EXISTS dream_journal (
    id SERIAL PRIMARY KEY,
    patient_id TEXT NOT NULL DEFAULT 'default',
    dream_date DATE NOT NULL DEFAULT CURRENT_DATE,
    content TEXT NOT NULL DEFAULT '',
    mood TEXT DEFAULT 'neutral',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE dream_journal ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_dream_journal_patient ON dream_journal(patient_id);
CREATE INDEX IF NOT EXISTS idx_dream_journal_date ON dream_journal(dream_date DESC);

-- Wish list table: patient wishes shared with family
CREATE TABLE IF NOT EXISTS wish_list (
    id SERIAL PRIMARY KEY,
    patient_id TEXT NOT NULL DEFAULT 'default',
    wish TEXT NOT NULL,
    full_text TEXT DEFAULT '',
    fulfilled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE wish_list ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_wish_list_patient ON wish_list(patient_id);

-- Advice book table: collected wisdom and advice
CREATE TABLE IF NOT EXISTS advice_book (
    id SERIAL PRIMARY KEY,
    patient_id TEXT NOT NULL DEFAULT 'default',
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE advice_book ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_advice_book_patient ON advice_book(patient_id);

-- Recipe book table: structured recipes from patient descriptions
CREATE TABLE IF NOT EXISTS recipe_book (
    id SERIAL PRIMARY KEY,
    patient_id TEXT NOT NULL DEFAULT 'default',
    name TEXT NOT NULL DEFAULT 'Untitled',
    recipe JSONB NOT NULL DEFAULT '{}',
    raw_text TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE recipe_book ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_recipe_book_patient ON recipe_book(patient_id);

-- Patient jokes table: jokes the patient has told (so Reachy never repeats them)
CREATE TABLE IF NOT EXISTS patient_jokes (
    id SERIAL PRIMARY KEY,
    patient_id TEXT NOT NULL DEFAULT 'default',
    joke_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE patient_jokes ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_patient_jokes_patient ON patient_jokes(patient_id);

-- Song favorites table: tracks song requests for personalized suggestions
CREATE TABLE IF NOT EXISTS song_favorites (
    id SERIAL PRIMARY KEY,
    patient_id TEXT NOT NULL DEFAULT 'default',
    request_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE song_favorites ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_song_favorites_patient ON song_favorites(patient_id);

-- Birthday tracker table
CREATE TABLE IF NOT EXISTS birthday_tracker (
    id SERIAL PRIMARY KEY,
    patient_id TEXT NOT NULL DEFAULT 'default',
    person_name TEXT NOT NULL,
    birthday_date TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(patient_id, person_name)
);

ALTER TABLE birthday_tracker ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_birthday_tracker_patient ON birthday_tracker(patient_id);

-- Worry jar table
CREATE TABLE IF NOT EXISTS worry_jar (
    id SERIAL PRIMARY KEY,
    patient_id TEXT NOT NULL DEFAULT 'default',
    worry TEXT NOT NULL,
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE worry_jar ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_worry_jar_patient ON worry_jar(patient_id);

-- Visitor log table
CREATE TABLE IF NOT EXISTS visitor_log (
    id SERIAL PRIMARY KEY,
    patient_id TEXT NOT NULL DEFAULT 'default',
    visitor_name TEXT NOT NULL DEFAULT 'Unknown',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE visitor_log ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_visitor_log_patient ON visitor_log(patient_id);
