# Seedling tests

This folder holds the end-to-end tests for Seedling, written with TestCafe, and the QA suite in [`qa/`](qa/README.md). They run against a real instance, so you tell them which one with the `INSITES_URL` environment variable.

The test tooling lives here rather than at the repository root on purpose: the Insites GitHub App treats a `package.json` at the root as a project to build, and would then deploy only its `dist/` folder.

## Running the tests

Run these commands from this `tests/` folder:

```bash
npm install
INSITES_URL=https://your-instance.example.com npm test       # headless Chrome
INSITES_URL=https://your-instance.example.com npm run test:ui  # visible Chrome
```

The tests stop with an error when `INSITES_URL` is missing. There is no default instance.

On macOS, TestCafe needs Screen Recording permission to drive a local browser. Grant it in System Settings, or run the tests in remote mode and open the printed connect URL in any browser:

```bash
INSITES_URL=https://your-instance.example.com npx testcafe remote 'e2e/**/*.e2e.js'
```

## Configuration

- `INSITES_URL`: the instance to test, for example `https://your-instance.example.com`.
- `.testcaferc.json` in this folder holds the TestCafe settings. Screenshots of failures go to `screenshots/` and the JSON report to `reports/report.json`, both ignored by git.

## Test files

- `qa/`: the QA suite for sign-in, 2FA, password reset, passwordless sign-in and the v2.1.0 clean-up work. It deploys to a test instance, runs 132 cases, verifies the build, and removes everything it added. See [qa/README.md](qa/README.md) before running it: it changes the instance.

- `e2e/email-api.e2e.js`: tests the email check endpoint used by registration (`/api/check-user-email-signup`): a new email, a missing email (400), a malformed email (422), and that no user id is ever returned. Set `EXISTING_EMAIL` to an address registered on the instance to also check the "already used" answer.

## Before you run them

1. Deploy Seedling to the instance and make sure it loads at `INSITES_URL`.
2. Set up any test data a test needs (for example `EXISTING_EMAIL`).
3. Use Node.js 18 or later.

## Writing new tests

1. Create a new `.e2e.js` file in `e2e/`.
2. Import TestCafe: `import { RequestLogger, Selector } from 'testcafe';`
3. Build every URL from `process.env.INSITES_URL`. Never write an instance address into a test.
4. Follow the structure of the existing test.

