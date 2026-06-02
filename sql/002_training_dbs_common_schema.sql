/*
Common schema observed across training_dbs/*.sqlite.

Inputs inspected:
- training_dbs/DynamicRoutingTraining.sqlite
  - 220 tables total
  - 219 per-mouse session tables
  - 12,407 session rows
  - all_mice has 224 rows
- training_dbs/DynamicRoutingTrainingNSB.sqlite
  - 218 tables total
  - 217 per-mouse session tables
  - 12,729 session rows
  - all_mice has 230 rows

Legacy shape:
- Each mouse has one table named by mouse id.
- all per-mouse tables have an INTEGER primary key named ID.
- all non-ID columns are declared TEXT in SQLite.
- No indexes or foreign keys were observed beyond the rowid primary key.

Session-table differences:
- DynamicRoutingTraining.sqlite has pass and does not have computer_name.
- DynamicRoutingTrainingNSB.sqlite has computer_name and does not have pass.

List-valued session metrics:
- hits, dprime_same_modality, and dprime_other_modality_go_stim are stored
  as text in SQLite, usually as bracketed arrays like [0.3] or [19, 19, 17].
- Legacy [nan] values should be loaded as NULL array elements.
- Legacy scalar values like 0 should be loaded as single-element arrays.

all_mice differences:
- Common columns:
  mouse_id, status, purpose, alive, genotype, sex, birthdate, whc, dhc,
  implant, cannula, cannula_loc, virus, virus_loc, regimen
- DynamicRoutingTraining.sqlite only:
  timeouts, trainer, next_task_version
- DynamicRoutingTrainingNSB.sqlite only:
  data_path
*/

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

CREATE TABLE IF NOT EXISTS training_subjects (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nsb boolean NOT NULL,
    legacy_id integer,
    mouse_id integer NOT NULL,

    status text,
    purpose text,
    alive boolean,
    genotype text,
    sex sex,
    birthdate date,
    whc text,
    dhc text,
    implant text,
    cannula text,
    cannula_loc text,
    virus text,
    virus_loc text,
    regimen text,

    -- Present only in DynamicRoutingTraining.sqlite all_mice.
    timeouts text,
    trainer text,
    next_task_version text,

    -- Present only in DynamicRoutingTrainingNSB.sqlite all_mice.
    data_path text,
    CONSTRAINT training_subjects_nsb_mouse_id_key
        UNIQUE (nsb, mouse_id)
);

CREATE TABLE IF NOT EXISTS training_sessions (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nsb boolean NOT NULL,
    mouse_id integer NOT NULL,
    legacy_session_id integer NOT NULL,

    start_time text,
    rig_name text,

    -- Present only in DynamicRoutingTrainingNSB.sqlite session tables.
    computer_name text,

    task_version text,
    hits double precision[],
    dprime_same_modality double precision[],
    dprime_other_modality_go_stim double precision[],
    quiescent_violations integer,

    -- Present only in DynamicRoutingTraining.sqlite session tables.
    pass_status text,

    ignore boolean,
    hab boolean,
    ephys boolean,
    muscimol boolean,
    CONSTRAINT training_sessions_subject_fkey
        FOREIGN KEY (nsb, mouse_id)
        REFERENCES training_subjects (nsb, mouse_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT training_sessions_nsb_mouse_legacy_key
        UNIQUE (nsb, mouse_id, legacy_session_id)
);

CREATE INDEX IF NOT EXISTS training_sessions_mouse_id_idx
    ON training_sessions (mouse_id);

CREATE INDEX IF NOT EXISTS training_sessions_start_time_idx
    ON training_sessions (start_time);
