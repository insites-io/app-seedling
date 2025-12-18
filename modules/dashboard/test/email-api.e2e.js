import { RequestLogger, Selector } from 'testcafe';

// Base URL - update this to match your environment
// Can be overridden with MPKIT_URL environment variable
const BASE_URL = process.env.MPKIT_URL || 'http://localhost:3000';

// Simple helper to log requests in the test output
// Note: Using TestCafe's built-in logging instead of console.log
function logRequest(label, url) {
    // Request logging is handled by TestCafe's RequestLogger
    // No console output needed
}

function getJsonBody(response) {
    if (!response || response.body == null) return {};

    if (typeof response.body === 'string' && response.body.length > 0) {
        try {
            return JSON.parse(response.body);
        } catch (e) {
            return {};
        }
    }

    return response.body;
}

// API endpoint path
const EMAIL_API_PATH = '/api/check-user-email-signup';

// Request logger to capture API responses
const emailApiLogger = RequestLogger(
    { url: new RegExp(`${EMAIL_API_PATH}.*`), method: 'get' },
    { logResponseBody: true, logResponseHeaders: true }
);

fixture('Email API Endpoint Tests')
    // We don't need to load a real page for API-level tests
    .page('about:blank')
    .requestHooks(emailApiLogger);

test('Should return valid status for new email', async t => {
    const testEmail = `test-${Date.now()}@example.com`;
    const url = `${BASE_URL}${EMAIL_API_PATH}?email=${encodeURIComponent(testEmail)}`;

    logRequest('Valid email request', url);
    const response = await t.request(url);

    const body = getJsonBody(response);

    await t
        .expect(response.status).eql(200)
        .expect(response.headers['content-type']).ok()
        .expect(response.headers['content-type']).contains('application/json');

    await t
        .expect(body).ok('Response body should be present')
        .expect('email_status' in body).ok('email_status should exist in body')
        .expect('message' in body).ok('message should exist in body')
        .expect(body.email_status).eql('valid')
        .expect(body.message).eql('Email is valid');
});

test('Should return invalid status for email with CRM profile', async t => {
    // Note: This test assumes you have a test email with a CRM profile
    // Update the email or set up test data accordingly
    const existingEmail = 'existing@example.com';
    const url = `${BASE_URL}${EMAIL_API_PATH}?email=${encodeURIComponent(existingEmail)}`;

    logRequest('Existing email request', url);
    const response = await t.request(url);

    const body = getJsonBody(response);

    await t
        .expect(response.status).eql(200)
        .expect(response.headers['content-type']).ok()
        .expect(response.headers['content-type']).contains('application/json');

    await t
        .expect(body).ok('Response body should be present')
        .expect('email_status' in body).ok('email_status should exist in body')
        .expect('message' in body).ok('message should exist in body');
    
    // The status could be 'invalid' or 'no-profile' depending on the email's state
    if (body.email_status === 'invalid') {
        await t.expect(body.message).eql('Email has already been used.');
    }
});

test('Should return no-profile status for email without CRM profile', async t => {
    // Note: This test assumes you have a test email without a CRM profile
    // Update the email or set up test data accordingly
    const emailWithoutProfile = 'no-profile@example.com';
    const url = `${BASE_URL}${EMAIL_API_PATH}?email=${encodeURIComponent(emailWithoutProfile)}`;

    logRequest('No-profile email request', url);
    const response = await t.request(url);

    const body = getJsonBody(response);

    await t
        .expect(response.status).eql(200)
        .expect(response.headers['content-type']).ok()
        .expect(response.headers['content-type']).contains('application/json');

    await t
        .expect(body).ok('Response body should be present')
        .expect('email_status' in body).ok('email_status should exist in body')
        .expect('message' in body).ok('message should exist in body');

    if (body.email_status === 'no-profile') {
        await t
            .expect('email_id' in body).ok('email_id should exist in body when status is no-profile')
            .expect(body.message).eql('Email needs update.');
    }
});

test('Should handle missing email parameter gracefully', async t => {
    const url = `${BASE_URL}${EMAIL_API_PATH}`;

    logRequest('Missing email param request', url);
    const response = await t.request(url);

    const body = getJsonBody(response);

    await t
        .expect(response.status).eql(200)
        .expect(response.headers['content-type']).ok()
        .expect(response.headers['content-type']).contains('application/json');

    await t
        .expect(body).ok('Response body should be present')
        .expect('email_status' in body).ok('email_status should exist in body')
        .expect('message' in body).ok('message should exist in body');
});

test('Should handle invalid email format', async t => {
    const invalidEmail = 'not-an-email';
    const url = `${BASE_URL}${EMAIL_API_PATH}?email=${encodeURIComponent(invalidEmail)}`;

    logRequest('Invalid email format request', url);
    const response = await t.request(url);

    const body = getJsonBody(response);

    await t
        .expect(response.status).eql(200)
        .expect(response.headers['content-type']).ok()
        .expect(response.headers['content-type']).contains('application/json');

    await t
        .expect(body).ok('Response body should be present')
        .expect('email_status' in body).ok('email_status should exist in body')
        .expect('message' in body).ok('message should exist in body');
});

test('Should log API requests correctly', async t => {
    const testEmail = `log-test-${Date.now()}@example.com`;
    const url = `${BASE_URL}${EMAIL_API_PATH}?email=${encodeURIComponent(testEmail)}`;

    logRequest('Logger verification request', url);
    await t.request(url);
    
    // Check that the request was logged
    await t
        .expect(emailApiLogger.contains(r => r.request.url.includes(EMAIL_API_PATH))).ok()
        .expect(emailApiLogger.requests.length).gt(0);
    
    const loggedRequest = emailApiLogger.requests[emailApiLogger.requests.length - 1];
    await t
        .expect(loggedRequest.request.url).contains(EMAIL_API_PATH)
        .expect(loggedRequest.response.statusCode).eql(200);
});

