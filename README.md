# Seedling

Seedling is a starter app for Insites. It gives you a public website and a signed-in dashboard with registration, sign-in, two-factor authentication (2FA), a profile page and password reset. The whole site lives in `app/`.

New to Insites? Work through the [Getting Started course](https://docs.insites.io/getting-started/welcome-to-insites) first. It explains instances, the CLI and how a site is built.

## Get started

1. **Get the code.** On GitHub, click **Use this template** on [insites-io/app-seedling](https://github.com/insites-io/app-seedling) to make your own copy, then clone your copy. You can also clone this repository directly:

   ```bash
   git clone https://github.com/insites-io/app-seedling.git
   cd app-seedling
   ```

2. **Install the Insites CLI.**

   ```bash
   npm install -g @insites/insites-cli
   ```

3. **Connect the CLI to your instance.** Use the instance UUID shown in the Insites Console. The CLI opens the Console in your browser so you can sign in.

   ```bash
   insites-cli env add staging --instance-uuid <your-instance-uuid>
   ```

4. **Send the code to your instance.** Send the whole app once with a partial deploy. Then run `sync` while you work, so each file goes up as you save it.

   ```bash
   insites-cli deploy -p staging
   insites-cli sync staging
   ```

Always pass `-p` to `deploy`. A full deploy (without `-p`) removes files from the instance that are not in your build, and every instance carries files that are not in this repository, such as the System Pages error pages.

## Installing over an older Seedling is not supported

Seedling 2.1.0 moved the site from its two folders under `modules/` (dashboard and website) into `app/`. Do not install 2.1.0 on an instance that already has an older Seedling (the `modules/` layout). A partial deploy never deletes files, so the instance would end up with both copies. The database tables and the user profile type also lost their module prefix (the profile type is now `client`), so data saved by the older version is not read by 2.1.0. Start from a new instance.

## What is in the repository

| Path | What it holds |
|---|---|
| `app/views/pages/` | Pages. `index.liquid` is the home page, `account/` holds sign-in, registration, 2FA and password reset, and `api/` holds the JSON endpoints |
| `app/views/layouts/` | `website_default`, `website_message`, `dashboard_default`, `dashboard_form` and `dashboard_account` |
| `app/views/partials/` | Header, footer, page content, account helpers and cache helpers |
| `app/forms/` | Form definitions: register, sign out, my details, change password, forgot password |
| `app/graphql/` | Queries and mutations for accounts, 2FA, rate limiting and page caching |
| `app/authorization_policies/` | Policies that protect signed-in pages and 2FA steps. Each one returns `true` or `false` |
| `app/schema/`, `app/user_profile_types/` | The `auth_attempt`, `documentation` and `reset_password` tables, and the `client` profile type |
| `app/emails/`, `app/api_calls/` | The password reset and 2FA alert emails, and the event log API call |
| `app/migrations/` | Seed data for the dashboard documentation cards |
| `app/assets/` | Scripts, styles and images. Readable sources sit beside their minified copies |
| `tests/` | End-to-end tests. See [tests/README.md](tests/README.md) |
| `docs/` | Notes on caching, environment flags, examples, form validation and migrations |

Seedling does not ship error pages. Every instance already has its 401, 403, 404 and 500 pages from System Pages. Seedling's `app/views/pages/index.liquid` replaces the placeholder home page that System Pages installs.

## Development guidelines

- Edit the readable sources (`*.js`, `*.liquid`, `*.graphql`) first, and keep the minified assets in step when they are the ones the pages load.
- Authorization policies must return `true` or `false` explicitly and handle missing user data.
- Reuse GraphQL documents. Update one query rather than copying it.
- Keep console logging behind a flag (`window.APP_DEBUG === true`) or remove it before you ship.
- Prefer small partials, and keep forms and scripts close to the page that uses them.

## Common patterns

- **Authorization:** policies run `account/check_2fa_setup` and return a boolean based on the 2FA and session state (`app/authorization_policies/*.liquid`).
- **GraphQL:** templates load data with `{% graphql check_2fa_setup = 'account/check_2fa_setup' %}` and read the result with Liquid assignments.
- **Form validation:** every form uses `FormValidation.validateAndSubmit(event, options)`. The browser checks give quick feedback. The form definitions on the server are the source of truth. See [docs/FORM_VALIDATION.md](docs/FORM_VALIDATION.md).
- **API helpers:** `app/assets/services/apiServices.js` wraps Axios for the dashboard, and `app/assets/services/formServices.js` does the same for website forms. Both log errors only when `window.APP_DEBUG` is `true`.

More examples are in [docs/EXAMPLES.md](docs/EXAMPLES.md).

## Caching

- Cache public website pages by default. The queries in `app/graphql/page_cache/` return the update times that drive cache invalidation.
- Do not cache pages that use `current_user` or private profile data.
- Details are in [docs/CACHING.md](docs/CACHING.md).

## Environment flags

- Browser flags such as `APP_DEBUG`, `API_BASE_URL` and `FORMS_API_BASE_URL` can be set in an inline script tag.
- Keep CSRF token selectors consistent with `CSRF_TOKEN_NAME` (default `csrf-token`).
- See [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md).

## Migrations

- Migrations live in `app/migrations/`.
- Follow [docs/MIGRATIONS_CLEANUP.md](docs/MIGRATIONS_CLEANUP.md) before you remove or merge any.
