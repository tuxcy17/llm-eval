# Bac à sable Harbor

Premier benchmark local d'un agent de codage avec [Harbor](https://docs.harborframework.com) (testé avec **Harbor 0.23.0**).
Les tâches sont des « issues à résoudre » dans l'esprit de SWE-bench, posées sur une codebase hébergée dans un **dépôt externe** ([tuxcy17/fake-app](https://github.com/tuxcy17/fake-app)) à une révision donnée. On les fait résoudre par Claude Code.

## Arborescence

```
harbor-sandbox/
├── specs/                         # SOURCE DE VÉRITÉ : une spec par tâche (dépôt + révision, patchs, limites)
├── tasks/                         # tâches Harbor GÉNÉRÉES par scripts/make_task.py (une par dossier)
│   ├── fix-bulk-discount/         # bugfix : seuil de remise volume (> au lieu de >=)
│   ├── fix-pagination/            # bugfix : dernière page partielle perdue (division entière)
│   ├── fix-slugify-accents/       # bugfix : accents traités comme séparateurs
│   └── add-coupon-code/           # feature : Cart.apply_coupon (difficulté medium)
│   Chaque tâche contient :
│   ├── instruction.md             # l'issue, telle qu'un utilisateur l'écrirait
│   ├── task.toml                  # timeouts et ressources
│   ├── environment/               # Dockerfile ; app/ = codebase récupérée du dépôt externe (non versionnée), 1 seul commit git
│   ├── solution/                  # correctif de référence (agent « oracle »)
│   └── tests/                     # tests cachés + test.sh (injectés dans /tests à la vérification)
├── scripts/
│   ├── make_task.py               # specs/<nom>/ → tasks/<nom>/ (--all pour toutes)
│   ├── check_prereqs.sh           # phase 0
│   ├── run_oracle.sh              # phase 3 : solution de référence → resolved = 1
│   ├── run_nop.sh                 # phase 4 : agent qui ne fait rien → resolved = 0, p2p = 1
│   ├── run_claude.sh              # phase 5 : Claude Code, un job par modèle et par tâche, 3 essais, 3 en parallèle
│   ├── extract_metrics.py         # phase 6 : jobs/ → docs/metrics.csv + résumé
│   ├── plot_metrics.py            # phase 6 : docs/metrics.csv → docs/comparison.html (graphiques par modèle)
│   ├── view.sh                    # phase 6 : interface web de navigation dans jobs/
│   └── build_ca_base_image.sh     # contournement optionnel pour proxy TLS (voir plus bas)
└── docs/
    ├── harbor-run-help.txt        # sortie de `harbor run --help` (référence des options)
    ├── metrics.csv
    └── REPORT.md                  # résultats et observations
```

## La codebase des tâches

Le code vit dans [tuxcy17/fake-app](https://github.com/tuxcy17/fake-app), un dépôt Python minuscule (`pricing/`, `paging/`, `textutils/`) à l'historique linéaire. Chaque tâche est un couple (révision de base, commit de correction), comme en SWE-bench : l'**état donné à l'agent est le parent du commit de correction**, et le diff de ce commit fournit le correctif de référence et les tests cachés.

| Tâche | Base (parent) | Commit de correction |
|---|---|---|
| `fix-bulk-discount` | `5137975` | `c7a3aae` Apply the bulk discount from 10 units |
| `fix-pagination` | `c7a3aae` | `2660c64` Count the last partial page |
| `fix-slugify-accents` | `2660c64` | `8dfba35` Strip accents when slugifying |
| `add-coupon-code` | `8dfba35` | `18f3b94` Add coupon codes to the cart |

Pour chaque tâche : les tests existants à la base sont les PASS_TO_PASS (visibles par l'agent, ne doivent pas casser) ; le fichier de tests ajouté par le commit de correction est le FAIL_TO_PASS (caché, appliqué à la vérification). Le verifier (`tests/test.sh`) écrit `/logs/verifier/reward.json` : `{"resolved": f2p*p2p, "f2p": 0|1, "p2p": 0|1}`, même si pytest plante.

> L'historique du dépôt est public : l'agent ne le voit pas (l'image ne contient qu'un commit, sans remote), mais les commits de correction sont consultables sur GitHub.

## Générer une tâche depuis une spec

`tasks/<nom>/` est un **artefact généré** : ne l'éditez pas à la main. La source de vérité est `specs/<nom>/spec.toml` (dépôt + révision SHA, script de préparation optionnel, patch de tests cachés, patch de correction, limites, ressources).

```bash
scripts/make_task.py --all               # génère toutes les tâches (à faire après un clone)
scripts/make_task.py fix-bulk-discount   # écrase tasks/fix-bulk-discount/
```

- `tasks/*/environment/app/` n'est **pas versionné** : il est récupéré du dépôt externe à la génération. Lancez `scripts/make_task.py --all` avant les scripts `run_*.sh` sur un clone neuf.
- La révision est récupérée **sur l'hôte** (`git fetch --depth 1` du seul SHA), puis copiée dans l'image : les dépôts privés utilisent vos identifiants locaux, aucun secret ne finit dans une couche Docker, et l'agent ne voit aucun historique amont.
- `source.setup` (optionnel) s'exécute dans `/app` au build, avant le commit de référence unique.
- `[limits]` produit les timeouts de `task.toml` ; `max_turns` et `max_budget_usd` vont dans `limits.env` (non lu par Harbor, destiné à `run_claude.sh`).
- Guide complet pour écrire une tâche : [docs/WRITING_TASKS.md](docs/WRITING_TASKS.md).
- Après génération, rejouez `run_oracle.sh` (resolved = 1) puis `run_nop.sh` (resolved = 0, p2p = 1).

## Mode d'emploi

Prérequis : Docker avec le plugin compose, `uv`, puis `uv tool install harbor`.

```bash
cd harbor-sandbox

# 0. Prérequis (n'affiche jamais le jeton)
export CLAUDE_CODE_OAUTH_TOKEN=...      # généré par `claude setup-token`, jamais écrit dans un fichier
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN
scripts/check_prereqs.sh

# 1. Générer les tâches (récupère la codebase du dépôt externe)
scripts/make_task.py --all

# 3-4. Valider les tâches avec les agents de contrôle (aucun quota consommé)
scripts/run_oracle.sh        # attendu : resolved = 1 sur chaque tâche
scripts/run_nop.sh           # attendu : resolved = 0, p2p = 1 sur chaque tâche

# 5. Claude Code (consomme le quota de l'abonnement)
scripts/run_claude.sh                   # évalue tous les modèles de MODELS (en tête du script)
CLAUDE_MODELS="claude-sonnet-5-5" scripts/run_claude.sh   # ou un sous-ensemble ponctuel
N_CONCURRENT=1 scripts/run_claude.sh          # essais en parallèle (défaut 3, compté en essais et non en tâches)
```

Les scripts `run_*.sh` visent par défaut tout le dossier `tasks/` (3 essais par tâche et par modèle pour Claude). Pour cibler :

```bash
TASKS="add-coupon-code fix-pagination" scripts/run_claude.sh   # des tâches par nom
TASK_PATH=tasks/add-coupon-code scripts/run_claude.sh          # une seule tâche
scripts/run_claude.sh -i 'fix-*'                        # filtre glob Harbor
```

Ajouter une tâche = écrire une spec dans `specs/` et la générer (voir [docs/WRITING_TASKS.md](docs/WRITING_TASKS.md)), puis valider avec oracle et nop avant tout run d'agent.

```bash

# 6. Métriques
python3 scripts/extract_metrics.py      # → docs/metrics.csv
python3 scripts/plot_metrics.py         # → docs/comparison.html (ouvrir dans un navigateur)
scripts/view.sh                         # navigateur de trajectoires (http://127.0.0.1:8080)
```

`run_claude.sh` lance, pour chaque modèle, **un `harbor run` par tâche** (job `claude-code-<modèle>-<horodatage>-<tâche>`, 3 essais en parallèle) et passe `--ak max_turns=…` / `--ak max_budget_usd=…` d'après `tasks/<nom>/limits.env`, quand ces limites sont définies dans la spec. Sans limite, seuls les timeouts de `task.toml` s'appliquent. `TASKS` restreint les tâches lancées (par défaut : toutes).

Les résultats bruts vont dans `jobs/<job>/<task>__<id>/`. Ce dossier est ignoré par git, car il contient les transcriptions complètes de l'agent.

### Authentification de Claude Code

L'agent `claude-code` de Harbor lit `CLAUDE_CODE_OAUTH_TOKEN` dans l'environnement du shell **au moment du run**, puis le transmet au conteneur. Par défaut, une `ANTHROPIC_API_KEY` présente serait prioritaire. `run_claude.sh` refuse donc de démarrer si elle est définie, et positionne `CLAUDE_FORCE_OAUTH=1`, une option de Harbor qui ne transmet que le jeton d'abonnement. Il retire aussi `ANTHROPIC_BASE_URL`, que Harbor relaierait à l'agent. Après le run, il vérifie que le jeton n'apparaît nulle part dans `jobs/`.

### Réseau derrière un proxy TLS (poste d'entreprise, sandbox cloud)

Si les conteneurs passent par un proxy qui intercepte TLS, `apt` (et sans doute les téléchargements de `uv`, non vérifié : `UV_NATIVE_TLS=1` est à essayer) échoue dans `docker build` avec l'erreur `CERTIFICATE_VERIFY_FAILED`. `scripts/build_ca_base_image.sh <ca.crt>` reconstruit alors localement `python:3.12-slim` **sous le même tag**, avec le CA ajouté. Le Dockerfile de la tâche reste inchangé. Si les miroirs Debian sont eux aussi bloqués, passez une image source qui contient déjà git (`... python:3.12-slim python:3.12`) : le Dockerfile n'installe git via apt que s'il est absent.

## Enseignements clés

1. **Une tâche Harbor = 4 éléments** : `instruction.md`, `environment/`, `tests/` (montés dans `/tests` seulement à la vérification) et `solution/` (utilisée par l'agent `oracle`).
2. **`oracle` et `nop` sont intégrés** et indispensables. Ils prouvent que la tâche est soluble et qu'elle n'est pas résolue d'avance, sans consommer de tokens.
3. **Un `reward.json` peut porter plusieurs clés.** Harbor agrège chaque clé (`F2P`, `P2P`, `Resolved` dans le tableau de fin de job).
4. **La doc peut diverger de la version installée.** Ici, le code source de Harbor dans le venv `uv` a servi de référence (schéma `task.toml`, chemins, format ATIF), et `harbor task init` génère un squelette canonique.
5. **Le réseau est le vrai sujet en entreprise.** L'installation de l'agent dans le conteneur nécessite `apt` (nodejs, npm, curl) et `downloads.claude.ai`. L'inférence nécessite `api.anthropic.com`.
6. **`--ak max_turns=N` est bien appliqué** (`claude --max-turns N` dans le conteneur), mais Harbor 0.23.0 étiquette alors l'essai `ApiRateLimitError` alors que Claude s'est simplement arrêté (`error_max_turns`, code de sortie 1) : le flux contient des `rate_limit_event`. L'essai est quand même vérifié. `extract_metrics.py` lit la ligne `result` de `agent/claude-code.txt` pour exposer `stop_reason` et `num_turns`. Ne pas utiliser `--retry-include ApiRateLimitError` dans ce cas.

Détails et chiffres : [docs/REPORT.md](docs/REPORT.md).
