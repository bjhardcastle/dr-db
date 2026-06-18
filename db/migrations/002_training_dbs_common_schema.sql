/*
Common schema observed across the SQLite files in training_dbs.

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

Subject rows from all_mice load into sam.subjects. Legacy mouse_id is stored as
subjects.subject_id, nsb is stored as subjects.is_nsb, and *_loc columns are
expanded to *_location.
*/

CREATE SCHEMA IF NOT EXISTS sam;

SET search_path TO sam;

DO $$
BEGIN
    IF to_regclass('training_subjects') IS NOT NULL THEN
        INSERT INTO subjects (
            subject_id,
            project,
            is_nsb,
            status,
            purpose,
            alive,
            genotype,
            sex,
            birthdate,
            whc,
            dhc,
            implant,
            cannula,
            cannula_location,
            virus,
            virus_location,
            regimen,
            timeouts,
            trainer,
            next_task_version,
            data_path,
            source_sheet,
            source_row
        )
        SELECT
            mouse_id,
            'DynamicRouting'::project,
            nsb,
            status,
            purpose,
            alive,
            genotype,
            sex,
            birthdate,
            whc,
            dhc,
            implant,
            cannula,
            cannula_loc,
            virus,
            virus_loc,
            regimen,
            timeouts,
            trainer,
            next_task_version,
            data_path,
            CASE
                WHEN nsb THEN 'DynamicRoutingTrainingNSB.sqlite:all_mice'
                ELSE 'DynamicRoutingTraining.sqlite:all_mice'
            END,
            id
        FROM training_subjects
        ON CONFLICT (subject_id) DO UPDATE SET
            project = EXCLUDED.project,
            is_nsb = EXCLUDED.is_nsb,
            status = EXCLUDED.status,
            purpose = EXCLUDED.purpose,
            alive = EXCLUDED.alive,
            genotype = EXCLUDED.genotype,
            sex = EXCLUDED.sex,
            birthdate = EXCLUDED.birthdate,
            whc = EXCLUDED.whc,
            dhc = EXCLUDED.dhc,
            implant = EXCLUDED.implant,
            cannula = EXCLUDED.cannula,
            cannula_location = EXCLUDED.cannula_location,
            virus = EXCLUDED.virus,
            virus_location = EXCLUDED.virus_location,
            regimen = EXCLUDED.regimen,
            timeouts = EXCLUDED.timeouts,
            trainer = EXCLUDED.trainer,
            next_task_version = EXCLUDED.next_task_version,
            data_path = EXCLUDED.data_path,
            source_sheet = EXCLUDED.source_sheet,
            source_row = EXCLUDED.source_row;
    END IF;
END
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
            AND table_name = 'training_sessions'
            AND column_name = 'mouse_id'
    )
    AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
            AND table_name = 'training_sessions'
            AND column_name = 'subject_id'
    ) THEN
        ALTER TABLE training_sessions RENAME COLUMN mouse_id TO subject_id;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS training_sessions (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_id integer NOT NULL,

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
    pass boolean,

    ignore boolean,
    hab boolean,
    ephys boolean,
    muscimol boolean,

    CONSTRAINT training_sessions_subject_fkey
        FOREIGN KEY (subject_id)
        REFERENCES subjects (subject_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

ALTER TABLE IF EXISTS training_sessions
    DROP CONSTRAINT IF EXISTS training_sessions_subject_fkey;

ALTER TABLE training_sessions
    ADD CONSTRAINT training_sessions_subject_fkey
        FOREIGN KEY (subject_id)
        REFERENCES subjects (subject_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT;

DROP INDEX IF EXISTS training_sessions_mouse_id_idx;

DROP TABLE IF EXISTS training_subjects;

CREATE INDEX IF NOT EXISTS training_sessions_subject_id_idx
    ON training_sessions (subject_id);

CREATE INDEX IF NOT EXISTS training_sessions_start_time_idx
    ON training_sessions (start_time);
