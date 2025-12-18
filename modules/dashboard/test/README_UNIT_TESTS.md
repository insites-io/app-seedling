# Dashboard Module Unit Tests

This directory contains unit tests for the dashboard module using PlatformOS's built-in test framework.

## Test Structure

Unit tests are located in:
- `modules/dashboard/public/views/partials/test/commands/` - Test files (must end with `_test.liquid`)
- `modules/dashboard/public/views/partials/test/assertions/` - Assertion helpers

## Running Tests

### Prerequisites
1. Deploy your code to a PlatformOS instance
2. Ensure test data is set up (some tests require specific users/profiles)

### Running All Tests

After deploying, navigate to:
```
https://your-instance.example.com/tests
```

This will run all available unit tests and return JSON results.

### Running a Specific Test

To run a specific test, use:
```
https://your-instance.example.com/tests/run?name=commands/account/check_user_email_signup_test
```

The test name format is: `commands/{path}/{test_name}` (without the `.liquid` extension)

For example:
- Test file: `test/commands/account/check_user_email_signup_test.liquid`
- Test name: `commands/account/check_user_email_signup_test`

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

1. Create a new test file in `modules/dashboard/public/views/partials/test/commands/`
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
       include 'modules/dashboard/test/assertions/register_error', contract: contract, field_name: 'test_name', message: 'Error message'
     endunless
   %}
   ```
5. Return the contract at the end:
   ```liquid
   {{ contract }}
   ```
6. Add the test to the test list in `modules/dashboard/public/views/pages/tests.liquid`

## Differences from E2E Tests

- **Unit Tests** (this directory): Test individual GraphQL queries, commands, and logic directly
- **E2E Tests** (`modules/dashboard/test/*.e2e.js`): Test full API endpoints and user flows using TestCafe

Both test types complement each other:
- Unit tests are faster and test logic in isolation
- E2E tests verify the full integration and user experience

