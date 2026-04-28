#!/bin/bash
# Script to squash commits from 5e6641ee to HEAD

echo "Starting interactive rebase to squash commits..."
echo ""
echo "This will merge 21 commits into 8 commits:"
echo "  1. Real-time log output infrastructure (4 -> 1)"
echo "  2. LLM conversation logging system (6 -> 1)"
echo "  3. Pytest output format optimization (3 -> 1)"
echo "  4. --from-test parameter feature (2 -> 1)"
echo "  5. Flaky retry mechanism (3 -> 1)"
echo "  6-8. Keep 3 independent commits"
echo ""
echo "Press Ctrl+C to cancel, or wait 3 seconds to continue..."
sleep 3

git rebase -i 5e6641ee
