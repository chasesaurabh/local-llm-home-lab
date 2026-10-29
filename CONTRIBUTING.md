# Proposed contribution guide

The author selected the MIT license and repository destination `chasesaurabh/local-llm-home-lab`. This local preparation has not created a public repository or contribution intake. Contribution intake and support arrangements remain to be established before accepting public contributions; this guide makes no support commitment. See LICENSE for the package license.

Keep a change narrow and map it to the exercise and book code release it affects. Use only synthetic or explicitly licensed fixtures. Preserve deliberately failing teaching baselines and negative tests unless the exercise itself changes. Record exact runtime/model/helper identity, distinguish static tests from actual inference and include failures rather than keeping only successful attempts.

Never overwrite a frozen manifest or claim old test results apply unchanged to edited code. A later candidate gets a new identifier and hash manifest. Run deterministic checks in a disposable working copy; live tests need the documented isolated lab and a coordinated request/service window. Do not include private evidence, screenshots of accounts, secrets, application volumes, model weights or book prose in code submissions.

Changes to runtime/model versions, API contracts, output paths or safety guards require fresh relevant execution. Native Windows, WSL, bare-metal Linux, macOS and different GPU backends are distinct test claims. The default branch may eventually evolve; the book must cite a tested immutable tag and commit.
