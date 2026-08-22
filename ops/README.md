# Operations and deployment configuration

This directory contains deployment-time configuration that is safe to keep in
Git. It deliberately excludes passwords, host-specific paths, and generated
backup files.

Install the example cron schedule on the production host with:

```bash
sudo crontab -u dr-db -l
sudo crontab -u dr-db ops/cron/dr-db.crontab
```

Before installing it, edit the repository path and choose the uncommented
tasks. The service account must be able to run Docker and read the external
Compose env file.

For a new scheduled operation, add a wrapper under `scripts/tasks/`, test it
manually, then add one line to `ops/cron/dr-db.crontab`.
