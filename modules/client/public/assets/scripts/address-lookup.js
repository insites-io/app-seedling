let addressValueChanged = false;

var AddressLookup = (function () {
    // google address lookup field
    let searchAddressElement; 

    return {
        methods: {
            fillAddress(field, type) {            
                let address = field.getPlace();
                let geometry = {
                    "latitude": address.geometry.location.lat(),
                    "longitude": address.geometry.location.lng()
                };            
                    AddressLookup.methods.resetAddress(type);
                    AddressLookup.methods.unselectAddressCards(type);
                if (address && address.address_components) {                    
                    AddressLookup.methods.mapGoogleAddress(address.address_components, type, geometry);
                    addressValueChanged = true;
                }
            },
            resetAddress(type) {
                let addressField = document.querySelectorAll(`[${type}-address-field]`);
                for (let i = 0; i < addressField.length; i++) {
                    addressField[i].value = "";
                }
            },
            unselectAddressCards(type) {
                let cards = document.querySelectorAll(`ins-checkbox-card[name="${type}-address-cards"]`);
                    cards.forEach(el => {
                        el.classList.remove('is-invalid');
                        el.removeAttribute('selected');
                        el.selected = false;
                    });
            },
            mapGoogleAddress(address, name, geometry) {
                //clear values
                if(document.getElementById(`${name}_address_1`))
                    document.getElementById(`${name}_address_1`).value = "";
                if(document.getElementById(`${name}_address_2`))
                    document.getElementById(`${name}_address_2`).value = "";
                if(document.getElementById(`${name}_suburb`))
                    document.getElementById(`${name}_suburb`).value = "";
                if(document.getElementById(`${name}_state`))
                    document.getElementById(`${name}_state`).value = "";
                if(document.getElementById(`${name}_postcode`))
                    document.getElementById(`${name}_postcode`).value = "";
                if(document.getElementById(`${name}_country`))
                    document.getElementById(`${name}_country`).value = "";

                if(document.getElementById(`${name}_longitude`))
                    document.getElementById(`${name}_longitude`).value = geometry.longitude;
                if(document.getElementById(`${name}_latitude`))
                    document.getElementById(`${name}_latitude`).value = geometry.latitude;

                address.forEach(item => {
                    let addressType = item.types[0];
                    // Update fields as needed on project.
                    switch (addressType) {
                        case "street_number":
                            if(document.getElementById(`${name}_address_1`))
                                document.getElementById(`${name}_address_1`).value = item['short_name'] + " ";
                            break;

                        case "premise":
                            if(document.getElementById(`${name}_address_1`))
                                document.getElementById(`${name}_address_1`).value = item['long_name'] + " ";
                            break;

                        case "route":
                            if(document.getElementById(`${name}_address_1`))
                                document.getElementById(`${name}_address_1`).value += item['long_name'] + " ";
                            break;

                        case "neighborhood":
                            if(document.getElementById(`${name}_address_2`))
                                document.getElementById(`${name}_address_2`).value += item['long_name'] + " ";
                            break;

                        case "sublocality_level_1":
                            if(document.getElementById(`${name}_address_2`))
                                document.getElementById(`${name}_address_2`).value += item['long_name'] + " ";
                            break;

                        case "locality":
                            if (address.length > 7 &&
                                address.length < 9 &&
                                address[6].long_name !== "Canada") {

                                if(document.getElementById(`${name}_address_2`))
                                    document.getElementById(`${name}_address_2`).value += item['long_name'] + " ";

                            } else {
                                if(document.getElementById(`${name}_suburb`))
                                    document.getElementById(`${name}_suburb`).value = item['long_name'] + " ";
                            }
                            break;

                        case "postal_town":
                            if(document.getElementById(`${name}_suburb`))
                                document.getElementById(`${name}_suburb`).value += item['long_name'];
                            break;

                        case "administrative_area_level_2":
                            if (address.length <= 7) {
                                if(document.getElementById(`${name}_state`))
                                    document.getElementById(`${name}_state`).value = item['long_name'] + " ";
                            } else{
                                if(document.getElementById(`${name}_state`))
                                document.getElementById(`${name}_state`).value = item['long_name'] + " ";
                            }
                            break;

                        case "administrative_area_level_1":
                            if (address.length < 8){
                                if(document.getElementById(`${name}_state`))
                                    document.getElementById(`${name}_state`).value = item['short_name'];                                    
                            }else{
                                if(document.getElementById(`${name}_suburb`))
                                    document.getElementById(`${name}_suburb`).value += item['short_name'];
                            }                                
                            break;

                        case "country":
                            if(document.getElementById(`${name}_country`))
                                document.getElementById(`${name}_country`).value = item['long_name'];
                            break;

                        case "postal_code":
                        case "postal_code_prefix":
                            if(document.getElementById(`${name}_postcode`))
                                document.getElementById(`${name}_postcode`).value = item['short_name'];
                            break;
                    }
                });
            }
        },
        events: {
            initGoogleAddressLookup: function () {
                let lookupFields = document.querySelectorAll('[address-lookup]');
                for(let i = 0; i < lookupFields.length; i++) {
                    searchAddressElement = lookupFields[i];
                    searchAddressElement.addEventListener('didLoad', 
                        this.initEventListeners(searchAddressElement));
                }
            },
            initEventListeners: function (field) {
                let name = field.getAttribute('name');
                let setStateInterval = setInterval(() => {
                    let lookupField = field.querySelector('input');
                    if (lookupField && google !== undefined) {
                        // Initialize google autocomplete on field
                        let searchAddressField = new google.maps.places.Autocomplete(lookupField);
                        // Set initial restrict to the listed countries
                        searchAddressField.setComponentRestrictions({ country: ["au"] });
                        // Fill address event
                        searchAddressField.addListener('place_changed', (event) => {
                            AddressLookup.methods.fillAddress(searchAddressField, name);
                        });
                        clearInterval(setStateInterval);
                    }
                }, 300);
                
            },
        }
    }
})(); 

// Initialize on window load
window.AddressLookup = AddressLookup;

// Set timeout, make sure INS components has been loaded
setTimeout(() => {
    AddressLookup.events.initGoogleAddressLookup();
}, 200);
