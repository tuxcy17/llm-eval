# Rapport : bac à sable Harbor, 4 tâches

> **Statut : phases 0 à 4 terminées sur les 4 tâches (`fix-bulk-discount`, `fix-pagination`, `fix-slugify-accents`, `add-coupon-code`). Phases 5 à 7 en attente du feu vert de l'utilisateur.**
> Le run Claude Code consomme le quota de l'abonnement. Les sections marquées ⏳ seront complétées après ce run.

## Tâches

| Tâche | Catégorie | Difficulté | Description |
|---|---|---|---|
| `fix-bulk-discount` | bugfix | easy | `>` au lieu de `>=` sur le seuil de remise volume |
| `fix-pagination` | bugfix | easy | `total_pages` arrondit à l'inférieur : la dernière page partielle est inaccessible |
| `fix-slugify-accents` | bugfix | easy | les accents sont traités comme des séparateurs (`caf-cr-me`) |
| `add-coupon-code` | feature | medium | implémenter `Cart.apply_coupon` (2 codes, ordre d'application, arrondi final) |

Toutes suivent le même format (image Python 3.12, `/app` en un seul commit git, tests publics P2P dans l'image, tests cachés F2P dans `tests/`). Les phases 1 à 4 ci-dessous ont été détaillées pour `fix-bulk-discount` ; les trois autres ont été validées de la même façon (voir « Validation multi-tâches »).

## Environnement d'exécution

| Élément | Valeur |
|---|---|
| Harbor | 0.23.0 (`uv tool install harbor`, Python 3.13 dans le venv de l'outil) |
| Docker | Engine 29.6.2, compose 5.3.1, environnement Harbor `docker` |
| Hôte | Conteneur Linux éphémère (sandbox cloud Claude Code), **pas le poste de l'utilisateur** |
| Réseau | Proxy TLS d'inspection. `deb.debian.org`, `downloads.claude.ai` et `docs.harborframework.com` sont bloqués. PyPI, npm et Docker Hub sont autorisés. |

Conséquence : la doc en ligne de Harbor était inaccessible. Le schéma de `task.toml`, le chemin de montage des tests, le format de `reward.json`, la structure ATIF et la gestion du jeton OAuth ont été lus **dans le code source de Harbor 0.23.0** (`harbor/models/task/config.py`, `harbor/verifier/verifier.py`, `harbor/models/trial/paths.py`, `harbor/models/trajectories/`, `harbor/agents/installed/claude_code.py`), complété par `harbor task init`.

## Commandes par phase

| # | Commande | Résultat |
|---|---|---|
| 0 | `scripts/check_prereqs.sh` | Docker, compose et Harbor OK, `ANTHROPIC_API_KEY` et `ANTHROPIC_AUTH_TOKEN` absentes. **`CLAUDE_CODE_OAUTH_TOKEN` absent** dans la sandbox (requis uniquement en phase 5). `COLUMNS=200 harbor run --help > docs/harbor-run-help.txt` |
| 1 | `cd project && uvx --python 3.12 pytest -q` | 8 passed (référence corrigée + tests cachés OK) |
| 1 | `cd tasks/fix-bulk-discount/environment/app && uvx --python 3.12 pytest -q tests/test_cart.py` | 8 passed (tests publics OK sur la version buggée) |
| 1 | idem avec `test_bulk_discount.py` | **2 failed**, 1 passed (`quantity_ten`, `mixed_cart` KO ; `quantity_nine` OK) |
| 2 | `docker build -t …:check tasks/fix-bulk-discount/environment` | OK. Dans le conteneur : 0 fichier `test_bulk_discount.py`, `git rev-list --count HEAD` = 1 (« initial import »), 8 tests publics passent |
| 3 | `scripts/run_oracle.sh` (`harbor run --path tasks --agent oracle --env docker --jobs-dir jobs --n-concurrent 1`) | `resolved = 1` |
| 4 | `scripts/run_nop.sh` (idem avec `--agent nop`) | `resolved = 0`, `f2p = 0`, `p2p = 1` |
| 5 ⏳ | `scripts/run_claude.sh` (un job par modèle de `MODELS` : `--agent claude-code --model <modèle> --n-attempts 3 --n-concurrent 1`, avec `CLAUDE_FORCE_OAUTH=1`) | en attente |
| 6 | `python3 scripts/extract_metrics.py` | `docs/metrics.csv` (oracle et nop pour l'instant) |

Les agents de contrôle s'appellent bien `oracle` et `nop` dans Harbor 0.23.0 (liste de `--agent` dans `harbor run --help`).

## Validation multi-tâches

Les scripts `run_*.sh` visent tout le dossier `tasks/` (`--path tasks`, traité par Harbor comme un dataset ; `TASK_PATH` et `-i` permettent de filtrer). Avant Harbor, chaque nouvelle tâche a été vérifiée hors Docker : tests cachés en échec sur la version buggée, tout au vert une fois `solve.sh` appliqué. Puis, en local (Docker du poste de développement) :

| Commande | Résultat sur les 4 tâches |
|---|---|
| `scripts/run_oracle.sh` | Resolved 1.000 (4/4), F2P 1.000, P2P 1.000, 0 exception, ~1 min au total |
| `scripts/run_nop.sh` | Resolved 0.000, F2P 0.000, P2P 1.000, 0 exception |

Les lignes correspondantes ont été ajoutées à `docs/metrics.csv` (jobs `oracle-20261002-235832` et `nop-20261002-235940`). Le run Claude Code reste à faire.

## Résultats

Résultats de la première tâche (`fix-bulk-discount`, sandbox cloud) ; voir `docs/metrics.csv` pour le détail par tâche.

| Agent | Modèle | Essais | resolved | f2p | p2p | Durée essai | Tokens (in/out) | Étapes |
|---|---|---|---|---|---|---|---|---|
| oracle | – | 1 | **1** | 1 | 1 | 14,0 s | – | – |
| nop | – | 1 | **0** | 0 | 1 | 13,9 s | – | – |
| claude-code ⏳ | à choisir | 3 | | | | | | |

## Temps observés

| Étape | Durée | Source |
|---|---|---|
| Pull des images de base (`python:3.12-slim` + `python:3.12`) | ~20 s | une seule fois |
| Build de l'image de la tâche, à froid (`--no-cache`) | 5,5 s | `docker build` |
| Setup de l'environnement dans Harbor (build en cache + `compose up`) | 1,8 à 2,1 s | `environment_setup` dans `result.json` |
| Exécution oracle (`solve.sh`) | 0,24 s | `agent_execution` |
| Verifier (2 runs pytest) | ~0,7 s | `verifier` |
| **Essai complet** oracle ou nop | ~14 s | `started_at` → `finished_at`. Le reste (~10 s) correspond à l'arrêt et au nettoyage du conteneur (`--delete` par défaut). |
| Installation de Claude Code dans le conteneur ⏳ | non mesurable ici | voir « Problèmes » ; à mesurer sur le poste (`agent_setup`) |

## Problèmes rencontrés et contournements

1. **Doc Harbor inaccessible** (proxy). Le code source installé a servi de référence (voir plus haut). Effet de bord utile : on lit le comportement réel de la version installée.
2. **Daemon Docker non démarré** dans la sandbox. Je l'ai lancé (`dockerd`) ; rien n'a été installé.
3. **Harbor non installé.** Je l'ai installé avec `uv tool install harbor` dans le conteneur éphémère, qui sera détruit en fin de session. Écart assumé par rapport à « ne pas installer sans demander », car le poste de l'utilisateur n'est pas touché.
4. **Proxy TLS d'inspection** : `pip` et `apt` échouaient dans `docker build` avec `CERTIFICATE_VERIFY_FAILED`. Contournement : `scripts/build_ca_base_image.sh` reconstruit le tag local `python:3.12-slim` avec le CA du proxy. Le Dockerfile de la tâche reste inchangé, car Docker utilise le tag local sans re-pull. **Ce cas se retrouvera en entreprise** (proxy Zscaler, Bluecoat…).
5. **Miroirs Debian bloqués (403)** : `apt-get install git` est impossible. L'image shim est construite à partir de `python:3.12` (complète, avec git), et le Dockerfile n'installe git via apt que s'il est absent. Sur un poste normal, le chemin `apt` est utilisé.
6. **Installation de Claude Code impossible dans la sandbox.** Testée avec `harbor run … --agent claude-code --install-only` (aucun appel API, aucun quota consommé). L'agent exécute `apt-get install curl bash nodejs npm procps`, puis `curl https://downloads.claude.ai/claude-code-releases/bootstrap.sh | bash`. Ces deux hôtes sont bloqués ici. Le phénomène est propre à cette sandbox ; le run doit se faire sur le poste de l'utilisateur.
7. **Piège d'authentification identifié dans le code** : par défaut, l'agent `claude-code` de Harbor **préfère `ANTHROPIC_API_KEY`** au jeton OAuth s'ils coexistent, et relaie `ANTHROPIC_BASE_URL`. D'où `CLAUDE_FORCE_OAUTH=1` et `env -u ANTHROPIC_BASE_URL` dans `run_claude.sh`. Harbor masque les valeurs sensibles dans ses logs ; le script vérifie en plus après le run que le jeton n'apparaît pas dans `jobs/`.
8. **Résumé de fin de job** : le tableau « Reward / Count » de Harbor liste une ligne par clé de `reward.json`, sans nommer la clé. Il vaut mieux se fier au tableau `F2P / P2P / Resolved` ou à `extract_metrics.py`.

## Arborescence réelle des résultats (Harbor 0.23.0)

```
jobs/<job_name>/
├── config.json, result.json, job.log, lock.json
└── <task>__<suffix>/                # un dossier par essai
    ├── config.json, result.json     # TrialResult : agent_info, verifier_result.rewards,
    │                                # exception_info, started_at/finished_at par phase
    ├── trial.log, exception.txt (si erreur)
    ├── agent/                       # oracle.txt, trajectory.json (ATIF, agents LLM)
    └── verifier/reward.json, test-stdout.txt
```

Les champs ATIF utilisés sont `steps[]` et `final_metrics.{total_prompt_tokens, total_completion_tokens, total_cached_tokens, total_cost_usd, total_steps}`. Si ATIF est absent, l'extracteur se rabat sur `agent_result.{n_input_tokens, n_output_tokens, n_cache_tokens, cost_usd}`. Un essai sans récompense (`verifier_result` nul) est classé `infra_error`. Ce dernier point a été testé sur un jeu synthétique, faute de vrai cas.

## Adapter à une vraie codebase Java/Maven

- **Dépendances pré-téléchargées dans l'image** (`mvn dependency:go-offline`, ou `-Dmaven.repo.local` dans une couche dédiée). Sinon, chaque essai retélécharge la moitié de Maven Central, et l'agent comme le verifier deviennent dépendants du réseau.
- **Dépôt d'artefacts interne** (Nexus/Artifactory) : `settings.xml` en couche d'image, identifiants injectés au build (secret BuildKit), jamais en clair. Le CA du proxy d'entreprise doit être installé dans le JDK (`cacerts`) et dans l'OS (voir point 4).
- **Isolation réseau** : `task.toml` accepte `[environment] network_mode` et `allowed_hosts`, ainsi que des politiques par phase (`[agent]`, `[verifier]`). Viser par exemple : agent autorisé vers `api.anthropic.com` seulement, verifier hors-ligne. À valider sur le poste.
- **Installation de l'agent** : prévoir `apt` (nodejs, npm, curl) et `downloads.claude.ai`, ou **pré-installer `claude` dans l'image**. Harbor saute alors l'installation s'il trouve `claude` dans le `PATH` (`_installed_claude_satisfies_version`), ce qui fait gagner du temps et de la reproductibilité. On peut épingler la version avec `--ak version=X.Y.Z`.
- **Temps de build et de tests** : prévoir de relever `build_timeout_sec` et `[verifier] timeout_sec`, et cibler les tests (`mvn -pl module -Dtest=…`) plutôt que lancer toute la suite. Mesurer le P2P sur le sous-ensemble pertinent. Garder l'image construite (`--no-delete` ou registre local) entre les essais.
- **Historique git** : repartir d'un commit unique « initial import » (ou d'un historique tronqué avant le correctif) pour éviter que l'agent ne retrouve la solution par `git log`.
- **Ressources** : `cpus` et `memory_mb` dans `task.toml` (la JVM et Maven sont gourmands) ; 1 024 Mo suffisent ici, il en faudra plutôt 4 à 8 Go.

## Prochaines étapes

1. ⏳ Lancer la phase 5 sur le poste de l'utilisateur : `scripts/check_prereqs.sh && scripts/run_claude.sh` (modèles définis dans `MODELS`, ou `CLAUDE_MODELS="..."`).
2. ⏳ `python3 scripts/extract_metrics.py` (toutes tâches), puis compléter les tableaux « Résultats » et « Temps observés » (installation de l'agent).
3. ✅ Tâches supplémentaires ajoutées (`fix-pagination`, `fix-slugify-accents`, `add-coupon-code`). Reste à ajouter une tâche plus ambiguë (bug multi-fichiers, ou issue sans test public proche) si les 4 tâches actuelles sont toutes résolues par l'agent.
4. Essayer `--ak reasoning_effort=…` et `--ak max_turns=…` pour comparer coût et taux de résolution.
5. Prototyper la tâche Java/Maven avec dépendances pré-téléchargées et réseau restreint.
