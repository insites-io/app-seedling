# Seedling

Seedling is a starter app for Insites. It gives you a public website and a signed-in dashboard with registration, sign-in (by password, emailed link or emailed code), two-factor authentication (2FA), a profile page and password reset. The whole site lives in `app/`.

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
| `app/views/pages/` | Pages. `index.liquid` is the home page, `account/` holds sign-in (password, emailed link and emailed code), registration, 2FA and password reset, and `api/` holds the JSON endpoints |
| `app/views/layouts/` | `website_default`, `website_message`, `dashboard_default`, `dashboard_form` and `dashboard_account` |
| `app/views/partials/` | Header, footer, page content, account helpers and cache helpers |
| `app/forms/` | One form definition, `update_password_token`, which sends the password reset email when a reset token is saved. Every form on a page is a plain `<form>`; see [docs/FORM_VALIDATION.md](docs/FORM_VALIDATION.md) |
| `app/graphql/` | Queries and mutations for accounts, 2FA, rate limiting and page caching |
| `app/authorization_policies/` | Policies that protect signed-in pages and 2FA steps. Each one returns `true` or `false` |
| `app/schema/`, `app/user_profile_types/` | The `auth_attempt`, `documentation`, `sign_in_code` and `sign_in_link` tables, and the `client` profile type |
| `app/emails/` | The password reset, 2FA alert, sign-in link and sign-in code emails |
| `app/migrations/` | Seed data for the dashboard documentation cards, and the secret that sign-in codes are hashed with |
| `app/assets/` | Scripts, styles and images. There is one readable copy of each script and stylesheet, loaded in every environment |
| `tests/` | End-to-end tests. See [tests/README.md](tests/README.md) |
| `docs/` | Notes on caching, examples, forms and validation, and migrations |

Seedling does not ship error pages. Every instance already has its 401, 403, 404 and 500 pages from System Pages. Seedling's `app/views/pages/index.liquid` replaces the placeholder home page that System Pages installs.

## Sign-in options

The sign-in page offers three ways in: a password, an emailed link, or an emailed 6-digit code.

| Option | Pages | How it works |
|---|---|---|
| Password | `/sign-in` | Email and password, then 2FA if the account has it turned on |
| Emailed link | `/sign-in/email-link`, then `/sign-in/link` | The email holds a link that works once, for 15 minutes. Opening it only shows a **Continue** button; pressing it signs you in |
| Emailed code | `/sign-in/email-code`, then `/sign-in/code` | The email holds a 6-digit code that works once, for 15 minutes. 5 wrong codes end it |

Two things to set up on each instance:

1. **`SITE_ORIGIN`.** The link in the email is built from this constant, never from the request, so nobody can make it point at another site. Set it to the address of your site, with no trailing slash. Until it is set, the emailed link option says it is not available.

   ```bash
   insites-cli constants set staging --name SITE_ORIGIN --value https://www.example.com
   ```

2. **`SIGN_IN_HMAC_KEY`.** Codes are stored as a keyed hash, never as the code. The migration `app/migrations/20261015000000_sign_in_code_hmac_key.liquid` creates a random key the first time you deploy, and leaves it alone after that. Until it is set, the emailed code option says it is not available.

How the emailed options stay safe:

- **The same answer for every address.** Asking for a link or a code for an address with no account gives the same message as for a real one, and counts toward the limits the same way. Nothing is sent.
- **Only registered accounts.** A user may sign in this way only when they have a `client` profile, which registration creates.
- **Limits.** 5 requests per address and 20 per IP address in 15 minutes, through the same `auth_attempt` table as password sign-in. Each code allows 5 guesses, and they are counted with one row per guess, so sending many guesses at once still gets only 5 checked. Across all codes for one address, 10 wrong codes in an hour stop further checks.
- **Works once.** Using a link or a code claims a single "use" row with a unique external id, so two requests at the same moment cannot both sign in.
- **Email scanners cannot use a link.** Many mail systems open every link to check it. Opening the link changes nothing: it moves the link into your session, takes it out of the address bar, and shows **Continue**. Only pressing **Continue** uses it.
- **2FA still applies.** If the account has 2FA turned on, you go to `/verify-2fa` after the link or code, exactly as after a password.
- **`return_to`** is passed through `account/safe_return_to`, so it can only be a path on this site, with no quote, angle bracket or backtick.

## Email sender

Every email comes from the instance's verified sender, which the CRM module resolves
(`modules/insites_crm/functions/email_sender/customer_sender`): the customer's own domain
once it is verified in Insites Console, otherwise `no-reply@insites.site`. The display name
is `company_name` from CMS Globals, and replies go to `company_email_1` from CMS Globals.
Without `company_email_1` the mail still goes, with no Reply-To.

This differs from the original 2.1.0 brief, which asked for mail to come from the Globals
address. A customer domain that is not verified fails the receiving server's delivery checks
(SPF, DKIM and DMARC), so that mail would be dropped. Mail is never sent from
`notifications@insites.io` or any other address the instance cannot authenticate. If the
instance has no sendable sender at all, the pages that send email say it is not available
and the reason is written to the instance log.

## Development guidelines

- Edit the readable sources (`*.js`, `*.css`, `*.liquid`, `*.graphql`). There are no minified copies to keep in step.
- Every page declares its `method:`. A form posts to its own page with `method: post`.
- Use `render` for a partial that outputs HTML and `function` for one that returns a value.
- A value that goes into an HTML attribute is escaped and written with `print` (see [docs/EXAMPLES.md](docs/EXAMPLES.md)). An output tag turns an escaped double quote back into a quote.
- Authorization policies must return `true` or `false` explicitly and handle missing user data.
- Reuse GraphQL documents. Update one query rather than copying it.
- Keep console logging behind a flag (`window.APP_DEBUG === true`) or remove it before you ship.
- Prefer small partials, and keep forms and scripts close to the page that uses them.

## Common patterns

- **Authorization:** policies run `account/check_2fa_setup` and return a boolean based on the 2FA and session state (`app/authorization_policies/*.liquid`).
- **Signed-out visitors:** a signed-in page sends a signed-out visitor to `/sign-in`, and the platform adds `return_to` so they come back after signing in. When several policies on a page fail, the platform uses the redirect of the policy that was created first, not the first one listed, so each policy's `redirect_to` checks whether someone is signed in rather than relying on the order.
- **GraphQL:** templates load data with `{% graphql check_2fa_setup = 'account/check_2fa_setup' %}` and read the result with Liquid assignments.
- **Form validation:** every form uses `FormValidation.validateAndSubmit(event, options)` in the browser for quick feedback. The page each form posts to checks everything again and decides. See [docs/FORM_VALIDATION.md](docs/FORM_VALIDATION.md).
- **API helpers:** `app/assets/services/apiServices.js` wraps Axios (pinned, with an integrity hash, in `app/views/partials/layout/axios.liquid`). It logs errors only when `window.APP_DEBUG` is `true`.
- **API errors:** the JSON endpoints answer with the real HTTP status (400, 403, 422, 429, 500) and the body from `api/error_response`.

More examples are in [docs/EXAMPLES.md](docs/EXAMPLES.md).

## Caching

- A page caches itself with `dynamic_cache`, keyed by `cache/generate_cache_key` with the tables it shows. The account-created page is the example.
- Never cache a page that shows one user's data. The dashboard is not cached.
- Details are in [docs/CACHING.md](docs/CACHING.md).

## Event log

Registration and profile changes add an entry to the instance's event stream, from a
background job that calls the CRM module's event stream controller
(`crm/controller/event-streams/create`) in the same request. No API key is sent anywhere.

## Migrations

- Migrations live in `app/migrations/`.
- Follow [docs/MIGRATIONS_CLEANUP.md](docs/MIGRATIONS_CLEANUP.md) before you remove or merge any.
