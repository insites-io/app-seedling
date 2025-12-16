# Form Validation Strategy

## Overview

This project uses a **two-layer validation approach**:
1. **Client-side validation** (JavaScript) - Provides immediate feedback and better UX
2. **Server-side validation** (Liquid form definitions) - Source of truth, always enforced

## Validation Flow

```
User Input → Client-side Validation → If Valid → Submit Form → Server-side Validation → Success/Error
                                    → If Invalid → Show Errors (no submit)
```

### Client-side validation
- Runs before form submission
- Provides immediate feedback
- Uses `App.validation` helpers and custom validators
- **Never trust client-side validation alone** - it can be bypassed

### Server-side validation
- Always runs on form submission
- Defined in form YAML frontmatter
- Returns errors that are displayed in the form
- **This is the authoritative validation**

## Standardized Validation Handler

All forms use `FormValidation.validateAndSubmit(event, options)` which:
- Prevents default submission
- Validates all fields in the form or specified container
- Returns `{ valid: boolean, errors: object }`
- Submits the form automatically if validation passes

### Usage Pattern

```javascript
// In form html-onsubmit attribute
html-onsubmit:"return FormValidation.validateAndSubmit(event);"

// Or with options
html-onsubmit:"return FormValidation.validateAndSubmit(event, { 
  containerId: 'personal-details-container',
  validateTel: true,
  checkEmail: true 
});"
```

## Validation Schema Standards

All form validation schemas should use consistent structure:

```yaml
fields:
  email:
    validation: 
      presence:
        message: Please use a valid email address
      email: 
        message: Please use a valid email address
      unique:  # Only for registration
        message: Email already exists
  password:
    validation: 
      presence:
        message: Password is required
      confirmation: true  # For password confirmation fields
```

**Avoid** boolean-only validation (e.g., `presence: true`) - always provide message objects.

## Form Types and Their Validation

### Sign In Form
- **Handler**: `FormValidation.validateAndSubmit(event)`
- **Validations**: Email format, password presence
- **No special handling needed**

### Registration Form
- **Handler**: `FormValidation.validateAndSubmit(event, { containerId: 'personal-details-container', validateTel: true, checkEmail: true })`
- **Validations**: Email uniqueness (async check), telephone format, all required fields
- **Special**: Email uniqueness check runs on blur, form submits after validation

### Forgot Password Form
- **Handler**: `FormValidation.validateAndSubmit(event)`
- **Validations**: Email format and presence
- **Simple validation only**

### Change Password Form
- **Handler**: `FormValidation.validateAndSubmit(event)`
- **Validations**: Password confirmation match, minimum length
- **Uses**: `UserProfileScript` for password-specific validation

## Custom Validators

### Email Uniqueness Check
- Runs asynchronously on email field blur
- Updates `emailInputInfo.status` with: `'clean'`, `'update'`, or `'error'`
- Form submission respects this status

### Telephone Validation
- Validates international phone number formats
- Uses regex: `/^[+]*[(]{0,1}[0-9]{1,4}[)]{0,1}[-\s\./0-9]*$/g`
- Applied to fields with `field="tel"` attribute

### Password Validation
- Minimum 6 characters
- Confirmation must match original password
- Validated both client and server-side

## Error Handling

All validation errors follow this pattern:
- Client-side: Set `field.hasError = true` and `field.errorMessage = "message"`
- Server-side: Errors returned in `form.errors['field_name']`
- Display: Use `{% if form.errors['field'] %} has-error {% endif %}` in templates

## Migration Guide

To update existing forms to use the unified handler:

1. Replace custom `html-onsubmit` handlers with `FormValidation.validateAndSubmit(event, options)`
2. Ensure validation schemas use message objects (not booleans)
3. Remove hard-coded form ID checks from JavaScript
4. Use options object to specify special behaviors (tel validation, email check, etc.)

