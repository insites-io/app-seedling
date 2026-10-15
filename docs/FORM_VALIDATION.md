# Forms and validation

Every form in Seedling is a plain HTML `<form>` that posts to a page of its own. There are
no form definitions with the `{% form %}` tag (see the Insites Logic Engine rule
`forms-no-form-tag`).

## Two layers

1. **The browser** checks the fields first, for quick feedback. It can be skipped, so it
   never decides anything.
2. **The page the form posts to** checks everything again on the server and decides.

## A form

```liquid
<form id="forgot-password-form" action="/forgot-password" method="post" novalidate
      onsubmit="return FormValidation.validateAndSubmit(event);">
  <input type="hidden" name="authenticity_token" value="{{ context.authenticity_token }}">
  <ins-input validate id="email" label="Email" field="email" name="email"
             error-message="Please use a valid email address"></ins-input>
  <ins-button label="SUBMIT" solid type="submit"></ins-button>
</form>
```

- Every form that posts carries the authenticity token.
- `FormValidation.validateAndSubmit(event, options)` (in `app/assets/scripts/login-scripts.js`)
  checks every `[validate]` field, then submits. While it runs, a second click does nothing.
  `options.containerId` limits the check to one part of the form, and `options.checkEmail`
  makes the register form wait for the "email already used" check.
- The profile forms use `UserProfileScript.methods.validateForm(event)` in
  `app/assets/scripts/user-profile.js`, which also asks before a password change.

## The page a form posts to

A page with `method: post` and the same slug as the form page, for example
`app/views/pages/account/forgot_password_submit.liquid`:

1. **Check the session.** A post without a valid authenticity token is not refused by the
   platform: it arrives with an empty session and no signed-in user. Signed-out forms set a
   session flag when the form page renders, and the post refuses to continue without it.
   Signed-in forms are protected by their page's authorization policies instead.
2. **Check every field,** whatever the browser did. Shared checks live in function partials,
   for example `account/details/check` for a name and email.
3. **Answer.** On a refused post, either show the form again with the errors and a 422
   status (register, forgot password), or redirect with an error code
   (`/profile?error=email_taken`).

## The register form and duplicate emails

The register form asks `/api/check-user-email-signup` whether the email is free, when the
email field loses focus and again on submit if the email has changed. Submit waits for the
answer, so a quick submit cannot overtake the check.

The server is still the authority. The register page checks again, and the platform refuses
a second user with the same email when the user is created, so two registrations sent at
the same moment cannot both make an account.

## Messages

Error messages live in `account/details/messages`, keyed by field and code (`required`,
`invalid`, `taken`, `short`, `mismatch`), so the browser and the server say the same thing.
