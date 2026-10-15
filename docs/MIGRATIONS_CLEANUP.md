# Migrations cleanup guide

Migrations live in `app/migrations/`. Use this guide when retiring or reorganizing them.

## When to clean up
- Seed files that are no longer required in any environment.
- Migrations superseded by later ones with the same data changes.
- Test or experimental migrations added during development.

## Process
1) Inventory: list migrations in chronological order; identify duplicates or obsolete seeds.
2) Verify usage: confirm no environment still depends on the migration (prod, staging, dev).
3) Replace/merge: if logic is still needed, create a new migration with a higher timestamp that consolidates changes, then remove the old one.
4) Communicate: note the removal in release notes or deployment steps so downstream environments can prune matching records.
5) Prune artifacts: delete unused files from `app/migrations/` and remove any linked documentation or references.

## Safety tips
- Do not modify existing migration timestamps; add new files instead.
- Keep migrations idempotent where possible so re-running is safe.
- If your platform supports dry runs, execute them before deleting files.

