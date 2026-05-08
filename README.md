# app-seedling

A starter Insites application that provides a reference implementation for an authenticated dashboard and a public marketing site. The codebase is organised as Liquid templates, GraphQL documents, and small vanilla JavaScript helpers (built around axios) that run in the browser. There is no server runtime in this repo. Fork it as a starting point for your own Insites application.

## Stack

- Liquid templates for layouts, pages, and partials
- GraphQL documents for data access
- Vanilla JavaScript with axios for browser-side helpers
- TestCafe for end-to-end tests
- Runs on the Insites platform

The repo is split into two modules:

- `modules/dashboard` — authenticated experiences (account, 2FA, profile management, documentation pages)
- `modules/website` — public-facing marketing site

## Getting started

This application is designed to run on a deployed Insites instance. You will need:

1. An Insites instance (provisioned via CloudShell). See [docs.insites.io](https://docs.insites.io) for setup.
2. Node.js 18 or newer (only required if you want to run the test suite).

To work with the source:

```bash
git clone https://github.com/insites-io/app-seedling.git
cd app-seedling
```

There is no build step. Edit the Liquid, GraphQL, and JavaScript files directly under `modules/`, then deploy them to your Insites instance using the Insites CLI or CloudShell.

## Architecture

- `modules/dashboard/public/authorization_policies` — Liquid auth policies that gate protected routes
- `modules/dashboard/public/graphql` — GraphQL documents for account and dashboard flows
- `modules/dashboard/public/assets` — JavaScript helpers (sign in, 2FA, profile, API services)
- `modules/dashboard/public/views` — Layouts, pages, and partials for authenticated experiences
- `modules/website/public` — Static marketing site layouts, styles, scripts, and GraphQL documents
- Schema, migrations, and user profile type definitions live beside the modules

## Patterns

- **Authorization** — Policies query `modules/dashboard/account/check_2fa_setup` and echo booleans based on 2FA and session state.
- **GraphQL usage** — Templates load data with `{% graphql variable = 'modules/dashboard/account/check_2fa_setup' %}` and consume it with Liquid assignments.
- **Form validation** — Forms use the unified `FormValidation.validateAndSubmit(event, options)` handler. Client-side validation provides immediate feedback; server-side validation (defined in form YAML) is the source of truth.
- **API helpers** — `modules/dashboard/public/assets/services/apiServices.js` wraps axios; error logging is gated by `window.APP_DEBUG`.

## Testing

End-to-end tests use TestCafe and run against a live Insites instance. The instance URL is read from the `MPKIT_URL` environment variable.

```bash
npm install
export MPKIT_URL=https://your-instance.insites.io
npm test                 # all modules, headless Chrome
npm run test:dashboard   # dashboard tests only
npm run test:website     # website tests only
npm run test:ui          # full Chrome UI (not headless)
```

If `MPKIT_URL` is not set, the scripts fall back to a placeholder which will not resolve. Set the variable to match the instance you want to test against.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow, including the Developer Certificate of Origin (DCO) sign-off requirement. Please also read the [Code of Conduct](CODE_OF_CONDUCT.md).

## Licence

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
