CREATE SCHEMA IF NOT EXISTS sam;

SET search_path TO sam;

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
        'male',
        'female'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE session_kind AS ENUM (
        'production_ephys',
        'muscimol',
        'other'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE workflow_state AS ENUM (
        'not_started',
        'queued',
        'in_progress',
        'blocked',
        'needs_review',
        'completed',
        'skipped',
        'not_applicable'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE TYPE workflow_readiness AS ENUM (
        'not_ready',
        'maybe',
        'ready'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

CREATE TABLE IF NOT EXISTS staff_members (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    display_name text NOT NULL UNIQUE,
    initials text,
    email text UNIQUE,
    active boolean NOT NULL DEFAULT true,
    notes text
);

CREATE TABLE IF NOT EXISTS rigs (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rig_name text NOT NULL UNIQUE,
    active boolean NOT NULL DEFAULT true,
    notes text
);

CREATE TABLE IF NOT EXISTS subjects (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_id integer NOT NULL UNIQUE,
    project project NOT NULL,
    is_nsb boolean,
    status text,
    purpose text,
    alive boolean,
    genotype text,
    sex sex,
    birthdate date,
    whc boolean,
    dhc boolean,
    implant text,
    cannula boolean,
    cannula_location text,
    virus text,
    virus_location text,
    regimen text,
    timeouts text,
    trainer text,
    next_task_version text,
    data_path text,
    line text,
    experiment_type text,
    rig_id integer,
    surgery_prep text,
    duragel boolean,
    behavior_failed boolean,
    notes text,
    source_sheet text,
    source_row integer,

    CONSTRAINT subjects_rig_id_fkey
        FOREIGN KEY (rig_id)
        REFERENCES rigs (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT subjects_subject_id_check
        CHECK (subject_id > 0),

    CONSTRAINT subjects_source_row_check
        CHECK (source_row IS NULL OR source_row > 0)
);

ALTER TABLE subjects ADD COLUMN IF NOT EXISTS is_nsb boolean;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS status text;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS purpose text;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS alive boolean;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS genotype text;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS sex sex;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS birthdate date;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS whc boolean;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS dhc boolean;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS cannula boolean;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS cannula_location text;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS virus text;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS virus_location text;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS regimen text;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS timeouts text;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS trainer text;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS next_task_version text;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS data_path text;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS source_sheet text;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS source_row integer;

CREATE TABLE IF NOT EXISTS sessions (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_id integer NOT NULL,
    date date NOT NULL,
    session_kind session_kind NOT NULL DEFAULT 'production_ephys',
    experiment_label text,
    implant text,
    dye text,
    rig_id integer,
    probes_in_brain text,
    insertion_config text,
    stims_run text,
    retracted_100 boolean,
    probe_locator text,
    surface_channel_recording boolean,
    needs_upload boolean,
    external_session_ids text[],
    notes text,
    source_sheet text,
    source_row integer,

    CONSTRAINT sessions_subject_id_fkey
        FOREIGN KEY (subject_id)
        REFERENCES subjects (subject_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT sessions_rig_id_fkey
        FOREIGN KEY (rig_id)
        REFERENCES rigs (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT sessions_id_subject_id_key
        UNIQUE (id, subject_id),

    CONSTRAINT sessions_source_row_check
        CHECK (source_row IS NULL OR source_row > 0)
);

CREATE TABLE IF NOT EXISTS insertions (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_id integer NOT NULL,
    session_id integer NOT NULL,
    probe_letter text NOT NULL,
    is_deep boolean NOT NULL DEFAULT false,
    was_inserted boolean NOT NULL DEFAULT true,
    target_location text,
    depth_um integer,
    depth_notes text,
    injection_distance_mm numeric(8, 3),
    notes text,

    CONSTRAINT insertions_subject_id_fkey
        FOREIGN KEY (subject_id)
        REFERENCES subjects (subject_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT insertions_session_id_subject_id_fkey
        FOREIGN KEY (session_id, subject_id)
        REFERENCES sessions (id, subject_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT insertions_session_id_probe_letter_key
        UNIQUE (session_id, probe_letter),

    CONSTRAINT insertions_probe_letter_check
        CHECK (probe_letter ~ '^[A-F]$'),

    CONSTRAINT insertions_depth_um_check
        CHECK (depth_um IS NULL OR depth_um >= 0),

    CONSTRAINT insertions_injection_distance_mm_check
        CHECK (injection_distance_mm IS NULL OR injection_distance_mm >= 0)
);

CREATE TABLE IF NOT EXISTS subject_workflows (
    subject_id integer PRIMARY KEY,
    recording_week_start date,
    recorded_days text,
    perfusion_date date,
    experiment_perfusion_notes text,
    surgery_feedback_submitted boolean,
    surgery_feedback_notes text,

    imaging_type text,
    imaging_completed boolean,
    imaging_completed_at date,
    stitching_completed boolean,
    stitching_completed_at date,
    neuroglancer_mirrored boolean,

    probes_inserted_days text,
    probes_annotated_days text,
    channels_aligned_by text,
    channels_aligned_notes text,

    days_resorted text,
    realignment_ready boolean,
    realignment_ready_notes text,
    realigner_staff_id integer,
    realignment_notes text,
    first_pass_done boolean,
    realignment_done boolean,
    general_notes text,
    source_sheet text,
    source_row integer,

    CONSTRAINT subject_workflows_subject_id_fkey
        FOREIGN KEY (subject_id)
        REFERENCES subjects (subject_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT subject_workflows_realigner_staff_id_fkey
        FOREIGN KEY (realigner_staff_id)
        REFERENCES staff_members (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT subject_workflows_source_row_check
        CHECK (source_row IS NULL OR source_row > 0)
);

CREATE TABLE IF NOT EXISTS session_injections (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id integer NOT NULL,
    substance text NOT NULL,
    volume_nl numeric(10, 3),
    volume_notes text,
    injection_location text,
    concentration_ug_per_ul numeric(10, 4),
    concentration_notes text,
    rate_nl_per_sec numeric(10, 4),
    rate_notes text,
    settle_time_minutes numeric(10, 3),
    settle_time_notes text,
    finished_at time,
    finished_at_notes text,
    pipette_inner_diameter_um numeric(10, 3),
    beveled_30_degrees boolean,
    labeling_site_notes text,
    notes text,
    source_sheet text,
    source_row integer,

    CONSTRAINT session_injections_session_id_fkey
        FOREIGN KEY (session_id)
        REFERENCES sessions (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT session_injections_volume_nl_check
        CHECK (volume_nl IS NULL OR volume_nl >= 0),

    CONSTRAINT session_injections_concentration_check
        CHECK (concentration_ug_per_ul IS NULL OR concentration_ug_per_ul >= 0),

    CONSTRAINT session_injections_rate_check
        CHECK (rate_nl_per_sec IS NULL OR rate_nl_per_sec >= 0),

    CONSTRAINT session_injections_settle_time_check
        CHECK (settle_time_minutes IS NULL OR settle_time_minutes >= 0),

    CONSTRAINT session_injections_pipette_inner_diameter_check
        CHECK (pipette_inner_diameter_um IS NULL OR pipette_inner_diameter_um >= 0),

    CONSTRAINT session_injections_source_row_check
        CHECK (source_row IS NULL OR source_row > 0)
);

CREATE TABLE IF NOT EXISTS smartspim_imaging_requests (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_id integer NOT NULL,
    experiment_label text,
    deep_recordings text,
    perfusion_date date,
    clearing_method text,
    cleared_date date,
    clearing_duration_days integer,
    imaged_date date,
    uploaded_date date,
    stitched_date date,
    data_available_latency_days integer,
    queue_notes text,
    reprocessed_date date,
    processing_notes text,
    needs_reprocessing boolean,
    reprocessing_requested boolean,
    neuroglancer_url text,
    annotation_status workflow_state NOT NULL DEFAULT 'not_started',
    annotator_staff_id integer,
    converted_asset_name text,
    converted_asset_id text,
    source_sheet text,
    source_row integer,

    CONSTRAINT smartspim_imaging_requests_subject_id_fkey
        FOREIGN KEY (subject_id)
        REFERENCES subjects (subject_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT smartspim_imaging_requests_annotator_staff_id_fkey
        FOREIGN KEY (annotator_staff_id)
        REFERENCES staff_members (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT smartspim_clearing_duration_days_check
        CHECK (clearing_duration_days IS NULL OR clearing_duration_days >= 0),

    CONSTRAINT smartspim_data_available_latency_days_check
        CHECK (data_available_latency_days IS NULL OR data_available_latency_days >= 0),

    CONSTRAINT smartspim_source_row_check
        CHECK (source_row IS NULL OR source_row > 0)
);

CREATE TABLE IF NOT EXISTS slide_imaging_requests (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_id integer NOT NULL,
    training_history text,
    virus_tracers text,
    injection_location text,
    perfusion_date date,
    sectioned_date date,
    slide_barcodes text,
    submitted_for_imaging_date date,
    directory_path text,
    channels text,
    imaged_date date,
    imaging_latency_days integer,
    slides_retrieved boolean,
    notes text,
    source_sheet text,
    source_row integer,

    CONSTRAINT slide_imaging_requests_subject_id_fkey
        FOREIGN KEY (subject_id)
        REFERENCES subjects (subject_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT slide_imaging_latency_days_check
        CHECK (imaging_latency_days IS NULL OR imaging_latency_days >= 0),

    CONSTRAINT slide_imaging_source_row_check
        CHECK (source_row IS NULL OR source_row > 0)
);

CREATE TABLE IF NOT EXISTS alignment_cases (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_id integer NOT NULL,
    experiment_label text,
    recorded_days text,
    deep_insertions text,
    probes_not_inserted text,
    neuroglancer_url text,
    annotated_neuroglass_url text,
    upload_complete boolean,
    sorting_complete boolean,
    converted_asset_name text,
    converted_asset_id text,
    converted_asset_notes text,
    manifest_asset text,
    alignment_readiness workflow_readiness NOT NULL DEFAULT 'not_ready',
    source_sheet text,
    source_row integer,

    CONSTRAINT alignment_cases_subject_id_fkey
        FOREIGN KEY (subject_id)
        REFERENCES subjects (subject_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT alignment_cases_subject_experiment_key
        UNIQUE (subject_id, experiment_label),

    CONSTRAINT alignment_cases_source_row_check
        CHECK (source_row IS NULL OR source_row > 0)
);

CREATE TABLE IF NOT EXISTS alignment_reviews (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alignment_case_id integer NOT NULL,
    aligner_staff_id integer,
    completed_date date,
    save_location text,
    confidence smallint,
    qc_noise boolean NOT NULL DEFAULT false,
    qc_drift boolean NOT NULL DEFAULT false,
    qc_low_yield boolean NOT NULL DEFAULT false,
    qc_brain_damage boolean NOT NULL DEFAULT false,
    notes text,
    source_sheet text,
    source_row integer,

    CONSTRAINT alignment_reviews_alignment_case_id_fkey
        FOREIGN KEY (alignment_case_id)
        REFERENCES alignment_cases (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT alignment_reviews_aligner_staff_id_fkey
        FOREIGN KEY (aligner_staff_id)
        REFERENCES staff_members (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT alignment_reviews_confidence_check
        CHECK (confidence IS NULL OR confidence BETWEEN 1 AND 5),

    CONSTRAINT alignment_reviews_source_row_check
        CHECK (source_row IS NULL OR source_row > 0)
);

CREATE TABLE IF NOT EXISTS workflow_tasks (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_id integer,
    session_id integer,
    insertion_id integer,
    smartspim_imaging_request_id integer,
    slide_imaging_request_id integer,
    alignment_case_id integer,
    task_name text NOT NULL,
    task_kind text,
    status workflow_state NOT NULL DEFAULT 'not_started',
    readiness workflow_readiness,
    priority smallint NOT NULL DEFAULT 0,
    assigned_to_staff_id integer,
    requested_at timestamptz NOT NULL DEFAULT now(),
    due_date date,
    started_at timestamptz,
    completed_at timestamptz,
    blocked_reason text,
    external_reference text,
    source_sheet text,
    source_row integer,
    notes text,

    CONSTRAINT workflow_tasks_subject_id_fkey
        FOREIGN KEY (subject_id)
        REFERENCES subjects (subject_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT workflow_tasks_session_id_fkey
        FOREIGN KEY (session_id)
        REFERENCES sessions (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT workflow_tasks_insertion_id_fkey
        FOREIGN KEY (insertion_id)
        REFERENCES insertions (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT workflow_tasks_smartspim_imaging_request_id_fkey
        FOREIGN KEY (smartspim_imaging_request_id)
        REFERENCES smartspim_imaging_requests (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT workflow_tasks_slide_imaging_request_id_fkey
        FOREIGN KEY (slide_imaging_request_id)
        REFERENCES slide_imaging_requests (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT workflow_tasks_alignment_case_id_fkey
        FOREIGN KEY (alignment_case_id)
        REFERENCES alignment_cases (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT workflow_tasks_assigned_to_staff_id_fkey
        FOREIGN KEY (assigned_to_staff_id)
        REFERENCES staff_members (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT workflow_tasks_priority_check
        CHECK (priority BETWEEN 0 AND 5),

    CONSTRAINT workflow_tasks_completed_after_started_check
        CHECK (
            completed_at IS NULL
            OR started_at IS NULL
            OR completed_at >= started_at
        ),

    CONSTRAINT workflow_tasks_source_row_check
        CHECK (source_row IS NULL OR source_row > 0)
);

CREATE TABLE IF NOT EXISTS workflow_task_events (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id integer NOT NULL,
    event_at timestamptz NOT NULL DEFAULT now(),
    from_status workflow_state,
    to_status workflow_state,
    staff_id integer,
    notes text,

    CONSTRAINT workflow_task_events_task_id_fkey
        FOREIGN KEY (task_id)
        REFERENCES workflow_tasks (id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT workflow_task_events_staff_id_fkey
        FOREIGN KEY (staff_id)
        REFERENCES staff_members (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT workflow_task_events_has_status_or_notes_check
        CHECK (
            from_status IS NOT NULL
            OR to_status IS NOT NULL
            OR notes IS NOT NULL
        )
);

CREATE INDEX IF NOT EXISTS subjects_project_idx
    ON subjects (project);

CREATE INDEX IF NOT EXISTS subjects_is_nsb_idx
    ON subjects (is_nsb);

CREATE INDEX IF NOT EXISTS subjects_rig_id_idx
    ON subjects (rig_id);

CREATE INDEX IF NOT EXISTS sessions_subject_id_date_idx
    ON sessions (subject_id, date);

CREATE INDEX IF NOT EXISTS sessions_session_kind_idx
    ON sessions (session_kind);

CREATE INDEX IF NOT EXISTS sessions_rig_id_idx
    ON sessions (rig_id);

CREATE INDEX IF NOT EXISTS insertions_subject_id_idx
    ON insertions (subject_id);

CREATE INDEX IF NOT EXISTS insertions_session_id_idx
    ON insertions (session_id);

CREATE INDEX IF NOT EXISTS session_injections_session_id_idx
    ON session_injections (session_id);

CREATE INDEX IF NOT EXISTS smartspim_imaging_requests_subject_id_idx
    ON smartspim_imaging_requests (subject_id);

CREATE INDEX IF NOT EXISTS smartspim_imaging_requests_annotation_status_idx
    ON smartspim_imaging_requests (annotation_status);

CREATE INDEX IF NOT EXISTS slide_imaging_requests_subject_id_idx
    ON slide_imaging_requests (subject_id);

CREATE INDEX IF NOT EXISTS alignment_cases_subject_id_idx
    ON alignment_cases (subject_id);

CREATE INDEX IF NOT EXISTS alignment_cases_readiness_idx
    ON alignment_cases (alignment_readiness);

CREATE INDEX IF NOT EXISTS alignment_reviews_alignment_case_id_idx
    ON alignment_reviews (alignment_case_id);

CREATE INDEX IF NOT EXISTS workflow_tasks_subject_id_idx
    ON workflow_tasks (subject_id);

CREATE INDEX IF NOT EXISTS workflow_tasks_status_idx
    ON workflow_tasks (status);

CREATE INDEX IF NOT EXISTS workflow_tasks_assigned_due_idx
    ON workflow_tasks (assigned_to_staff_id, due_date);

CREATE INDEX IF NOT EXISTS workflow_task_events_task_id_event_at_idx
    ON workflow_task_events (task_id, event_at);
