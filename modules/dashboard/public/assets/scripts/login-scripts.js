// Email uniqueness check state (for registration forms)
let emailInputInfo = {
    status: 'clean',
    id: null
}

//Personal Details
const mobileFields = {
    inputTel: document.getElementById('mobile-phone'),
    phone_number: document.getElementById('mobile_phone_number'),
    country_code: document.getElementById('mobile_phone_country_code')
}

//Company Details
const companyMobileFields = {
    inputTel: document.getElementById('company-mobile-phone'),
    phone_number: document.getElementById('company_mobile_phone_number'),
    country_code: document.getElementById('company_mobile_phone_country_code')
}

/**
 * Unified Form Validation Handler
 * Standardizes form validation across all forms in the application
 */
let FormValidation = (function () {
    return {
        /**
         * Validates telephone input fields
         */
        validateTelField() {
            const isTel = /^[+]*[(]{0,1}[0-9]{1,4}[)]{0,1}[-\s\./0-9]*$/g;
            const telFields = document.querySelectorAll("[field='tel']");
            telFields.forEach(field => {
                if (field.required) {
                    if (field.value && isTel.test(field.value) === true) {
                        field.hasError = false;
                    } else {
                        field.hasError = true;
                    }
                } else {
                    if (field.value.trim() === "") {
                        field.hasError = false;
                    } else {
                        field.hasError = !isTel.test(field.value) === true;
                    }
                }
            });
        },

        /**
         * Validates password field (minimum 6 characters)
         */
        validatePasswordField(field) {
            if (field.value) {
                if ((field.value.length >= 6)) {
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
         * Validates password confirmation matches original password
         */
        validatePasswordConfirm(field) {
            const passFields = document.getElementById('password');
            if (passFields) {
                if (passFields.value === field.value) {
                    field.hasError = false;
                } else {
                    field.hasError = true;
                    field.errorMessage = "Password doesn't match";
                }
            }
        },

        /**
         * Validates all fields in a container element
         * @param {HTMLElement} containerEl - Container element with fields to validate
         * @returns {Promise<boolean>} - True if all fields are valid
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
         * Unified form validation and submission handler
         * @param {Event} event - Form submit event
         * @param {Object} options - Validation options
         * @param {string} options.containerId - ID of container element to validate (defaults to form)
         * @param {boolean} options.validateTel - Whether to validate telephone fields
         * @param {boolean} options.checkEmail - Whether to check email uniqueness status (for registration)
         * @returns {boolean} - False to prevent default submission, true if validation passes
         */
        async validateAndSubmit(event, options = {}) {
            if (event) {
                event.preventDefault();
            }

            const formId = event.target.id;
            const formElem = document.getElementById(formId)?.closest('form') || event.target.closest('form');
            
            if (!formElem) {
                console.error('FormValidation: Could not find form element');
                return false;
            }

            // Determine container element (form or specified container)
            const containerEl = options.containerId 
                ? document.getElementById(options.containerId) 
                : formElem;

            if (!containerEl) {
                console.error('FormValidation: Could not find container element');
                return false;
            }

            // Validate telephone fields if requested
            if (options.validateTel) {
                this.validateTelField();
            }

            // Perform validation
            const isValid = await this.validationForm(containerEl);

            if (!isValid) {
                return false;
            }

            // Check email uniqueness status for registration forms
            if (options.checkEmail) {
                switch (emailInputInfo.status) {
                    case 'clean':
                        // Email is new, proceed with submission
                        formElem.submit();
                        return false; // Prevent default since we're submitting
                    case 'update':
                        // Email exists but no profile, update existing user
                        LoginScript.methods.changeFormToAppend(formElem, emailInputInfo.id);
                        formElem.submit();
                        return false; // Prevent default since we're submitting
                    case 'error':
                        // Email is already in use
                        const emailElem = document.getElementById('email');
                        if (emailElem) {
                            emailElem.hasError = true;
                            emailElem.errorMessage = "Email has already been used.";
                        }
                        return false; // Prevent submission
                    default:
                        // Unknown status, don't submit
                        return false;
                }
            }

            // Standard validation passed, submit form
            formElem.submit();
            return false; // Prevent default since we're submitting
        }
    }
})();

// Expose globally
window.FormValidation = FormValidation;

let LoginScript = (function () {
    return {
        methods: {
            validateTelField() {
                return FormValidation.validateTelField();
            },
            validatePasswordField(field) {
                return FormValidation.validatePasswordField(field);
            },
            validatePasswordConfirm(field) {
                return FormValidation.validatePasswordConfirm(field);
            },
            async validationForm(containerEl) {
                return await FormValidation.validationForm(containerEl);
            },
            /**
             * Legacy validateForm method - maintained for backward compatibility
             * @deprecated Use FormValidation.validateAndSubmit() instead
             */
            async validateForm(event, groupElem) {
                // For signup forms with email check
                const formId = event.target.id;
                if (formId === 'submit-personal-details' || formId === 'submit-company-details') {
                    return await FormValidation.validateAndSubmit(event, {
                        containerId: groupElem?.id || 'personal-details-container',
                        validateTel: true,
                        checkEmail: true
                    });
                }
                // For password reset form
                else if (formId === 'password-reset-form') {
                    return await FormValidation.validateAndSubmit(event, {
                        validateTel: false,
                        checkEmail: false
                    });
                }
                // For other forms (sign in, etc.)
                else {
                    return await FormValidation.validateAndSubmit(event, {
                        validateTel: false,
                        checkEmail: false
                    });
                }
            },
            async checkSignUpUserEmail(event){ 
                // Attached to the eventlistener
                let emailInput = document.getElementById('email');
                let varEmail = document.getElementById('email').value
                if(App.validation.validateEmail(emailInput)){
                    let url = '/check-user-email-signup?'+ 'email='+ varEmail ;
                    let response = await apiServices.processRequest('get', url);
                    if(response.state && response.data) {
                        //Check / Handle if user exist
                        LoginScript.methods.checkUserEmail(emailInput, response.data);
                    } 
                }
            },
            checkUserEmail(emailElem, data){
                if(data.email_status == "invalid"){
                    //Profile in account is already existing (Active / Inactive)
                    emailElem.hasError = true;
                    emailElem.errorMessage = data.message;
                    this.updateEmailInputInfo('error');
                } 
                else if(data.email_status == "no-profile") {
                    //Profile has no profile
                    emailElem.hasError = false;
                    this.updateEmailInputInfo('update', data.email_id);
                } else {
                    // New email
                    emailElem.hasError = false;
                    this.updateEmailInputInfo('clean');
                }
            },
            changeFormToAppend(formElement, id){
                let tmpInput = document.createElement("input");
                tmpInput.name = "_method";
                tmpInput.type = "hidden";
                tmpInput.value = "patch"
                formElement.appendChild(tmpInput);
                let tmpSrc = formElement.querySelector('input[name="resource_id"]');
                tmpSrc.value = id;
                formElement.action = '/api/users/' + id;
            },
            updateEmailInputInfo(status, id = null){
                emailInputInfo.status = status;
                emailInputInfo.id = id;
            }
        },
        init: {
            //Initialise form if signup (only applies to sign up)
            initSignUp() {
                let elem = document.getElementById('register-form');
                if(elem){
                    let emailInput = document.getElementById('email');
                    emailInput.addEventListener('insBlur', LoginScript.methods.checkSignUpUserEmail);
                } 
            }
        }
    }
})();

setTimeout(() => {
    LoginScript.init.initSignUp();
}, 200);