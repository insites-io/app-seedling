# Seedling Liquid unit tests

Seedling has one Liquid unit test. It checks the GraphQL query behind the email check that registration uses. It runs on an instance, not on your computer.

## Test structure

- `app/views/partials/test/commands/`: test files. Each name ends in `_test.liquid`.
- `app/views/partials/test/assertions/`: assertion helpers.

## Running the tests

Seedling does not ship a page that runs these tests. The test builds its own `contract` object and prints it as JSON, so the way to run it today is to render the partial on a staging instance and read the result (for example with `insites-cli exec liquid`).

It is not yet wired to the `insites-cli test run` runner. That runner passes in a `contract` and reads the same object back, and this test replaces it with its own, so the runner would not see its failures.

Before you run it, deploy Seedling to the instance and set up the test data listed below.

## Available Tests

### `check_user_email_signup_test`
Tests the email validation GraphQL query used by the registration API endpoint.

**Test Cases:**
1. Valid email (new email that doesn't exist)
2. Invalid email (email with CRM profile)
3. No-profile email (email exists but no CRM profile)
4. Missing email parameter
5. Invalid email format
6. GraphQL query structure validation

**Test Data Requirements:**
- Some tests require test users to exist:
  - A user with email `existing-crm@example.com` that has a CRM contact profile
  - A user with email `existing-no-profile@example.com` that does NOT have a CRM contact profile

You may need to adjust these email addresses in the test file to match your test data, or create the required test users.

## Test Results

Tests return a JSON contract object with:
- `valid`: `true` if all tests passed, `false` if any test failed
- `errors`: Object containing error messages grouped by test field name

Example successful result:
```json
{
  "valid": true,
  "errors": {}
}
```

Example failed result:
```json
{
  "valid": false,
  "errors": {
    "valid_email_test": ["Expected email to not exist in database"]
  }
}
```

## Writing New Tests

1. Create a new test file in `app/views/partials/test/commands/`
2. Name it with `_test.liquid` suffix (e.g., `my_feature_test.liquid`)
3. Use the test contract pattern:
   ```liquid
   {% liquid
     assign contract = '{"errors": {}, "valid": true}' | parse_json
   %}
   ```
4. Use assertions:
   ```liquid
   {% liquid
     unless condition
       include 'test/assertions/register_error', contract: contract, field_name: 'test_name', message: 'Error message'
     endunless
   %}
   ```
5. Return the contract at the end:
   ```liquid
   {{ contract }}
   ```

## Differences from E2E Tests

- **Unit tests** (`app/views/partials/test/`): Test individual GraphQL queries, commands, and logic directly
- **E2E tests** (`tests/e2e/*.e2e.js`): Test full API endpoints and user flows using TestCafe

Both test types complement each other:
- Unit tests are faster and test logic in isolation
- E2E tests verify the full integration and user experience

