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
base_image = "ubuntu:24.04"          # optionnel (défaut : ubuntu:24.04)
packages = ["python3", "python3-pytest", "python-is-python3"]   # optionnel
# pip = ["requests"]                 # optionnel : paquets Python
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
| `environment.base_image` | non | Défaut `ubuntu:24.04`. N'importe quelle image Linux : voir « Choisir l'image de base ». |
| `environment.packages` | non | Paquets système à installer (outils de build, JDK, etc.). |
| `environment.pip` | non | Paquets Python ; l'image doit fournir `pip`. |
| `limits.*_timeout_sec` | oui | Enforcés par Harbor. `build_timeout_sec` couvre aussi `setup.sh` : prévoyez large pour un vrai projet. |
| `limits.max_turns`, `max_budget_usd` | non | Ne sont **pas** lus par Harbor : écrits dans `limits.env`, transmis par `run_claude.sh` à l'agent (`--ak`). |

## Choisir l'image de base

`base_image` est le `FROM` du Dockerfile généré. **Défaut : `ubuntu:24.04`**, adaptée à Python, Java et C. Le générateur ne suppose ni Python ni Debian :

- **Le gestionnaire de paquets est détecté** (`apt-get`, `apk`, `dnf`, `microdnf` ou `yum`).
- **`git` et `bash` sont ajoutés automatiquement** s'ils manquent : le premier sert au commit de référence, le second à `test.sh`, `solve.sh` et `setup.sh`.
- **`packages`** liste les paquets système du projet. Les noms dépendent de la distribution.
- **`pip`** n'est utilisé que s'il est renseigné ; l'image doit fournir `python3` et `pip` (sur Ubuntu : paquet `python3-pip`). `PIP_BREAK_SYSTEM_PACKAGES=1` est positionné, car Ubuntu protège le Python système (PEP 668) et le conteneur est jetable.

### Ubuntu 24.04 : points d'attention

- Il n'y a pas de commande `python`, seulement `python3` : ajoutez `python-is-python3` si `tests.command` appelle `python`.
- Pour pytest, `python3-pytest` (apt) évite `pip`.
- Python y est en version 3.12.

### Exemples

```toml
# Python
[environment]
packages = ["python3", "python3-pytest", "python-is-python3"]

# C (CMake)
[environment]
packages = ["build-essential", "cmake"]

# Java (Maven)
[environment]
packages = ["openjdk-21-jdk-headless", "maven"]
```

Les installations de ces trois jeux de paquets sur `ubuntu:24.04` ont été testées (gcc 13.3, cmake 3.28, javac 21, Maven 3.8.7, pytest, pip). **Les tâches Java et C elles-mêmes (compilation, tests, run d'un agent) n'ont pas été testées de bout en bout.**

### Java et C : à prévoir

- **Commande de test** : `test.sh` exécute `<command> <f2p>` puis `<command> <p2p>`, chaque élément de la liste étant un argument. Cela convient à pytest, mais aussi, en théorie, à Maven (`command = "mvn -q -B test"`, `f2p = ["-Dtest=BulkDiscountTest"]`) ou à CTest (`command = "ctest --test-dir build --output-on-failure"`, `f2p = ["-R", "bulk"]`).
- **Compilation** : pour C, il faut compiler après l'application de `tests.patch` ; le générateur n'a pas d'étape de build dédiée aujourd'hui. Il faudrait l'ajouter (par exemple `tests.build`) ou passer par un script du dépôt.
- **Dépendances** : Maven télécharge ses dépendances. Préchargez-les dans `setup.sh` (`mvn -B dependency:go-offline`) pour que le build ne dépende pas du réseau pendant l'évaluation, et ajoutez-les au temps de `build_timeout_sec`.
- **Ressources** : un build Java ou C est plus gourmand que pytest ; augmentez `memory_mb` et `cpus` si nécessaire.

Les images testées avec Dockerfile généré : `ubuntu:24.04` (et tâche pilote), `python:3.12-slim`, `alpine:3.20`, `fedora:40`. L'installation de l'agent `claude-code` dans le conteneur par Harbor (nodejs, npm, curl) n'a été éprouvée que sur Debian/Ubuntu ; sur Alpine ou RHEL, vérifiez-la avec un run réel.

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
- **Changer d'image change le `task_checksum`** : les résultats d'avant et d'après ne sont pas comparables sans le noter.
- **Dépôt privé** : le clone utilise vos identifiants locaux, et aucun secret n'est copié dans l'image.
