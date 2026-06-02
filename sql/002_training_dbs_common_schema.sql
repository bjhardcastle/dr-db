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
- DynamicRoutingTraining.sqlite columns:
  ARRAY[
      'ID',
      'start_time',
      'rig_name',
      'task_version',
      'hits',
      'dprime_same_modality',
      'dprime_other_modality_go_stim',
      'quiescent_violations',
      'pass',
      'ignore',
      'hab',
      'ephys',
      'muscimol'
  ]::text[]
- DynamicRoutingTrainingNSB.sqlite columns:
  ARRAY[
      'ID',
      'start_time',
      'rig_name',
      'computer_name',
      'task_version',
      'hits',
      'dprime_same_modality',
      'dprime_other_modality_go_stim',
      'quiescent_violations',
      'ignore',
      'hab',
      'ephys',
      'muscimol'
  ]::text[]

all_mice differences:
- Common columns:
  ARRAY[
      'mouse_id',
      'status',
      'purpose',
      'alive',
      'genotype',
      'sex',
      'birthdate',
      'whc',
      'dhc',
      'implant',
      'cannula',
      'cannula_loc',
      'virus',
      'virus_loc',
      'regimen'
  ]::text[]
- DynamicRoutingTraining.sqlite only:
  ARRAY[
      'timeouts',
      'trainer',
      'next_task_version'
  ]::text[]
- DynamicRoutingTrainingNSB.sqlite only:
  ARRAY[
      'data_path'
  ]::text[]
*/

CREATE TABLE IF NOT EXISTS training_subjects (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_database text NOT NULL,
    legacy_id integer,
    mouse_id integer NOT NULL,

    status text,
    purpose text,
    alive text,
    genotype text,
    sex text,
    birthdate text,
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

    CONSTRAINT training_subjects_source_database_check
        CHECK (source_database IN (
            'DynamicRoutingTraining',
            'DynamicRoutingTrainingNSB'
        )),

    CONSTRAINT training_subjects_source_database_mouse_id_key
        UNIQUE (source_database, mouse_id)
);

CREATE TABLE IF NOT EXISTS training_sessions (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_database text NOT NULL,
    mouse_id integer NOT NULL,
    legacy_session_id integer NOT NULL,

    start_time text,
    rig_name text,

    -- Present only in DynamicRoutingTrainingNSB.sqlite session tables.
    computer_name text,

    task_version text,
    hits text,
    dprime_same_modality text,
    dprime_other_modality_go_stim text,
    quiescent_violations text,

    -- Present only in DynamicRoutingTraining.sqlite session tables.
    pass_status text,

    ignore boolean,
    hab boolean,
    ephys boolean,
    muscimol boolean,

    CONSTRAINT training_sessions_source_database_check
        CHECK (source_database IN (
            'DynamicRoutingTraining',
            'DynamicRoutingTrainingNSB'
        )),

    CONSTRAINT training_sessions_subject_fkey
        FOREIGN KEY (source_database, mouse_id)
        REFERENCES training_subjects (source_database, mouse_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT training_sessions_source_mouse_legacy_key
        UNIQUE (source_database, mouse_id, legacy_session_id)
);

CREATE INDEX IF NOT EXISTS training_sessions_mouse_id_idx
    ON training_sessions (mouse_id);

CREATE INDEX IF NOT EXISTS training_sessions_start_time_idx
    ON training_sessions (start_time);
