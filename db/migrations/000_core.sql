


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
    implant_id text,
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

    CONSTRAINT surgical_procedures_pkey
        PRIMARY KEY (subject_id, procedure, date),

    CONSTRAINT surgical_procedures_id_fkey
        FOREIGN KEY (subject_id)
        REFERENCES subject (id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);
