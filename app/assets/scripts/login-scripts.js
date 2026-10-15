/**
 * Form checks in the browser for the account pages (sign in, register, forgot password,
 * password reset and the emailed sign-in pages). They give quick feedback only: every
 * page checks the same things again on the server, and the server decides.
 */
let FormValidation = (function () {
    return {
        /**
         * Password: required, at least 6 characters
         */
        validatePasswordField(field) {
            if (field.value) {
                if (field.value.length >= 6) {
                    field.hasError = false;
                } else {
                    field.hasError = true;
                    field.errorMessage = "Minimum of 6 characters";
                }
            } else {
                field.hasError = true;
                field.errorMessage = "Password is required";
            }
        },

        /**
         * Password confirmation: must match the password field
         */
        validatePasswordConfirm(field) {
            const passwordField = document.getElementById('password');
            if (passwordField) {
                if (passwordField.value === field.value) {
                    field.hasError = false;
                } else {
                    field.hasError = true;
                    field.errorMessage = "Password doesn't match";
                }
            }
        },

        /**
         * Checks every [validate] field in a container
         * @param {HTMLElement} containerEl
         * @returns {Promise<boolean>} true when every field is valid
         */
        async validationForm(containerEl) {
            const fields = containerEl.querySelectorAll('[validate]');
            for (let index = 0; index < fields.length; index++) {
                const field = fields[index];
                const type = field.tagName.toLowerCase();
                switch (type) {
                    case 'div':
                        App.validation.validateRadio(field);
                        break;
                    case 'ins-input-file':
                        App.validation.validateFile(field);
                        break;
                    case 'ins-textarea':
                        App.validation.validateInput(field.querySelector('textarea'));
                        break;
                    case 'ins-input':
                    default:
                        if (field.field === 'password') {
                            if (field.id === 'password_confirmation') {
                                this.validatePasswordConfirm(field);
                            } else {
                                this.validatePasswordField(field);
                            }
                        } else if (field.field === 'email') {
                            App.validation.validateEmail(field);
                        } else {
                            App.validation.validateInput(field);
                        }
                        break;
                }
            }
            return App.validation.checkInvalidFields(containerEl);
        },

        /**
         * Checks a form and submits it when it passes. Use it as the form's onsubmit:
         *   onsubmit="return FormValidation.validateAndSubmit(event);"
         * @param {Event} event - the submit event
         * @param {Object} options
         * @param {string} options.containerId - check only the fields inside this element
         * @param {boolean} options.checkEmail - wait for the "email already used" check (register)
         * @returns {boolean} always false: the form is submitted from here when it passes
         */
        async validateAndSubmit(event, options = {}) {
            if (event) {
                event.preventDefault();
            }

            const formElem = event.target.closest('form') || event.target;
            if (!formElem || formElem.tagName !== 'FORM') {
                return false;
            }

            // One submit at a time: a second click while this one is being checked does nothing
            if (formElem.dataset.submitting === 'true') {
                return false;
            }
            formElem.dataset.submitting = 'true';
            const done = (submit) => {
                if (submit) {
                    formElem.submit();
                } else {
                    formElem.dataset.submitting = 'false';
                    this.setButtonsDisabled(formElem, false);
                }
                return false;
            };
            this.setButtonsDisabled(formElem, true);

            const containerEl = options.containerId
                ? document.getElementById(options.containerId)
                : formElem;
            if (!containerEl) {
                return done(false);
            }

            const isValid = await this.validationForm(containerEl);
            if (!isValid) {
                return done(false);
            }

            if (options.checkEmail) {
                // Wait for the email check to finish, running it now if it has not run
                // for the email in the field. The register page checks again on the server.
                const status = await LoginScript.methods.checkEmailNow();
                if (status === 'taken') {
                    const emailElem = document.getElementById('email');
                    if (emailElem) {
                        emailElem.hasError = true;
                        emailElem.errorMessage = "Email has already been used.";
                    }
                    return done(false);
                }
            }

            return done(true);
        },

        setButtonsDisabled(formElem, state) {
            formElem.querySelectorAll('ins-button[type="submit"]').forEach(btn => {
                btn.disabled = state;
            });
        }
    }
})();

window.FormValidation = FormValidation;

// A page restored from the back/forward cache keeps a form marked as submitting; free it
window.addEventListener('pageshow', (event) => {
    if (event.persisted) {
        document.querySelectorAll('form[data-submitting="true"]').forEach(form => {
            form.dataset.submitting = 'false';
            FormValidation.setButtonsDisabled(form, false);
        });
    }
});

/**
 * The register form's "email already used" check. It runs when the email field loses
 * focus, and again on submit if the email has changed since. Statuses: 'unchecked',
 * 'free', 'taken', or 'unknown' when the check could not run (the server then decides).
 */
let LoginScript = (function () {
    let emailCheck = { email: null, status: 'unchecked', pending: null };

    return {
        methods: {
            async checkEmailNow() {
                const emailInput = document.getElementById('email');
                if (!emailInput) {
                    return 'unknown';
                }
                const email = (emailInput.value || '').trim().toLowerCase();
                if (emailCheck.email === email) {
                    if (emailCheck.pending) {
                        return await emailCheck.pending;
                    }
                    if (emailCheck.status !== 'unchecked') {
                        return emailCheck.status;
                    }
                }
                emailCheck = { email: email, status: 'unchecked', pending: null };
                emailCheck.pending = LoginScript.methods.askServer(email).then(status => {
                    if (emailCheck.email === email) {
                        emailCheck.status = status;
                        emailCheck.pending = null;
                    }
                    return status;
                });
                return await emailCheck.pending;
            },
            async askServer(email) {
                const url = '/check-user-email-signup?email=' + encodeURIComponent(email);
                const response = await apiServices.processRequest('get', url);
                if (response.state && response.data && response.data.email_status) {
                    return response.data.email_status === 'invalid' ? 'taken' : 'free';
                }
                return 'unknown';
            },
            async onEmailBlur() {
                const emailInput = document.getElementById('email');
                if (!emailInput || !App.validation.validateEmail(emailInput)) {
                    return;
                }
                const status = await LoginScript.methods.checkEmailNow();
                if (status === 'taken') {
                    emailInput.hasError = true;
                    emailInput.errorMessage = "Email has already been used.";
                }
            }
        },
        init: {
            // Register form only
            initSignUp() {
                const form = document.getElementById('register-form');
                const emailInput = document.getElementById('email');
                if (form && emailInput) {
                    emailInput.addEventListener('insBlur', () => LoginScript.methods.onEmailBlur());
                }
            }
        }
    }
})();

window.LoginScript = LoginScript;

setTimeout(() => {
    LoginScript.init.initSignUp();
}, 200);
