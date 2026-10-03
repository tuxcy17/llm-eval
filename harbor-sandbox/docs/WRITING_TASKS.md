# Écrire une tâche d'évaluation

Une tâche se **déclare** dans `specs/<nom>/`, puis `scripts/make_task.py` génère `tasks/<nom>/`, le dossier que Harbor exécute. On n'édite jamais `tasks/<nom>/` à la main : il est écrasé à chaque génération.

```
specs/<nom>/                    ← ce que vous écrivez
├── spec.toml                   source, tests, limites, ressources
├── instruction.md              l'issue, telle qu'un utilisateur l'écrirait
├── tests.patch                 tests cachés (FAIL_TO_PASS, éventuellement PASS_TO_PASS)
├── fix.patch                   correctif de référence
└── setup.sh                    (optionnel) préparation de la codebase

        scripts/make_task.py <nom>
                  ▼
tasks/<nom>/                    ← généré, versionné, ne pas éditer
├── environment/{Dockerfile, app/, setup.sh}
├── instruction.md, task.toml, limits.env
├── tests/{test.sh, tests.patch}
└── solution/{solve.sh, fix.patch}
```

## Principe

1. La révision demandée du dépôt est récupérée **sur l'hôte** (`git fetch --depth 1` du seul SHA), avec vos identifiants git locaux. Elle est copiée dans l'image comme `/app`.
2. Si `setup` est défini, ce script s'exécute dans `/app` au build.
3. Un commit unique (`initial import`) fige l'état de départ : l'agent ne voit ni l'historique amont, ni remote, ni le correctif.
4. L'agent travaille dans `/app`. À la vérification, les tests cachés sont appliqués puis exécutés.
5. `reward.json` vaut `{"resolved": f2p*p2p, "f2p": 0|1, "p2p": 0|1}`.

## Écrire `spec.toml`

Modèle complet (les chemins sont relatifs au dossier de la spec) :

```toml
name = "fix-bulk-discount"          # = nom du dossier specs/<nom>/
instruction = "instruction.md"

[source]
repo = "https://github.com/org/pricing.git"   # URL git ou chemin local
revision = "753a28a68d3caba953d1074f33b13198f9ff9453"
subdir = "services/pricing"                    # optionnel
setup = "setup.sh"                             # optionnel

[tests]
patch = "tests.patch"
command = "python -m pytest -rA -p no:cacheprovider"
f2p = ["tests/test_bulk_discount.py"]
p2p = ["tests/test_cart.py"]

[solution]
patch = "fix.patch"

[environment]
base_image = "python:3.12-slim"
pip = ["pytest"]                     # optionnel
cpus = 1
memory_mb = 1024
storage_mb = 2048

[limits]
build_timeout_sec = 300
agent_timeout_sec = 600
verifier_timeout_sec = 120
# max_turns = 30                     # optionnel
# max_budget_usd = "2.00"            # optionnel

[metadata]                           # optionnel
difficulty = "easy"
category = "bugfix"
tags = ["python"]
```

| Champ | Obligatoire | Notes |
|---|---|---|
| `source.repo` | oui | URL git, ou chemin local (résolu depuis le dossier de la spec). |
| `source.revision` | oui | **SHA complet de 40 caractères.** Une branche ou un tag est refusé, car il n'est pas reproductible. Pour résoudre une branche : `git ls-remote <repo> <branche>`. |
| `source.subdir` | non | Ce sous-dossier devient `/app`. Les chemins des patchs sont alors relatifs à lui. |
| `source.setup` | non | Voir « Préparer la codebase ». |
| `tests.command` | oui | Commande préfixant la liste de fichiers de `f2p`, puis de `p2p`. |
| `tests.f2p` | oui | Fichiers de tests qui échouent avant le correctif et réussissent après. |
| `tests.p2p` | oui | Fichiers de tests qui réussissent avant et après. |
| `environment.base_image` | oui | `git` est installé via `apt` s'il manque. |
| `limits.*_timeout_sec` | oui | Enforcés par Harbor. `build_timeout_sec` couvre aussi `setup.sh` : prévoyez large pour un vrai projet. |
| `limits.max_turns`, `max_budget_usd` | non | Ne sont **pas** lus par Harbor : écrits dans `limits.env`, transmis par `run_claude.sh` à l'agent (`--ak`). |

## Écrire l'instruction

`instruction.md` est le seul texte vu par l'agent. Rédigez-la comme une issue d'utilisateur : le symptôme et le comportement attendu, sans indiquer le fichier fautif ni la solution. Précisez où se trouve le code (`/app`).

## Produire `tests.patch` et `fix.patch`

À partir d'un commit de base et d'un commit de correction (`<base>`, `<fix>`), depuis la racine de l'application (le `subdir` s'il y en a un) :

```bash
cd <repo>/<subdir>
git diff --relative <base> <fix> -- tests > /chemin/specs/<nom>/tests.patch
git diff --relative <base> <fix> -- . ':(exclude)tests' > /chemin/specs/<nom>/fix.patch
```

`--relative` est indispensable avec un `subdir` : les chemins des patchs doivent être ceux vus depuis `/app`. Adaptez `tests` au dossier réel de tests du projet.

Règles :

- `tests.patch` ne contient que des tests. Les fichiers qu'il touche sont **réinitialisés** par `test.sh` (restaurés depuis le commit de base, ou supprimés s'ils sont nouveaux) avant application : si l'agent a modifié ou créé un de ces fichiers, ses changements sont écartés.
- Les fichiers listés dans `f2p` doivent figurer dans `tests.patch`, ou exister déjà dans le dépôt.
- Les fichiers de `p2p` doivent réussir sur la révision de base : ce sont les garde-fous contre la régression.
- `fix.patch` est le correctif de référence de l'agent `oracle`. Il doit s'appliquer sur la révision de base.

Pour un bug sans commit de correction (tâche construite à la main), créez les patchs depuis un dépôt temporaire : commit de l'état buggé, modification, `git diff`.

## Préparer la codebase (`setup.sh`)

Script bash exécuté **au build**, dans `/app`, avant le commit de référence. Usages typiques : installer les dépendances, compiler, générer des fichiers.

```bash
#!/bin/bash
set -euo pipefail
pip install --no-cache-dir -e .
```

- Il s'exécute une fois à la construction de l'image, jamais pendant le temps de l'agent, et il est mis en cache par Docker.
- Le réseau doit être accessible pendant le build (voir la section proxy TLS du README).
- Ce que le script crée et que `.gitignore` n'exclut pas fait partie de l'état de référence : l'agent verra un arbre git propre.
- Le script est supprimé de l'image après exécution.
- Un échec fait échouer le build : testez-le avant de lancer l'agent.

## Générer et valider

```bash
scripts/make_task.py <nom>            # génère tasks/<nom>/
TASK=<nom> scripts/run_oracle.sh      # attendu : resolved = 1
TASK=<nom> scripts/run_nop.sh         # attendu : resolved = 0 et p2p = 1
```

Sans `TASK`, ces deux scripts visent `fix-bulk-discount`.

Une tâche n'est utilisable que si les deux contrôles passent :

| Contrôle | Résultat attendu | Sinon |
|---|---|---|
| oracle | `resolved=1` | `fix.patch` ne s'applique pas, ou les tests cachés échouent même avec le correctif. |
| nop | `resolved=0`, `p2p=1` | La tâche est déjà résolue, ou un test `p2p` échoue sur la base. |

## Lancer l'agent

```bash
export CLAUDE_CODE_OAUTH_TOKEN=...          # jamais dans un fichier
TASKS="<nom>" scripts/run_claude.sh claude-sonnet-5-5 --n-attempts 1
```

`run_claude.sh` lance un `harbor run` par tâche et passe `--ak max_turns` / `--ak max_budget_usd` si la spec les définit. Sans `TASKS`, il lance toutes les tâches de `tasks/`.

Résultats : `python3 scripts/extract_metrics.py` (colonnes `task`, `task_checksum`, `stop_reason`, `num_turns`…) ou `harbor view jobs`.

> Un essai arrêté par `max_turns` est affiché `ApiRateLimitError` par Harbor 0.23.0 alors que le quota est sain. La colonne `stop_reason` donne la vraie cause (`max_turns`, `completed`…).

## Pièges

- **Ne jamais éditer `tasks/<nom>/`** : modifiez la spec, puis régénérez. Après un changement de spec, le `task_checksum` change.
- **`git archive` ne copie ni les sous-modules ni les fichiers marqués `export-ignore`** dans `.gitattributes`. Si votre projet en dépend, préparez-les dans `setup.sh`.
- **`git apply` dans un dépôt** ignore les chemins hors du dossier courant. Pour vérifier un patch à la main, exécutez `git apply --check` depuis la racine de l'application, pas depuis un autre sous-dossier.
- **Le SHA doit être joignable** : un `fetch` d'un commit non référencé par une branche peut échouer selon le serveur. Choisissez un commit présent sur une branche.
- **`fix.patch` n'est validé que par l'oracle** : lancez-le systématiquement après une génération.
- **Dépôt privé** : le clone utilise vos identifiants locaux, et aucun secret n'est copié dans l'image.
