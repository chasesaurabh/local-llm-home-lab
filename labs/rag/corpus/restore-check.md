# Juniper Lab restore check

Document ID: RESTORE-002. Revision: 1. Effective: 2026-10-01. Status: current. Synthetic training fixture.

## Restore verification
Restore a snapshot into the scratch folder restore-scratch. Check that the restored sentinel file health-note.txt contains exactly JUNIPER-READY. Record a pass only when the restored file contains that text. A missing file or different text is a failed restore verification.

## Failure recovery
On a failed restore verification, preserve the failed snapshot for investigation and try the previous snapshot in restore-scratch. Do not overwrite the working lab data during this check.
