# Bac à sable Harbor

Premier benchmark local d'un agent de codage avec [Harbor](https://docs.harborframework.com) (testé avec **Harbor 0.23.0**).
Une mini-codebase Python contient un bug connu. On en fait une tâche Harbor « issue à résoudre », dans l'esprit de SWE-bench, puis on la fait résoudre par Claude Code.

## Arborescence

```
harbor-sandbox/
├── project/                       # codebase de référence (état CORRIGÉ)
├── tasks/                         # une tâche Harbor par dossier
│   ├── fix-bulk-discount/         # bugfix : seuil de remise volume (> au lieu de >=)
│   ├── fix-pagination/            # bugfix : dernière page partielle perdue (division entière)
│   ├── fix-slugify-accents/       # bugfix : accents traités comme séparateurs
│   └── add-coupon-code/           # feature : Cart.apply_coupon (difficulté medium)
│   Chaque tâche contient :
│   ├── instruction.md             # l'issue, telle qu'un utilisateur l'écrirait
│   ├── task.toml                  # timeouts et ressources
│   ├── environment/               # image Docker : /app en état BUGGÉ, 1 seul commit git
│   ├── solution/solve.sh          # correctif de référence (agent « oracle »)
│   └── tests/                     # tests cachés + test.sh (injectés dans /tests à la vérification)
├── scripts/
│   ├── check_prereqs.sh           # phase 0
│   ├── run_oracle.sh              # phase 3 : solution de référence → resolved = 1
│   ├── run_nop.sh                 # phase 4 : agent qui ne fait rien → resolved = 0, p2p = 1
│   ├── run_claude.sh              # phase 5 : Claude Code, 3 essais, concurrence 1
│   ├── extract_metrics.py         # phase 6 : jobs/ → docs/metrics.csv + résumé
│   └── build_ca_base_image.sh     # contournement optionnel pour proxy TLS (voir plus bas)
└── docs/
    ├── harbor-run-help.txt        # sortie de `harbor run --help` (référence des options)
    ├── metrics.csv
    └── REPORT.md                  # résultats et observations
```

## Le bug

Règle métier : toute ligne dont la quantité est **≥ 10** bénéficie de 10 % de remise.
La version buggée (`environment/app/pricing/cart.py`) teste `quantity > 10`, donc une ligne de 10 unités exactement n'est pas remisée.

| Tests | Où | Rôle |
|---|---|---|
| `tests/test_cart.py` (7 cas, 8 tests) | dans l'image, visibles par l'agent | PASS_TO_PASS : ne doivent pas casser |
| `test_bulk_discount.py` (3 tests) | uniquement dans `tasks/.../tests/` | FAIL_TO_PASS : prouvent la correction |

Le verifier (`tests/test.sh`) écrit `/logs/verifier/reward.json` :
`{"resolved": f2p*p2p, "f2p": 0|1, "p2p": 0|1}`. Il écrit ce fichier même si pytest plante.

## Mode d'emploi

Prérequis : Docker avec le plugin compose, `uv`, puis `uv tool install harbor`.

```bash
cd harbor-sandbox

# 0. Prérequis (n'affiche jamais le jeton)
export CLAUDE_CODE_OAUTH_TOKEN=...      # généré par `claude setup-token`, jamais écrit dans un fichier
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN
scripts/check_prereqs.sh

# 1. Codebase : tests locaux hors Docker
(cd project && uvx --python 3.12 pytest -q)

# 3-4. Valider les tâches avec les agents de contrôle (aucun quota consommé)
scripts/run_oracle.sh        # attendu : resolved = 1 sur chaque tâche
scripts/run_nop.sh           # attendu : resolved = 0, p2p = 1 sur chaque tâche

# 5. Claude Code (consomme le quota de l'abonnement)
scripts/run_claude.sh <modèle>          # ex. claude-sonnet-5-5, toutes les tâches de tasks/
```

Les scripts `run_*.sh` visent par défaut tout le dossier `tasks/` (3 essais par tâche pour Claude). Pour cibler :

```bash
TASK_PATH=tasks/add-coupon-code scripts/run_claude.sh <modèle>   # une seule tâche
scripts/run_claude.sh <modèle> -i 'fix-*'                        # filtre glob Harbor
```

Ajouter une tâche = créer un dossier dans `tasks/` avec les 4 éléments ci-dessous, puis valider avec oracle et nop avant tout run d'agent.

```bash

# 6. Métriques
python3 scripts/extract_metrics.py      # → docs/metrics.csv
harbor view jobs                        # navigateur de trajectoires
```

Les résultats bruts vont dans `jobs/<job>/<task>__<id>/`. Ce dossier est ignoré par git, car il contient les transcriptions complètes de l'agent.

### Authentification de Claude Code

L'agent `claude-code` de Harbor lit `CLAUDE_CODE_OAUTH_TOKEN` dans l'environnement du shell **au moment du run**, puis le transmet au conteneur. Par défaut, une `ANTHROPIC_API_KEY` présente serait prioritaire. `run_claude.sh` refuse donc de démarrer si elle est définie, et positionne `CLAUDE_FORCE_OAUTH=1`, une option de Harbor qui ne transmet que le jeton d'abonnement. Il retire aussi `ANTHROPIC_BASE_URL`, que Harbor relaierait à l'agent. Après le run, il vérifie que le jeton n'apparaît nulle part dans `jobs/`.

### Réseau derrière un proxy TLS (poste d'entreprise, sandbox cloud)

Si les conteneurs passent par un proxy qui intercepte TLS, `pip` et `apt` échouent dans `docker build` avec l'erreur `CERTIFICATE_VERIFY_FAILED`. `scripts/build_ca_base_image.sh <ca.crt>` reconstruit alors localement `python:3.12-slim` **sous le même tag**, avec le CA ajouté. Le Dockerfile de la tâche reste inchangé. Si les miroirs Debian sont eux aussi bloqués, passez une image source qui contient déjà git (`... python:3.12-slim python:3.12`) : le Dockerfile n'installe git via apt que s'il est absent.

## Enseignements clés

1. **Une tâche Harbor = 4 éléments** : `instruction.md`, `environment/`, `tests/` (montés dans `/tests` seulement à la vérification) et `solution/` (utilisée par l'agent `oracle`).
2. **`oracle` et `nop` sont intégrés** et indispensables. Ils prouvent que la tâche est soluble et qu'elle n'est pas résolue d'avance, sans consommer de tokens.
3. **Un `reward.json` peut porter plusieurs clés.** Harbor agrège chaque clé (`F2P`, `P2P`, `Resolved` dans le tableau de fin de job).
4. **La doc peut diverger de la version installée.** Ici, le code source de Harbor dans le venv `uv` a servi de référence (schéma `task.toml`, chemins, format ATIF), et `harbor task init` génère un squelette canonique.
5. **Le réseau est le vrai sujet en entreprise.** L'installation de l'agent dans le conteneur nécessite `apt` (nodejs, npm, curl) et `downloads.claude.ai`. L'inférence nécessite `api.anthropic.com`.

Détails et chiffres : [docs/REPORT.md](docs/REPORT.md).
