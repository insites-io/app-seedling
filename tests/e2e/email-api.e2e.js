import { RequestLogger, Selector } from 'testcafe';

// The instance under test. Set INSITES_URL when you run the tests, for example
// INSITES_URL=https://your-instance.example.com npm test
const BASE_URL = (process.env.INSITES_URL || '').replace(/\/+$/, '');

if (!/^https?:\/\//.test(BASE_URL)) {
    throw new Error('Set INSITES_URL to the instance you want to test, for example INSITES_URL=https://your-instance.example.com npm test');
}

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

test('Should never return a user id for an email', async t => {
    // Set EXISTING_EMAIL to an address registered on the instance to also check the "taken" answer.
    const existingEmail = process.env.EXISTING_EMAIL || 'existing@example.com';
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
    
    // Any existing user is reported as taken, and the user id is never returned
    if (process.env.EXISTING_EMAIL) {
        await t
            .expect(body.email_status).eql('invalid')
            .expect(body.message).eql('Email has already been used.');
    }
    await t
        .expect(['valid', 'invalid']).contains(body.email_status)
        .expect('email_id' in body).notOk('email_id must never be returned')
        .expect('id' in body).notOk('id must never be returned');
});

test('Should answer 400 when the email parameter is missing', async t => {
    const url = `${BASE_URL}${EMAIL_API_PATH}`;

    logRequest('Missing email param request', url);
    const response = await t.request(url);

    const body = getJsonBody(response);

    await t
        .expect(response.status).eql(400)
        .expect(response.headers['content-type']).contains('application/json');

    await t
        .expect(body.success).eql(false)
        .expect(body.status_code).eql(400)
        .expect(body.errors.email).ok('errors.email should name the problem');
});

test('Should answer 422 for an invalid email format', async t => {
    const invalidEmail = 'not-an-email';
    const url = `${BASE_URL}${EMAIL_API_PATH}?email=${encodeURIComponent(invalidEmail)}`;

    logRequest('Invalid email format request', url);
    const response = await t.request(url);

    const body = getJsonBody(response);

    await t
        .expect(response.status).eql(422)
        .expect(response.headers['content-type']).contains('application/json');

    await t
        .expect(body.success).eql(false)
        .expect(body.status_code).eql(422)
        .expect(body.errors.email).ok('errors.email should name the problem');
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

