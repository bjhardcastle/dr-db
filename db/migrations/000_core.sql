


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
    CREATE TYPE session_type AS ENUM (
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
    CREATE TYPE platform AS ENUM (
        'ephys',
        'fip',
        'behavior_with_sync',
        'behavior'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE asset_type AS ENUM (
        'raw',
        'sorted',
        'lp_face',
        'lp_body',
        'eye_tracking',
        'gamma_correct_vid',
        'ibl_conversion_manifest',
        'neuroglancer_state',
        'smartspim',
        'smartspim_stitched',
        'ibl_converted',
        'nwb'
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
    subject_id integer NOT NULL,
    date date NOT NULL,
    ignore boolean,
    project project NOT NULL,
    platform platform NOT NULL,
    session_type session_type NOT NULL,
    rig_id rig_id,
    ephys_day integer,
    perturbation_day integer,
    task_version text,
    hits double precision[],
    dprime_same_modality double precision[],
    dprime_other_modality_go_stim double precision[],
    quiescent_violations integer,
    pass boolean,
    is_production boolean NOT NULL DEFAULT true,
    is_split_recording boolean NOT NULL DEFAULT false,
    is_context_naive boolean NOT NULL DEFAULT false,
    is_injection_perturbation boolean NOT NULL DEFAULT false,
    is_opto_perturbation boolean NOT NULL DEFAULT false,
    notes text,

    CONSTRAINT session_ephys_day_check
        CHECK (ephys_day IS NULL OR ephys_day > 0),

    CONSTRAINT session_perturbation_day_check
        CHECK (perturbation_day IS NULL OR perturbation_day > 0),

    CONSTRAINT session_probe_letters_to_skip_check
        CHECK (probe_letters_to_skip ~ '^[A-F]{0,6}$'),

    CONSTRAINT session_surface_recording_probe_letters_to_skip_check
        CHECK (surface_recording_probe_letters_to_skip ~ '^[A-F]{0,6}$'),

    CONSTRAINT session_pkey
        PRIMARY KEY (subject_id, date)
);

CREATE TABLE IF NOT EXISTS asset (
    id uuid PRIMARY KEY,
    subject_id integer NOT NULL,
    session_date date,
    name text,
    type asset_type,
    notes text,

    CONSTRAINT asset_subject_id_fkey
        FOREIGN KEY (subject_id)
        REFERENCES subject (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT asset_session_fkey
        FOREIGN KEY (subject_id, session_date)
        REFERENCES session (subject_id, date)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS insertions (
    subject_id integer NOT NULL,
    date date NOT NULL,
    probe_letter text NOT NULL,
    was_inserted boolean NOT NULL DEFAULT true,
    ignore boolean NOT NULL DEFAULT false,
    retracted_100 boolean,
    unsortable boolean,
    has_surface_channel_recording boolean,
    target_location text,
    dye text,
    depth_um integer,
    is_deep boolean,
    depth_notes text,
    injection_distance_mm numeric(8, 3),
    notes text,

    CONSTRAINT insertions_pkey
        PRIMARY KEY (subject_id, date, probe_letter),

    CONSTRAINT insertions_subject_id_fkey
        FOREIGN KEY (subject_id)
        REFERENCES subject (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT insertions_probe_letter_check
        CHECK (probe_letter ~ '^[A-F]$'),

    CONSTRAINT insertions_depth_um_check
        CHECK (depth_um IS NULL OR depth_um >= 0),

    CONSTRAINT insertions_injection_distance_mm_check
        CHECK (injection_distance_mm IS NULL OR injection_distance_mm >= 0),

    CONSTRAINT insertions_unsortable_implies_ignore_check
        CHECK (unsortable IS NOT TRUE OR ignore IS TRUE),

    CONSTRAINT insertions_depth_implies_is_deep_check
        CHECK (depth_um IS NULL OR is_deep = (depth_um > 3000))
);

CREATE OR REPLACE FUNCTION set_insertion_ignore_for_unsortable()
RETURNS trigger AS $$
BEGIN
    IF NEW.unsortable IS TRUE THEN
        NEW.ignore := true;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS insertions_set_ignore_for_unsortable ON insertions;

CREATE TRIGGER insertions_set_ignore_for_unsortable
    BEFORE INSERT OR UPDATE OF unsortable, ignore
    ON insertions
    FOR EACH ROW
    EXECUTE FUNCTION set_insertion_ignore_for_unsortable();

CREATE OR REPLACE FUNCTION set_insertion_is_deep_for_depth()
RETURNS trigger AS $$
BEGIN
    NEW.is_deep := NEW.depth_um > 3000;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS insertions_set_is_deep_for_depth ON insertions;

CREATE TRIGGER insertions_set_is_deep_for_depth
    BEFORE INSERT OR UPDATE OF depth_um, is_deep
    ON insertions
    FOR EACH ROW
    EXECUTE FUNCTION set_insertion_is_deep_for_depth();
