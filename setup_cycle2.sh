#!/bin/bash

# Exit on any error, unset var, or failed pipeline
set -euo pipefail

# === CONFIGURATION ===
GOOD_BRANCH="cycle1-pitboss"
NEW_CYCLE1="cycle1"
NEW_CYCLE2="cycle2"
FEATURE_BRANCHES=(
  "cycle2-fancy-sql"
  "cycle2-parse-eligibility"
  "cycle2-parse-ie"
  "cycle2-cards"
)

# Auto-stash uncommitted changes? true/false
AUTO_STASH=true

# === INTERNAL STATE ===
ORIGINAL_BRANCH="$(git branch --show-current)"
STASHED=false

echo "🔍 Current branch: $ORIGINAL_BRANCH"
echo "🧹 Checking for uncommitted changes..."

# === CLEAN WORKING DIR CHECK ===
if ! git diff --quiet || ! git diff --cached --quiet; then
  if [ "$AUTO_STASH" = true ]; then
    echo "💾 Stashing uncommitted changes..."
    git stash push -u -m "Auto-stash by setup_cycle2.sh"
    STASHED=true
  else
    echo "❌ Uncommitted changes detected. Please commit or stash manually."
    exit 1
  fi
fi

# === STEP 1: Tag & delete old cycle1 ===
if git show-ref --quiet "refs/heads/${NEW_CYCLE1}"; then
  if git rev-parse --verify --quiet "refs/tags/archive/broken-${NEW_CYCLE1}" >/dev/null; then
    echo "⚠️  Tag archive/broken-${NEW_CYCLE1} already exists. Skipping tag."
  else
    echo "🏷 Tagging existing ${NEW_CYCLE1} as archive/broken-${NEW_CYCLE1}"
    git tag "archive/broken-${NEW_CYCLE1}" "${NEW_CYCLE1}"
    git push origin "archive/broken-${NEW_CYCLE1}"
  fi

  echo "🔥 Deleting broken ${NEW_CYCLE1}"
  git branch -D "${NEW_CYCLE1}"
  git push origin --delete "${NEW_CYCLE1}" || true
fi

# === STEP 2: Create fresh cycle1 from GOOD_BRANCH ===
if git show-ref --quiet "refs/heads/${NEW_CYCLE1}"; then
  echo "⚠️  ${NEW_CYCLE1} already exists. Skipping creation."
else
  echo "🌱 Creating ${NEW_CYCLE1} from ${GOOD_BRANCH}"
  git checkout "${GOOD_BRANCH}"
  git checkout -b "${NEW_CYCLE1}"
  git push -u origin "${NEW_CYCLE1}"
fi

# === STEP 3: Create cycle2 from cycle1 ===
if git show-ref --quiet "refs/heads/${NEW_CYCLE2}"; then
  echo "⚠️  ${NEW_CYCLE2} already exists. Skipping creation."
else
  echo "🌱 Creating ${NEW_CYCLE2} from ${NEW_CYCLE1}"
  git checkout "${NEW_CYCLE1}"
  git checkout -b "${NEW_CYCLE2}"
  git push -u origin "${NEW_CYCLE2}"
fi

# === STEP 4: Create feature branches ===
for branch in "${FEATURE_BRANCHES[@]}"; do
  echo "🔁 Processing feature branch: ${branch}"

  if git show-ref --quiet "refs/heads/${branch}" || git ls-remote --exit-code --heads origin "${branch}" > /dev/null 2>&1; then
    echo "⚠️  Branch '${branch}' already exists. Skipping."
    continue
  fi

  echo "🌿 Creating branch '${branch}' from ${NEW_CYCLE2}"
  git checkout "${NEW_CYCLE2}"
  git checkout -b "${branch}"
  git push -u origin "${branch}"
done

# === FINALIZE ===
echo "✅ All branches created. Returning to original branch: ${ORIGINAL_BRANCH}"
git checkout "${ORIGINAL_BRANCH}"

if [ "$STASHED" = true ]; then
  echo "♻️  Restoring stashed changes..."
  git stash pop
fi

echo "🏁 Done - v2"