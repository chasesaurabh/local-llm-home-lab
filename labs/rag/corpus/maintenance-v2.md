# Juniper Lab maintenance — revision 2

Document ID: MAINT-001. Revision: 2. Effective: 2026-10-01. Status: current. Supersedes revision 1. Synthetic training fixture; no real operational instructions.

## Maintenance window
The current maintenance window is Sunday at 09:00. This is Juniper Lab local wall-clock time. No time zone is specified in these notes.

## Backup location
The current backup folder is lab-backups. The backup job writes one snapshot before each maintenance window.

## Backup retention
Retain backup snapshots for 14 days. Remove an expired snapshot only after a newer restore check succeeds.

## Maintenance authorization
Before maintenance, check that the most recent restore verification succeeded. If verification failed, postpone maintenance and investigate the backup. Do not treat a successful copy alone as proof of recovery.
