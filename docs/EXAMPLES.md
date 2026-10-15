# Common patterns and examples

## Authorization policy template
Use a consistent pattern: fetch data, guard nulls, echo explicitly.
```
---
name: policy_name
redirect_to: 403
---
{% liquid
  graphql data = 'account/check_2fa_setup'
  assign user = data.current_user.client | first

  comment Explain the decision tree and defaults endcomment
  if user == blank
    echo false
    return
  endif

  if user.otp_configured == true
    echo true
  else
    echo false
  endif
%}
```

## GraphQL in Liquid templates
```
{% graphql check_2fa_setup = 'account/check_2fa_setup' %}
{% assign otp_configured = check_2fa_setup.current_user.client[0].otp_configured %}
{% if otp_configured %} ... {% endif %}
```

## Forms
Every form is a plain `<form>` with the authenticity token that posts to its own page, and
uses `FormValidation.validateAndSubmit(event, options)` for the checks in the browser:

```liquid
<form id="register-form" action="/register" method="post" novalidate
      onsubmit="return FormValidation.validateAndSubmit(event, { containerId: 'personal-details-container', checkEmail: true });">
  <input type="hidden" name="authenticity_token" value="{{ context.authenticity_token }}">
  <!-- fields -->
</form>
```

See `docs/FORM_VALIDATION.md` for the page the form posts to and the server-side checks.

## A value inside an HTML attribute
An output tag on Insites turns an escaped double quote back into a quote, so `value="{{ x | escape }}"`
can be broken out of. Escape the value first and write it with `print`:

```liquid
{%- assign email_attr = email | escape -%}
<input type="hidden" name="email" value="{% print email_attr %}">
```

## API helper with debug logging
`app/assets/services/apiServices.js` logs errors only when `window.APP_DEBUG === true`:
```
window.APP_DEBUG = true; // enable temporary console logging
await apiServices.processRequest('get', '/sessions/current');
```

