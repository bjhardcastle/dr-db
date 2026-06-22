


DO $$
BEGIN
    CREATE TYPE implant_id AS ENUM (
        '2001',
        '2002',
        '2005',
        '2006',
        '2011',
        '2014',
        '2015'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE project AS ENUM (
        'DynamicRouting',
        'Templeton'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE sex AS ENUM (
        'M',
        'F'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE session_kind AS ENUM (
        'brainwide_survey',
        'muscimol',
        'virus_test',
        'hab',
        'dye_test',
        'training',
        'other'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE session_type AS ENUM (
        'ephys',
        'behavior_with_sync'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE subject_status AS ENUM (
        'dead',
        'training',
        'www'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

CREATE TABLE IF NOT EXISTS implant (
    id text PRIMARY KEY,
    dhc boolean DEFAULT false
);

CREATE TABLE IF NOT EXISTS subject (
    id integer PRIMARY KEY,
    status subject_status,
    purpose text,
    project project NOT NULL,
    nsb boolean,
    genotype text,
    sex sex,
    birth_date date,
    surgery_prep text,
    surgery_notes text,
    implant_id implant_id,
    cannula_location text,
    virus text,
    virus_location text,
    regimen integer,
    timeouts boolean,
    trainer text,
    next_task_version text,
    duragel boolean DEFAULT false,
    notes text,

    CONSTRAINT subjects_implant_id_fkey
        FOREIGN KEY (implant_id)
        REFERENCES implant (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT subjects_subject_id_check
        CHECK (id > 0)
);

CREATE TABLE IF NOT EXISTS surgical_procedures (
    subject_id integer NOT NULL,
    procedure text NOT NULL,
    date date NOT NULL,
    implant_id implant_id,

    CONSTRAINT surgical_procedures_pkey
        PRIMARY KEY (subject_id, procedure, date),

    CONSTRAINT surgical_procedures_id_fkey
        FOREIGN KEY (subject_id)
        REFERENCES subject (id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS session (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    folder text NOT NULL,
    project text NOT NULL DEFAULT 'DynamicRouting',
    session_type session_type NOT NULL DEFAULT 'ephys',
    ephys_day integer,
    perturbation_day integer,
    is_production boolean NOT NULL DEFAULT true,
    is_split_recording boolean NOT NULL DEFAULT false,
    is_context_naive boolean NOT NULL DEFAULT false,
    is_injection_perturbation boolean NOT NULL DEFAULT false,
    is_opto_perturbation boolean NOT NULL DEFAULT false,
    is_deep_insertion boolean NOT NULL DEFAULT false,
    probe_letters_to_skip text NOT NULL DEFAULT '',
    surface_recording_probe_letters_to_skip text NOT NULL DEFAULT '',

    CONSTRAINT session_project_check
        CHECK (project IN ('DynamicRouting', 'TempletonPilotSession')),

    CONSTRAINT session_ephys_day_check
        CHECK (ephys_day IS NULL OR ephys_day > 0),

    CONSTRAINT session_perturbation_day_check
        CHECK (perturbation_day IS NULL OR perturbation_day > 0),

    CONSTRAINT session_probe_letters_to_skip_check
        CHECK (probe_letters_to_skip ~ '^[A-F]{0,6}$'),

    CONSTRAINT session_surface_recording_probe_letters_to_skip_check
        CHECK (surface_recording_probe_letters_to_skip ~ '^[A-F]{0,6}$'),

    CONSTRAINT session_folder_project_type_key
        UNIQUE (folder, project, session_type)
);
