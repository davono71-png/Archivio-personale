-- ARCHIVIO SMART - DATABASE V1
-- PostgreSQL / Supabase ready
--
-- Modello: i documenti appartengono sempre a Davide o Ralitza.
-- La condivisione e gestita con visibility + document_shares, non con un proprietario "Famiglia".

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =========================
-- ENUM
-- =========================

CREATE TYPE document_visibility AS ENUM (
  'privato',
  'condiviso'
);

CREATE TYPE document_origin AS ENUM (
  'gmail',
  'icloud',
  'scanner',
  'android',
  'upload_web',
  'drive',
  'whatsapp'
);

CREATE TYPE document_status AS ENUM (
  'bozza',
  'da_classificare',
  'da_verificare',
  'attivo',
  'archiviato',
  'cestinato'
);

CREATE TYPE share_permission AS ENUM (
  'lettura',
  'modifica'
);

CREATE TYPE ai_review_status AS ENUM (
  'pending',
  'approved',
  'rejected',
  'applied'
);

-- =========================
-- UTENTI
-- =========================

CREATE TABLE app_users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  email text UNIQUE,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO app_users (name)
VALUES
  ('Davide'),
  ('Ralitza');

-- =========================
-- CATEGORIE
-- =========================

CREATE TABLE categories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  sort_order integer NOT NULL DEFAULT 0,
  is_active boolean NOT NULL DEFAULT true
);

INSERT INTO categories (name, sort_order)
VALUES
  ('Banca', 10),
  ('Salute', 20),
  ('Assicurazioni', 30),
  ('Auto', 40),
  ('Casa', 50),
  ('Fisco', 60),
  ('Garanzie', 70),
  ('Sport', 80),
  ('Tecnologia', 90),
  ('Viaggi', 100),
  ('Lavoro', 110),
  ('Alimentazione', 120),
  ('Varie', 999);

-- =========================
-- DOCUMENTI
-- =========================

CREATE TABLE documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  owner_user_id uuid NOT NULL REFERENCES app_users(id),
  category_id uuid REFERENCES categories(id),

  title text NOT NULL,
  description text,

  visibility document_visibility NOT NULL DEFAULT 'privato',
  origin document_origin NOT NULL,
  status document_status NOT NULL DEFAULT 'attivo',

  document_date date,
  expiry_date date,
  reminder_date date,

  sender text,
  source_reference text,
  drive_file_id text,
  drive_folder_id text,
  drive_link text,

  tags text[] NOT NULL DEFAULT '{}',

  ocr_text text,
  ai_summary text,
  ai_keywords text[] NOT NULL DEFAULT '{}',
  ai_confidence numeric(5, 2),

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  archived_at timestamptz,
  deleted_at timestamptz
);

-- =========================
-- FILE DOCUMENTO
-- =========================

CREATE TABLE document_files (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

  file_name text NOT NULL,
  file_path text NOT NULL,
  mime_type text,
  file_size bigint,

  page_count integer,
  checksum text,

  is_original boolean NOT NULL DEFAULT true,

  created_at timestamptz NOT NULL DEFAULT now()
);

-- =========================
-- CONDIVISIONI
-- =========================

CREATE TABLE document_shares (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES app_users(id),

  permission share_permission NOT NULL DEFAULT 'lettura',

  created_at timestamptz NOT NULL DEFAULT now(),

  UNIQUE (document_id, user_id)
);

-- =========================
-- NOTE DOCUMENTO
-- =========================

CREATE TABLE document_notes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES app_users(id),

  note text NOT NULL,

  created_at timestamptz NOT NULL DEFAULT now()
);

-- =========================
-- EVENTI / STORICO
-- =========================

CREATE TABLE document_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  document_id uuid REFERENCES documents(id) ON DELETE CASCADE,
  user_id uuid REFERENCES app_users(id),

  event_type text NOT NULL,
  event_payload jsonb NOT NULL DEFAULT '{}',

  created_at timestamptz NOT NULL DEFAULT now()
);

-- =========================
-- IMPORTAZIONI
-- =========================

CREATE TABLE import_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  origin document_origin NOT NULL,
  started_by_user_id uuid REFERENCES app_users(id),

  status text NOT NULL DEFAULT 'pending',
  source_label text,
  details jsonb NOT NULL DEFAULT '{}',

  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

CREATE TABLE imported_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  import_job_id uuid REFERENCES import_jobs(id) ON DELETE CASCADE,
  document_id uuid REFERENCES documents(id) ON DELETE SET NULL,

  external_id text,
  original_name text,
  detected_mime_type text,

  status text NOT NULL DEFAULT 'imported',
  error_message text,

  created_at timestamptz NOT NULL DEFAULT now()
);

-- =========================
-- REVIEW AI
-- =========================

CREATE TABLE ai_review_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
  document_name text NOT NULL,

  category text,
  subcategory text,
  owner_name text,
  suggested_visibility document_visibility,
  relevant_date text,
  deadline text,
  recommended_action text,
  duplicate_of text,
  confidence numeric(5, 2),
  reason text,

  review_status ai_review_status NOT NULL DEFAULT 'pending',
  source_path text,

  imported_at timestamptz NOT NULL DEFAULT now(),
  applied_at timestamptz
);

-- =========================
-- KNOWLEDGE BASE RICORRENZE
-- =========================

CREATE TABLE document_patterns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  name text NOT NULL,
  sender text,
  provider text,
  keywords text[] NOT NULL DEFAULT '{}',
  category_id uuid REFERENCES categories(id),
  default_owner_user_id uuid REFERENCES app_users(id),
  default_visibility document_visibility NOT NULL DEFAULT 'privato',
  default_action text,
  confidence_boost numeric(5, 2) NOT NULL DEFAULT 0,

  examples jsonb NOT NULL DEFAULT '[]',
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- =========================
-- TRIGGER UPDATED_AT
-- =========================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_documents_updated_at
BEFORE UPDATE ON documents
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================
-- INDICI
-- =========================

CREATE INDEX idx_documents_owner ON documents(owner_user_id);
CREATE INDEX idx_documents_category ON documents(category_id);
CREATE INDEX idx_documents_visibility ON documents(visibility);
CREATE INDEX idx_documents_origin ON documents(origin);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_date ON documents(document_date);
CREATE INDEX idx_documents_expiry ON documents(expiry_date);
CREATE INDEX idx_documents_drive_file ON documents(drive_file_id);
CREATE INDEX idx_documents_tags ON documents USING gin(tags);
CREATE INDEX idx_documents_ai_keywords ON documents USING gin(ai_keywords);
CREATE INDEX idx_documents_ocr_text ON documents USING gin(to_tsvector('italian', coalesce(ocr_text, '')));
CREATE INDEX idx_document_files_document ON document_files(document_id);
CREATE INDEX idx_document_shares_user ON document_shares(user_id);
CREATE INDEX idx_ai_review_status ON ai_review_items(review_status);
CREATE INDEX idx_document_patterns_keywords ON document_patterns USING gin(keywords);
