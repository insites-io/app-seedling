## Project overview

Seedling contains the public assets that power the dashboard and marketing site. The codebase is organized as Liquid templates, GraphQL documents, and small JavaScript helpers that run in the browser (no server runtime inside this repo). The `modules/dashboard` folder owns authenticated experiences such as account, 2FA, profile management, and documentation pages; `modules/website` serves the public-facing marketing site.

## Installation instructions

1) Clone the repository: `git clone <repo-url> && cd app-seedling`  
2) There is no build step required to view or edit the Liquid/GraphQL files. Open the `modules/` tree in your editor and work directly against the source files.  
3) If you use optional tooling (formatters, linters, or bundlers), install a recent Node.js LTS (18+) and add your toolchain locally; compiled assets should be checked in alongside the readable sources.  
4) Deploy/sync the `modules/` directory to your target platform as needed (for example via your platform’s CLI or file sync).

## Architecture overview

- `modules/dashboard/public/authorization_policies`: Liquid auth policies that gate protected routes (2FA, session checks).
- `modules/dashboard/public/graphql`: GraphQL documents used by account and dashboard flows.
- `modules/dashboard/public/assets`: Unminified JS helpers plus minified counterparts for dashboard flows (sign in, 2FA, profile, API helpers).
- `modules/dashboard/public/views`: Layouts, pages, and partials for authenticated experiences.
- `modules/website/public`: Static marketing site layouts, styles, scripts, and GraphQL documents that support caching and notifications.
- Schema, migrations, and user profile type definitions live beside the modules to keep runtime configuration close to the templates.

## Development guidelines

- Edit the readable sources (`*.js`, `*.liquid`, `*.graphql`) first; keep minified assets in sync when they are the deployed artifacts.
- Auth policies must explicitly echo `true` or `false` and handle missing user data defensively.
- GraphQL documents should be shared and de-duplicated; prefer updating a single query and reusing it instead of copying.
- Keep console logging behind a feature flag (e.g., `window.APP_DEBUG === true`) or remove it entirely before shipping.
- Favor small, composable partials and keep forms/scripts close to their associated view for discoverability.

## Common patterns and examples

- **Authorization**: Policies query `modules/dashboard/account/check_2fa_setup` and echo booleans based on 2FA and session state (`authorization_policies/*.liquid`).
- **GraphQL usage**: Templates request data with `{% graphql variable = 'modules/dashboard/account/check_2fa_setup' %}` then consume it with Liquid assignments.
- **Form validation**: All forms use the unified `FormValidation.validateAndSubmit(event, options)` handler. Client-side validation provides immediate feedback; server-side validation (defined in form YAML) is the source of truth. See `docs/FORM_VALIDATION.md` for the complete strategy.
- **API helpers**: `modules/dashboard/public/assets/services/apiServices.js` wraps Axios; error logging is gated by `window.APP_DEBUG` to avoid noisy consoles in production. A similar helper exists for marketing forms at `modules/website/public/assets/services/formServices.js`.

More examples live in `docs/EXAMPLES.md`.

## Caching strategy

- Cache static marketing pages by default; see `modules/website/public/graphql/page_cache` for update timestamps to drive cache invalidation.
- Avoid caching routes that reference `current_user` or private profile data.
- Use short TTLs (5–15 minutes) on public GraphQL page-cache endpoints; bypass caching for dashboard API responses.
- Details in `docs/CACHING.md`.

## Environment configuration examples

- Front-end flags such as `APP_DEBUG`, `API_BASE_URL`, and `FORMS_API_BASE_URL` can be injected via inline script tags or your platform’s environment settings.
- Keep CSRF token selectors consistent with `CSRF_TOKEN_NAME` (default `csrf-token`).
- See `docs/ENVIRONMENT.md` for example snippets and guidance.

## Migrations cleanup guide

- Migrations live in `modules/dashboard/public/migrations/`; clean obsolete seeds and duplicates carefully.
- Follow the safety checklist in `docs/MIGRATIONS_CLEANUP.md` before removing or consolidating files.

