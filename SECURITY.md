# Proposed security policy

This unpublished local candidate has no public security-reporting channel yet. The repository owner must designate a private reporting destination and supported release policy before publication; no address or support commitment is invented here.

Use synthetic data for these labs. Do not submit passwords, environment files, API keys, session tokens, backups, model weights, original user documents, database files, application logs or private generated answers with a report. Record a minimal synthetic reproduction, exact helper hash, runtime/model version and expected versus actual behavior. Review the report before sharing it.

Local model output and retrieved documents are untrusted. The coding helper proposes text for manual review; the agent permits only bounded note reads and one draft. Neither should be expanded to execute arbitrary model-generated commands. The adversarial notes are deliberate synthetic tests and must not be followed.

Measurement performs inference and selected-model unloads. Backup deliberately quiesces the owned source and restores to separate resources. Read the plan and guards before execution. Retain the original working volume and known-good archive after a failed attempt; no broad cleanup is included. Restricted archive permissions are not encryption, and same-user DPAPI is not portable secret recovery.

Loopback bindings and the recorded authentication checks do not establish a secure internet-facing or multi-device deployment. Keep these examples on the documented local lab path until separately reviewed and tested. The shared probe logs retrieved synthetic content and cannot establish every authorization boundary.

Before any future push or release, inspect the explicit distribution list, run secret and dependency checks for the exact candidate, resolve findings, and compare the final manifest. Ignore rules are defense in depth, not proof that content is safe to publish.
