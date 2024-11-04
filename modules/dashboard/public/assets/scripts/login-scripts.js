let emailInputInfo =  {
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

let LoginScript = (function () {
    return {
        methods: {
            validateTelField() {
                //Function to validate telephone input fields
                let isTel = /^[+]*[(]{0,1}[0-9]{1,4}[)]{0,1}[-\s\./0-9]*$/g;
                let telFields = document.querySelectorAll("[field='tel']");
                telFields.forEach(field => {
                    if (field.required) {
                        if (field.value && isTel.test(field.value) === true) {
                            field.hasError = false;
                        } else
                            field.hasError = true;
                    } else {
                        if (field.value.trim() === "") {
                            field.hasError = false;
                        } else {
                            field.hasError = !isTel.test(field.value) === true;
                        }
                    }
                });
            },
            validatePasswordField(field){
                if (field.value) {
                    if((field.value.length >= 6)){
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
            validatePasswordConfirm(field){
                let passFields = document.getElementById('password');
                if(passFields){
                    if(passFields.value === field.value){
                        field.hasError = false;
                    } else {                        
                        field.hasError = true;
                        field.errorMessage = "Password doesn't match";
                    }
                } 
            },
            async validationForm(containerEl) {
                for (let index = 0; index < containerEl.querySelectorAll('[validate]').length; index++) {
                    let field = containerEl.querySelectorAll('[validate]')[index];
                    let type = field.tagName.toLowerCase();
                    switch (type) {
                        case 'div':
                            App.validation.validateRadio(field);
                            break;
                        case 'ins-input-file':
                            App.validation.validateFile(field);
                            break;
                        case 'ins-textarea':
                            App.validation.validateInput(field.querySelector('textarea'));
                            break
                        case 'ins-input':
                        default:
                            if(field.field === 'password'){
                                if(field.id === 'password_confirmation'){
                                    this.validatePasswordConfirm(field);
                                } else {
                                    this.validatePasswordField(field);
                                }
                            } else if(field.field === 'email'){
                                App.validation.validateEmail(field);
                            } else{
                                App.validation.validateInput(field);
                            }
                            break;
                    }
                }
                return App.validation.checkInvalidFields(containerEl);
            },
            async validateForm(event, groupElem) {
                event ? event.preventDefault(): '';
                //Get id and element to identify the kind of form submitted
                let formId = event.target.id;
                let formElem = document.getElementById(formId).closest('form'); 
                // Check what form is being validated...
                if(formId == 'submit-personal-details' || formId == 'submit-company-details'){
                    //Validation for Sign Up Form
                    this.validateTelField();
                    if(await this.validationForm(groupElem)){
   
                        switch(emailInputInfo.status){
                            case 'clean':{ //email is clean
                                //formElem.submit();
                                return true;
                            }break;
                            case 'update':{ //email 'update'
                                this.changeFormToAppend(formElem, emailInputInfo.id);
                                //formElem.submit();
                                return true;
                            }break;
                            case 'error':{ //email is used
                                let emailElem = document.getElementById('email');
                                emailElem.hasError = true;
                                emailElem.errorMessage = "Email has already been used.";    
                            }break;
                        }
                    }
                } else if (formId == 'password-reset-form'){
                    if(await this.validationForm(formElem)){
                        formElem.submit();
                    }

                } else {
                    //Validation for other forms
                    if(await App.validation.validateForm(formElem)){
                        formElem.submit();
                    }
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