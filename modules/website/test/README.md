# Website Module E2E Tests

This directory contains end-to-end tests for the website module using TestCafe.

## Running Tests

From the project root:

```bash
# Run all website tests
npm run test:website

# Run all tests (dashboard + website)
npm run test

# Run tests with UI (non-headless)
npm run test:ui
```

## Configuration

- Base URL is set via `MPKIT_URL` environment variable (defaults to UAT staging URL in npm scripts)
- Default base URL in test files: `http://localhost:3000`
- TestCafe configuration: `.testcaferc.json` in project root
- To override the base URL: `MPKIT_URL=https://your-url.com npm run test:website`

## Environment Setup

Before running tests, ensure:
1. Your application is running and accessible at the base URL
2. Test data is set up (if required for specific test cases)
3. Node.js 18+ is installed

## Writing New Tests

1. Create a new `.e2e.js` file in this directory
2. Import TestCafe utilities: `import { RequestLogger, Selector } from 'testcafe';`
3. Use the `BASE_URL` constant or environment variable for API endpoints
4. Follow the existing test structure and naming conventions

