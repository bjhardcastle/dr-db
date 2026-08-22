# Cron schedules

`dr-db.crontab` is the version-controlled schedule for the production host.
Cron invokes `scripts/run-task.sh`, which supplies locking and delegates the
actual work to a task wrapper.

Cron has a minimal environment. Use absolute paths, put secrets in a host-only
Compose env file, and redirect output to a host log directory. Keep schedules
commented until the corresponding task has been implemented and tested.

For important production jobs, systemd timers are also a reasonable deployment
option; keep the task wrappers unchanged if the scheduler is later migrated.
