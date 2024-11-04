let stripeCard = document.getElementById('stripe-card');
let stripeCardModal = document.getElementById('stripe-modal');
let cardOptionsList = document.getElementById('card-options-list');
let noCardNotif = document.getElementById('no-card');
let cardFields = document.getElementById('credit-card-fields');

// Create an instance of Elements.
let elements = stripe.elements();
let card;
// Custom styling can be passed to options when creating an Element.
// (Note that this demo uses a wider set of styles than the guide below.)
let style = {
    base: {
        color: '#404040',
        fontFamily: '"Work Sans", sans-serif',
        fontSmoothing: 'antialiased',
        fontSize: '14px',
        '::placeholder': {
            color: '#8C94A4'
        }
    },
    invalid: {
        color: '#F27474',
        iconColor: '#F27474'
    }
};
// Handle Form Elements.
let stripeBtn = document.querySelectorAll('.card-form-submit');
let stripeCancelBtn = document.querySelectorAll('.card-form-cancel');
let errorElement = document.getElementById('card-errors');

let StripeElement = (() => {
    return {
        methods: {
            makeCardElement(token) {
                if (cardOptionsList && token) {
                    let grid = cardOptionsList.getAttribute('card-grid') || "large-4 medium-6 small-12";
                    let divEl = document.createElement("div");
                    divEl.className = `${grid} cell card-options`;
                    let insCardEl = document.createElement("ins-credit-card");
                    insCardEl.setAttribute('full-year', true);
                    insCardEl.setAttribute('brand', token.card.brand);
                    insCardEl.setAttribute('last-four', token.card.last4);
                    insCardEl.setAttribute('expiry-month', token.card.exp_month);
                    insCardEl.setAttribute('expiry-year', token.card.exp_year);
                    insCardEl.setAttribute('compact', '');
                    insCardEl.value = token.card.id;
                    divEl.appendChild(insCardEl);
                    cardOptionsList.appendChild(divEl);
                    StripeElement.init.dynamicCCEventListener(insCardEl, true);
                    StripeElement.methods.checkCardCount();
                }
            },
            validateStripeRequirements() {
                if (emailField && emailField.value) {
                    this.setButtonLoading(true);
                    this.tokenizedStripeCC();
                } else {
                    App.events.notyf('error', "Email is required");
                }
            },
            async tokenizedStripeCC() {
                stripe.createToken(card).then(async(result) => {
                    if (errorElement && result.error) {
                        // Inform the user if there was an error.
                        errorElement.textContent = result.error.message;
                        this.setButtonLoading(false);

                    } else {
                        // Send the token to your server.
                        let response = await this.createStripeCardModel(result.token);
                        // set stripe card token to form for payment
                        this.setStripeCardField(result.token);
                        this.setButtonLoading(false);
                        card.clear();
                        stripeCardModal.close();
                        App.events.notyf('success', "Credit card has been added");
                        this.makeCardElement(result.token);
                    }
                });
            },
            setButtonLoading(state) {
                stripeCancelBtn.forEach(el => {
                    el.disabled = state;
                });
                stripeBtn.forEach(el => {
                    el.loading = state;
                });
            },
            // AXIOS Create credit card model
            async createStripeCardModel(token) {
                let data = {
                    "email": emailField.value,
                    "first_name": stripeFirstName.value,
                    "last_name": stripeLastName.value,
                    "creditcard": token.id
                }
                let response = await StripeModel.creditcard.createCreditCard(data);
                // Insert the token ID into the form checkout - Optional if no element / not checkout form
                if (response.state && payByCardField)
                    payByCardField.setAttribute('value', token.id);
            },
            // Set checkout form with the token ID.
            setStripeCardField(token) {
                // Set token ID into the card field - Optional if no element / not checkout form
                if (payByCardField)
                    payByCardField.setAttribute('value', token.id);
            },
            checkCardCount() {
                let cards = cardFields.querySelectorAll('.card-options');
                if (cards.length === 0)
                    noCardNotif.classList.remove('hide');
                else
                    noCardNotif.classList.add('hide');
            }
        },
        events: {
            selectCard(selectedEl) {
                let cards = Array.from(document.getElementsByTagName('ins-credit-card'));
                if (cards) {
                    // remove error state of credit cards
                    cards.forEach(element => {
                        element.classList.remove('is-invalid');
                        element.active = false
                    });
                }
                // set selected state
                selectedEl.active = true;
                if (stripeCard)
                    stripeCard.value = selectedEl.value;
                stripeCard.setAttribute('value', selectedEl.value)
            },
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
                    if (selectedEl.active && stripeCard)
                        stripeCard.value = "";
                    selectedEl.parentNode.remove();
                    App.events.notyf('success', "Credit card has been removed");
                    StripeElement.methods.checkCardCount();
                }
            },
        },
        init: {
            dynamicCCEventListener(element, click = false) {
                setTimeout(() => {
                    element.addEventListener('insClick', () => {
                        StripeElement.events.selectCard(element);
                    });
                    element.addEventListener('insClose', () => {
                        StripeElement.events.removeCard(element);
                    });
                    if (click && element && element.querySelector('.ins-credit-card-wrap'))
                        element.querySelector('.ins-credit-card-wrap').click();
                }, 500);
            },
            eventListeners() {
                stripeCancelBtn.forEach(el => {
                    el.addEventListener('insClick', () => cardModal.close());
                })

                // Handle real-time validation errors from the card Element.
                card.on('change', function(event) {
                    if (errorElement && event.error) {
                        errorElement.textContent = event.error.message;
                    } else {
                        errorElement.textContent = '';
                    }
                });
                stripeBtn.forEach(el => {
                    el.addEventListener('insClick', () => {
                        StripeElement.methods.validateStripeRequirements();
                    });
                })
            },
            stripeElements() {
                // Create an instance of the card Element.
                card = elements.create('card', { style: style });
                // Add an instance of the card Element into the `card-element` <div>.
                card.mount('#card-element');
                StripeElement.init.eventListeners();
            }
        }
    }
})();
// Make sure component rendered
setTimeout(() => {
    StripeElement.init.stripeElements();
}, 500);