# Juniper Lab maintenance — revision 3

Document ID: MAINT-001. Revision: 3. Effective: 2026-11-01. Status: current. Supersedes revisions 1 and 2. Synthetic training fixture; apply only in the after-update scenario.

## Maintenance window
The current maintenance window is Wednesday at 18:30. This is Juniper Lab local wall-clock time. No time zone is specified in these notes.

## Backup location
The current backup folder is lab-backups-v3. The backup job writes one snapshot before each maintenance window.

## Backup retention
Retain backup snapshots for 21 days. Remove an expired snapshot only after a newer restore check succeeds.

## Maintenance authorization
Before maintenance, check that the most recent restore verification succeeded. If verification failed, postpone maintenance and investigate the backup. Do not treat a successful copy alone as proof of recovery.
