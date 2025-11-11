# ======= CONFIG ========
PYTHON_VERSION := 3.11.9
BASE_BRANCH ?= cycle2
BRANCH ?=

# ======= INSTALLATION ========
install:
	@echo "🔧 Installing backend requirements..."
	pip install -r services/requirements.txt
	@echo "📦 Installing frontend dependencies..."
	yarn --cwd src install

# ======= DEVELOPMENT ========
dev:
	@echo "🚀 Starting backend + frontend dev environment"
	yarn dev

# ======= BRANCHING ========
start:
ifndef BRANCH
	$(error ❌ BRANCH is not set. Use: make start BRANCH=cycle2-my-feature)
endif
	@echo "🔁 Syncing base branch: $(BASE_BRANCH)"
	git checkout $(BASE_BRANCH)
	git pull origin $(BASE_BRANCH)
	@echo "🌱 Creating new feature branch: $(BRANCH)"
	git checkout -b $(BRANCH)
	git push -u origin $(BRANCH)

rebase-feature:
ifndef BRANCH
	$(error ❌ BRANCH is not set. Use: make rebase-feature BRANCH=cycle2-my-feature)
endif
	@echo "🔁 Rebasing $(BRANCH) on $(BASE_BRANCH)"
	git fetch origin
	git checkout $(BRANCH)
	git rebase origin/$(BASE_BRANCH)

# ======= HOUSEKEEPING ========
list-merged:
	@echo "📜 Listing local branches merged into current"
	git branch --merged | grep -v "\*" | grep -v "$(BASE_BRANCH)"

clean-merged:
	@echo "🧹 Cleaning up merged branches (excluding main/cycle2)"
	git branch --merged | grep -v "\*" | grep -v "main" | grep -v "$(BASE_BRANCH)" | xargs git branch -d

# ======= PYENV VERSION ========
pyenv-version:
	@echo "$(PYTHON_VERSION)" > .python-version
	@echo "📌 Pinned Python version to $(PYTHON_VERSION)"

.PHONY: install dev start rebase-feature list-merged clean-merged pyenv-version
