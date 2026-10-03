# Main actions of the Harbor sandbox. `make` or `make help` lists them.
# The scripts live in harbor-sandbox/scripts/; this Makefile only drives them.

SB := harbor-sandbox

# Optional variables (also readable by the scripts through the environment):
#   TASK=<name>             one task (oracle, nop, check, task)
#   TASKS="<a> <b>"         several tasks by name (claude)
#   CLAUDE_MODELS="<m1> .." models to evaluate (default: MODELS in run_claude.sh)
#   N_CONCURRENT=<n>        parallel trials (claude, default 3)
#   ARGS="<harbor options>" extra options passed to harbor run, e.g. ARGS='--n-attempts 1'
export TASK TASKS CLAUDE_MODELS N_CONCURRENT

.DEFAULT_GOAL := help
.PHONY: help prereqs tasks task oracle nop check claude metrics plot view ensure-tasks

help: ## Show this help
	@echo "Usage: make <target> [TASK=<name>] [TASKS=\"<a> <b>\"] [CLAUDE_MODELS=\"<m>\"] [N_CONCURRENT=<n>] [ARGS=\"...\"]"
	@echo
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

prereqs: ## Check Docker, Harbor and credentials
	@$(SB)/scripts/check_prereqs.sh

tasks: ## Generate every task from specs/ (fetches the codebases)
	@$(SB)/scripts/make_task.py --all

task: ## Generate one task: make task TASK=<name>
	@test -n "$(TASK)" || { echo "usage: make task TASK=<name>" >&2; exit 2; }
	@$(SB)/scripts/make_task.py $(TASK)

# Generate the tasks whose codebase has not been fetched yet (fresh clone).
ensure-tasks:
	@for spec in $(SB)/specs/*/spec.toml; do \
		name=$$(basename $$(dirname $$spec)); \
		if [ ! -d $(SB)/tasks/$$name/environment/app ]; then \
			echo "tasks/$$name is not generated yet"; \
			$(SB)/scripts/make_task.py $$name || exit 1; \
		fi; \
	done

oracle: ensure-tasks ## Reference solution: expect resolved = 1 (all tasks or TASK=<name>)
	@$(SB)/scripts/run_oracle.sh $(ARGS)

nop: ensure-tasks ## Agent that does nothing: expect resolved = 0, p2p = 1
	@$(SB)/scripts/run_nop.sh $(ARGS)

check: oracle nop ## Validate the tasks: oracle then nop (no quota used)

claude: ensure-tasks ## Run Claude Code (uses quota; needs CLAUDE_CODE_OAUTH_TOKEN)
	@$(SB)/scripts/run_claude.sh $(ARGS)

metrics: ## Extract jobs/ into docs/metrics.csv and print the summary
	@python3 $(SB)/scripts/extract_metrics.py

plot: ## Build docs/comparison.html from docs/metrics.csv
	@python3 $(SB)/scripts/plot_metrics.py

view: ## Browse trajectories (http://127.0.0.1:8080)
	@$(SB)/scripts/view.sh
