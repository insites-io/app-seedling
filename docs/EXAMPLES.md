# Common patterns and examples

## Authorization policy template
Use a consistent pattern: fetch data, guard nulls, echo explicitly.
```
---
name: policy_name
redirect_to: 403
---
{% liquid
  graphql data = 'modules/dashboard/account/check_2fa_setup'
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
{% graphql check_2fa_setup = 'modules/dashboard/account/check_2fa_setup' %}
{% assign otp_configured = check_2fa_setup.current_user.client[0].otp_configured %}
{% if otp_configured %} ... {% endif %}
```

## Unified form validation
All forms use `FormValidation.validateAndSubmit(event, options)` for consistent validation and submission:

**Simple form (sign in, forgot password):**
```liquid
{%- form 
  html-id: "sign-in-form"
  html-onsubmit:"return FormValidation.validateAndSubmit(event);" -%}
  <!-- form fields -->
{%- endform -%}
```

**Form with telephone validation and email uniqueness check (registration):**
```liquid
{%- form 
  html-id: "register-form"
  html-onsubmit:"return FormValidation.validateAndSubmit(event, { 
    containerId: 'personal-details-container', 
    validateTel: true, 
    checkEmail: true 
  });" -%}
  <!-- form fields -->
{%- endform -%}
```

**Validation schema (always use message objects, not booleans):**
```yaml
fields:
  email:
    validation: 
      presence:
        message: Please use a valid email address
      email: 
        message: Please use a valid email address
  password:
    validation: 
      presence:
        message: Password is required
```

See `docs/FORM_VALIDATION.md` for the complete validation strategy.

## API helper with debug logging
`modules/dashboard/public/assets/services/apiServices.js` and `modules/website/public/assets/services/formServices.js` log errors only when `window.APP_DEBUG === true`:
```
window.APP_DEBUG = true; // enable temporary console logging
await apiServices.processRequest('get', '/sessions/current');
```

