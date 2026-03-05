-- ============================================================
-- SpecSense — Initial Schema Migration
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";

-- ============================================================
-- Custom Types
-- ============================================================
CREATE TYPE requirement_status AS ENUM ('draft', 'analyzed', 'validated', 'stale');

-- ============================================================
-- Trigger Function: set updated_at on every UPDATE
-- ============================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Table: projects
-- ============================================================
CREATE TABLE projects (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- Table: requirements
-- ============================================================
CREATE TABLE requirements (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id  UUID NOT NULL
                    REFERENCES projects(id)
                    ON DELETE CASCADE,
    status      requirement_status NOT NULL DEFAULT 'draft',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_requirements_project_id ON requirements(project_id);
CREATE INDEX idx_requirements_status     ON requirements(status);

CREATE TRIGGER trg_requirements_updated_at
    BEFORE UPDATE ON requirements
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- Table: requirement_versions  (append-only / immutable)
-- ============================================================
CREATE TABLE requirement_versions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    requirement_id  UUID NOT NULL
                        REFERENCES requirements(id)
                        ON DELETE CASCADE,
    version_number  INTEGER NOT NULL,
    text_content    TEXT NOT NULL,
    quality_score   NUMERIC(5,2),
    embedding       vector(1536),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_requirement_version
        UNIQUE (requirement_id, version_number)
);

CREATE INDEX idx_req_versions_requirement_id ON requirement_versions(requirement_id);

-- ============================================================
-- Immutability Guard: block UPDATE and DELETE on versions
-- ============================================================
CREATE OR REPLACE FUNCTION prevent_version_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'requirement_versions is immutable: % operations are not allowed',
        TG_OP;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_requirement_versions_no_update
    BEFORE UPDATE ON requirement_versions
    FOR EACH ROW
    EXECUTE FUNCTION prevent_version_mutation();

CREATE TRIGGER trg_requirement_versions_no_delete
    BEFORE DELETE ON requirement_versions
    FOR EACH ROW
    EXECUTE FUNCTION prevent_version_mutation();

-- ============================================================
-- Auto-increment version_number per requirement
-- ============================================================
CREATE OR REPLACE FUNCTION set_version_number()
RETURNS TRIGGER AS $$
BEGIN
    NEW.version_number := COALESCE(
        (SELECT MAX(version_number) FROM requirement_versions
         WHERE requirement_id = NEW.requirement_id),
        0
    ) + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_requirement_versions_set_version
    BEFORE INSERT ON requirement_versions
    FOR EACH ROW
    EXECUTE FUNCTION set_version_number();