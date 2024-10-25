let sameAddressBtn = document.getElementById('same-billing');
let sameShippingDetailsBtn = document.getElementById('same-shipping');

//let addCardBtn = document.getElementById('add-card-btn');
//let cardModal = document.getElementById('stripe-modal');
let checkoutSubmitBtn = document.getElementById('checkout-submit-btn');
let checkoutForm = document.getElementById('checkout-form');

//------------------------------------------



let Paybill = (function() {
    return {
        validation: {
            addressCardsHasError(step, error) {
                step.querySelectorAll('.address-options ins-checkbox-card')
                    .forEach(element => {
                        error
                            ?
                            element.classList.add('is-invalid') :
                            element.classList.remove('is-invalid')
                    });
            },
            validateCreditCard(currentStep) {
                let cardValid = currentStep.querySelectorAll("#stripe-card[required] .is-invalid");
                let container = currentStep.querySelector('.validate-credit-card');
                if (container) {
                    if (cardValid && cardValid.length > 0) {
                        container.querySelector('.error-message').classList.remove('hide');
                        Paybill.validation.creditCardsHasError(container, true);
                    } else {
                        container.querySelector('.error-message').classList.add('hide');
                        Paybill.validation.creditCardsHasError(container, false);
                    }
                }
            },
            creditCardsHasError(step, error) {
                step.querySelectorAll('.card-options ins-credit-card')
                    .forEach(element => {
                        error
                            ?
                            element.classList.add('is-invalid') :
                            element.classList.remove('is-invalid')
                    });
            },
        },
        events: {
            async payBillsSubmit(event) {
                event.preventDefault();
                checkoutSubmitBtn.loading = true;
                let form = event.srcElement;
                let validAmount = true;
                let billAmountEl = document.getElementById('bill-amount');
                let isValid = await App.validation.validateForm(form);

                if (billAmountEl) {
                    billAmountEl.hasError = !(billAmountEl.value && Math.sign(parseFloat(billAmountEl.value)) > 0);
                    validAmount = !billAmountEl.hasError;
                }

                //Phone Number
                let insPhone = document.getElementById('ins-phone-number');
                let phoneNumber = document.getElementById('phone-number');
                if (insPhone && phoneNumber) {
                    let phoneValues = await insPhone.getValues();
                    phoneNumber.value = phoneValues.country_code + " " + phoneValues.phone_number;
                }

                Paybill.validation.validateCreditCard(form);

                if (isValid && validAmount) {
                    //payBillAddOrder();
                    form.submit();
                } else {
                    App.events.notyf("error", "Please check missing fields");
                    checkoutSubmitBtn.loading = false
                }
                return false;
            },
            selectAddressCard(addressCard) {
                let name = addressCard.getAttribute('name');
                // remove error state of address cards - by field name
                document.getElementsByName(name).forEach(el => {
                    el.classList.remove('is-invalid');
                    el.removeAttribute('selected');
                    el.selected = false;
                });
                // set selected state
                addressCard.setAttribute('selected', true);
                addressCard.selected = true;
                this.fillAddressField(addressCard);
            },
            fillAddressField(addressCard) {
                let name = addressCard.getAttribute('name');
                let type = name.split('-')[0];

                document.getElementById(`${type}-address-search`).value = addressCard.dataset.address;
                document.getElementById(`${type}_address_id`).value = addressCard.value;
                document.getElementById(`${type}_address_1`).value = addressCard.dataset.address_1 || "";
                document.getElementById(`${type}_address_2`).value = addressCard.dataset.address_2 || "";
                document.getElementById(`${type}_city`).value = addressCard.dataset.city || "";
                document.getElementById(`${type}_state`).value = addressCard.dataset.state || "";
                document.getElementById(`${type}_postcode`).value = addressCard.dataset.postcode || "";
                document.getElementById(`${type}_country`).value = addressCard.dataset.country || "";
            },
            addressInputEvent(event) {
                let type = event.target.getAttribute('id').split('_')[0];
                addressValueChanged = true;
                AddressLookup.methods.unselectAddressCards(type);
                if (sameAddressBtn)
                    sameAddressBtn.checked = false;
            }
        },
        init: {
            initEventListener() {
                // if(addCardBtn) {
                //     addCardBtn.addEventListener('insClick',() => cardModal.open());
                // }

                //this.initShippingDetailsListener();
                this.initAddressFieldInputListener();
                this.initAddressBtnListener();
                this.initAddressCardListener();
                this.initCardsEventListener();
            },
            initAddressFieldInputListener() {
                let shippingAddressFields = document.querySelectorAll('[shipping-address-field]');
                this.bindAddressInputListener(shippingAddressFields);
                let billingAddressFields = document.querySelectorAll('[billing-address-field]');
                this.bindAddressInputListener(billingAddressFields);
            },
            bindAddressInputListener(fields) {
                fields.forEach((field) => {
                    field.addEventListener('insInput', (event) => {
                        Paybill.events.addressInputEvent(event);
                    });
                });
            },
            initAddressCardListener() {
                let addressCards = Array.from(document.querySelectorAll('ins-checkbox-card'));
                addressCards.forEach(address => {
                    address.addEventListener('insClick', () => {
                        Paybill.events.selectAddressCard(address);
                    });
                });
            },
            initAddressBtnListener() {
                let buttons = Array.from(document.getElementsByClassName('add-address-btn'));
                buttons.forEach(btn => {
                    btn.addEventListener('insClick', () => {
                        let name = btn.getAttribute('name');
                        let fieldGroup = document.getElementById(name);
                        fieldGroup.classList.remove('hide');
                        fieldGroup.scrollIntoView({
                            behavior: "smooth",
                            block: "center", // vertical position
                            inline: "start" // horizontal position
                        });
                        fieldGroup.querySelector('ins-input input').focus();
                    });
                });
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
                                StripeElement.events.removeCard(element);
                            });
                        });
                        clearInterval(setStateInterval);
                    } else {
                        iterations++;
                        if (iterations > 5)
                            clearInterval(setStateInterval);
                    }
                }, 300);
            }
        }
    }
})();

setTimeout(() => {
    Paybill.init.initEventListener();
}, 200);