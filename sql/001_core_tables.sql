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

CREATE TABLE IF NOT EXISTS subjects (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_id integer NOT NULL UNIQUE,
    project project NOT NULL,
    implant text
);

CREATE TABLE IF NOT EXISTS sessions (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_id integer NOT NULL,
    date date NOT NULL,

    CONSTRAINT sessions_subject_id_fkey
        FOREIGN KEY (subject_id)
        REFERENCES subjects (subject_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT sessions_id_subject_id_key
        UNIQUE (id, subject_id)
);

CREATE TABLE IF NOT EXISTS insertions (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_id integer NOT NULL,
    session_id integer NOT NULL,
    probe_letter text NOT NULL,
    is_deep boolean NOT NULL,

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
        CHECK (probe_letter ~ '^[A-Z]$')
);
