/**
 * Form checks in the browser for the profile page: the details form and the change-password
 * form. They give quick feedback only: /profile/details and /profile/password check the
 * same things again on the server, and the server decides.
 */
let UserProfileScript = (function () {
    return {
        methods: {
            disableFormButtons(formElem, state = true) {
                formElem.querySelectorAll('ins-button').forEach(btn => btn.disabled = state);
            },
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
            async validatePasswordForm(containerEl) {
                containerEl.querySelectorAll('[validate]').forEach(field => {
                    if (field.id === 'password_confirmation') {
                        this.validatePasswordConfirm(field);
                    } else {
                        this.validatePasswordField(field);
                    }
                });
                return App.validation.checkInvalidFields(containerEl);
            },
            /**
             * The onsubmit of both profile forms:
             *   onsubmit="return UserProfileScript.methods.validateForm(event);"
             */
            async validateForm(event) {
                if (event) {
                    event.preventDefault();
                }
                const formElem = event.target.closest('form') || event.target;
                if (!formElem || formElem.dataset.submitting === 'true') {
                    return false;
                }

                if (formElem.id === 'user-profile-form') {
                    if (await App.validation.validateForm(formElem)) {
                        formElem.dataset.submitting = 'true';
                        this.disableFormButtons(formElem);
                        formElem.submit();
                    }
                    return false;
                }

                if (formElem.id === 'user-password-form') {
                    if (await this.validatePasswordForm(formElem)) {
                        const result = await Swal.fire({
                            title: `<i class="icon-alert-circle"></i>Change Password?`,
                            html: `You will be signed out after changing your password.`,
                            confirmButtonText: `Submit`,
                            showCancelButton: true,
                            cancelButtonText: `Cancel`,
                            allowOutsideClick: false,
                            customClass: "swal-user-account"
                        });
                        if (result.isConfirmed) {
                            formElem.dataset.submitting = 'true';
                            this.disableFormButtons(formElem);
                            formElem.submit();
                        }
                    }
                    return false;
                }
                return false;
            }
        }
    }
})();

window.UserProfileScript = UserProfileScript;
