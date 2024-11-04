let StripeModel = (() => {
    return {
        creditcard: {
            async createCreditCard(data) {
                let payload = {
                    "email": data.email,
                    "first_name": stripeFirstName.value,
                    "last_name": stripeLastName.value,
                    "stripe_credit_card": data.creditcard
                }
                let response = await StripeServices.createCreditCard({ 'payload': payload });
                if(response.state) {
                    return response;
                } else {
                    App.events.notyf('error', "Failed to create creditcard");
                    return response;
                }
            },
            async removeCreditCard(id) {
                let payload = {
                    id: id,
                    properties: { is_enabled: false }
                }
                let response = await StripeServices.deleteCreditCard({ payload });
                if (response.state) {
                    return response;
                } else {
                    App.events.notyf('error', "Failed to delete creditcard");
                    return response;
                }
            },
            async updateCreditCard(payload) {
                let response = await StripeServices.updateCreditCard({ payload });
                if (response.state) {
                    return response;
                } else {
                    App.events.notyf('error', "Failed to update creditcard");
                    return response;
                }
            },
        },
        customer: {

        }
    }
})();

window.StripeModel = StripeModel;