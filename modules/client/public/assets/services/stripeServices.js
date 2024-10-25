let StripeServices = (function () {
    return {
        // create Stripe creditcard & customer + create pOS creditcard & customer model
        createCreditCard: async function (payload) {
            let url = `/stripe/create-credit-card.json`;
            return await apiServices.processRequest('post', url, payload);
        },
        // update pOS creditcard model
        updateCreditCard: async function (payload) {
            let url = `/stripe/update-credit-card.json`;
            return await apiServices.processRequest('post', url, payload);
        },        
        // delete stripe card
        deleteCreditCard: async function (payload) {
            let url = `/stripe/delete-credit-card.json`;
            return await apiServices.processRequest('post', url, payload)
        }
    }
})();