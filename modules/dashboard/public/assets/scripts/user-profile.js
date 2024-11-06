//Insites CRM -> Contacts : mobile_phone_number, mobile_phone_country_code
let contactMobileFields = {
    inputTel: document.getElementById('mobile-phone'),
    phone_number: document.getElementById('mobile_phone_number'),
    country_code: document.getElementById('mobile_phone_country_code')
}

let addressForm = {
    deletBtn: document.getElementById('deleteAddressBtn-main'),
    deleteBtnTrigger: document.getElementById('deleteAddressBtn2'),
    saveAddressBtn: document.querySelectorAll('.save-address-btn')
}

let customerProfileForm = {
    updateProfileBtn: document.getElementsByClassName('submit-btn'),
    updatePasswordBtn: document.getElementById('save-password-btn')
}

let tmpUserPayload = {
    'first_name': "",
    'last_name': "",
    'email': ""
}

/* Variable that handles the credit card elements */
let addCardBtn = document.querySelectorAll('.add-credit-card');
let cardModal = document.getElementById('stripe-modal');

/* Variables that handles the data for the Order History  Table*/
var orderListTable = document.getElementById('order-list-table');
let pageBaseUrl = "";
let orderListFilter = {
    "page": "1",
    "per_page": "10",
    "sort_by": ""
};


let UserProfileScript = (function () {
    return {
        methods: {
            pricify(number) {
                return number.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            },
            disableFormButtons(formElem, state = true) {
                let buttons = formElem.querySelectorAll('ins-button');
                buttons.forEach(btn => btn.disabled = state);
            },
            validateTelField() {
                /* Validation for the telephone field */
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
            validatePasswordConfirm(field) {
                let passFields = document.getElementById('password');
                if (passFields) {
                    if (passFields.value === field.value) {
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
            async validateForm(event) {
                /* Validation and scripts done before submission of forms */
                /* Attached on the on-submit event of the form */
                /* Can identify form submitted by using their id */
                event ? event.preventDefault() : '';

                //Get id and element to identify the kind of form submitted
                let formId = event.target.id;
                let formElem = document.getElementById(formId);

                // Check what form is being validated...
                if (formId == 'user-profile-form' || formId == 'user-company-form') {
                    //Validation for User profile/company
                    this.validateTelField();

                    if (await App.validation.validateForm(formElem)) {                        
                        this.disableFormButtons(formElem);
                        customerProfileForm.updateProfileBtn.loading = true;
                        formElem.submit();
                    }
                } else if (formId == 'user-password-form') {
                    // Validation and function for update of password
                    if (await this.validationForm(formElem)) {
                        const customIcon = `<i class="icon-alert-circle"></i>`; 

                        let confirm = await Swal.fire({
                            title: customIcon + `Change Password?`,
                            html: `You will be logged out after changing your password.`,
                            confirmButtonText: `Submit`,
                            showCancelButton: true,
                            cancelButtonText: `Cancel`,
                            allowOutsideClick: false,
                            customClass: "swal-user-account"
                            }).then( async (result) => {
                                if (result.isConfirmed) {
                                    this.disableFormButtons(formElem);
                                    customerProfileForm.updatePasswordBtn.loading = true;
                                    formElem.submit();
                                }
                            });
                    }
                } else {
                    //Validation for other (account type) forms
                    if (await App.validation.validateForm(formElem)) {
                        formElem.submit();
                    }
                }
            },
            checkCardCount() {
                let cards = cardFields.querySelectorAll('.card-options');
                if (cards.length === 0)
                    noCardNotif.classList.remove('hide');
                else
                    noCardNotif.classList.add('hide');
            },
            initBaseURL() {
                pageBaseUrl = window.location.pathname;
            },
            initOrderTableContents() {
                // Prepare / process data for adding to the Order Table History
                orderListTable.tableHeaders = tableHeaders;

                let tableData = tableContent.results.map(data => {
                    let props = data;
                    let shippingArray = [];
                    //Combine the fields connected to address to make a full address
                    if (props.shipping_address_1) {
                        shippingArray.push(props.shipping_address_1);
                    }
                    if (props.shipping_address_2) {
                        shippingArray.push(props.shipping_address_2);
                    }
                    if (props.shipping_city) {
                        shippingArray.push(props.shipping_city);
                    }
                    if (props.shipping_state) {
                        shippingArray.push(props.shipping_state);
                    }
                    if (props.shipping_postcode) {
                        shippingArray.push(props.shipping_postcode);
                    }
                    if (props.shipping_country) {
                        shippingArray.push(props.shipping_country);
                    }
                    let fullAddress = shippingArray.join(", ");

                    //Format date to human radable one
                    let tmpDate = new Date(props.date_time);
                    let formattedDate = tmpDate.getFullYear() + "-" + (tmpDate.getMonth() + 1) + "-" + tmpDate.getDate();

                    return {
                        id: data.id,
                        "Order Number": data.id,
                        "Items": data.cart.length,
                        "Total Price": this.pricify(props.total_amount / 100.0),
                        "Shipping Address": fullAddress,
                        "Date Ordered": formattedDate,
                        "Status": props.order_status
                    }
                })

                // Add the created data to the table 
                orderListTable.tableData = tableData;
                // Add event litener to link to detail of each row
                orderListTable.addEventListener('insTableRowAction', event => {
                    window.location.href = '/order-history/' + event.detail.data.id;
                });

            },
            initOrderFilterValues() {
                let query = window.location.search.substring(1);
                let vars = query.split("&");
                for (var i = 0; i < vars.length; i++) {
                    let pair = vars[i].split("=");
                    orderListFilter[pair[0]] = pair[1];
                }
                UserProfileScript.methods.putOrderFilterValues();
            },
            putOrderFilterValues() {
                if (orderListTable) {
                    orderListTable.pageSize = orderListFilter.per_page;
                    orderListTable.pageNumber = orderListFilter.page;
                    if (maxCount) {
                        orderListTable.totalCount = maxCount;
                    }
                }
            },
            buildParamlist() {
                //Get all items on the object and buld them as parameters
                let entries = Object.entries(orderListFilter);
                let tmpParamArr = [];
                for (let a = 0; a < entries.length; a++) {
                    if (entries[a][1] != "") {
                        tmpParamArr.push(entries[a].join('='));
                    }
                }
                let tmpParam = tmpParamArr.join('&');
                return tmpParam;
            },


        },
        events: {
            async removeCard(selectedEl) {
                let confirm = await App.events.swal('warning',
                    'Remove Card?',
                    'Are you sure you want to remove this credit card?',
                    'Remove',
                    true,
                    'icon-trash');
                if (confirm) {
                    if (selectedEl.dataset.id) {
                        let response = await StripeModel.creditcard.removeCreditCard(selectedEl.dataset.id);
                        if (response.state && response.data.items) {
                            // API successfully removed card
                        }
                    }
                    selectedEl.parentNode.remove();
                    App.events.notyf('success', "Credit card has been removed");
                    UserProfileScript.methods.checkCardCount();
                }
            },
            tablePaginationHandler(event) {
                orderListFilter.page = event.detail.pageNumber;
                orderListFilter.per_page = event.detail.pageSize;

                let paramStr = UserProfileScript.methods.buildParamlist();
                let urlStr = pageBaseUrl + "?" + paramStr;
                window.location.href = urlStr;

            }
        },
        init: {
            initEventListener() {
                if (addCardBtn) {
                    addCardBtn.forEach(btn => btn.addEventListener('insClick', () => cardModal.open()));
                }
                this.initCardsEventListener();
            },
            initCardsEventListener() {
                let iterations = 5;
                let setStateInterval = setInterval(() => {
                    let cards = Array.from(document.getElementsByTagName('ins-credit-card'));
                    if (cards) {
                        cards.forEach(element => {
                            element.addEventListener('insClick', () => {
                                StripeElement.events.selectCard(element);
                            });
                            element.addEventListener('insClose', () => {
                                UserProfileScript.events.removeCard(element);
                            });
                        });
                        clearInterval(setStateInterval);
                    } else {
                        iterations++;
                        if (iterations > 5)
                            clearInterval(setStateInterval);
                    }
                }, 300);
            },
            initOrderListing() {
                if (orderListTable) {
                    UserProfileScript.methods.initBaseURL();
                    UserProfileScript.methods.initOrderFilterValues();
                    UserProfileScript.methods.initOrderTableContents();
                    orderListTable.addEventListener('insPaginationChange', UserProfileScript.events.tablePaginationHandler);
                }

            }
        }
    }
})();


setTimeout(() => {
    UserProfileScript.init.initEventListener();
    UserProfileScript.init.initOrderListing();
}, 200);

