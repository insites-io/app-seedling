// Contact Us Form
const formEl = document.getElementById('contact-us-form');
const formSubmitBtn = document.getElementById('submit-btn-contact-us');
const insFileUploaderEl = document.getElementById('document-input');
const documentFieldEl = document.getElementById('document');
const s3CredentialsURL = `${window.location.origin}/api/s3-contact-us.json`;
const phoneFields = {
    inputTel: document.getElementById('phone-number-field'),
    mobile_phone: document.getElementById('mobile_phone'),
    country_code: document.getElementById('country_code')
}

const contactUsFields = {
    first_name: document.getElementById("first-name"),
    last_name: document.getElementById("last-name"),
    email: document.getElementById("email"),
    message: document.getElementById("message"),
    
}

let uuidList = [];

// Google Map phoneFields
// Div element to set Google Map display
const mapEl = document.getElementById('contact-google-map');

// Map center address
// let address = document.getElementById('full-address').innerText;
// GeoJSON feature not yet supported on INS global contents / data
let addressData = document.getElementById('address-data');
addressData = addressData ? JSON.parse(addressData) : null;
// GeoJSON area indicator styling on map
let polyOptions = {
    strokeColor: "#1E86E3",
    fillColor: "#1E86E3",
    strokeOpacity: 1,
    strokeWeight: 3,
    fillOpacity: 0.35
}
/**
 * To change or apply your own map style, simply change the value of 
 * variable 'mapStyle' below to your prefered JSON styling.
 * 
 * References:
 * Google Detailed Guide: https://developers.google.com/maps/documentation/javascript/styling
 * Google map template styles: https://snazzymaps.com/ (or get from designer / PM)
 * */
let mapStyle = InsitesUtil.getTheme();

/** 
 * Contact Us - Scripts / Functions
 * */
let ContactUs = (function () {
    return {
        methods: {
            async submitForm() {
                // Submit form via API axios -> Create pOS Model
                let response = await FormServices.createContactUs({ 'payload': payload });
                if (response.state && response.data.items) {
                    // model has been created
                    this.successHandler();
                } else {
                    // API error: failed to submit form
                    this.errorHandler();
                }
            },
            successHandler() {
                window.location.href = `/thank-you`;
            },
            errorHandler() {
                formEl.querySelector('ins-button').loading = false;
                App.events.swal('error',
                    'API Error',
                    'Failed to send form enquiry. Please refresh and try again.',
                    'OK',
                    false);
            },
            async validateForm(event) {
                event ? event.preventDefault() : '';
                var captcha = true;
                // IF your form / instance have recaptcha enabled, uncommment this code instead
                var captcha = App.validation.checkRecaptcha();

                let values = await phoneFields.inputTel.getValues();
                phoneFields.country_code.value = values.country_code;
                phoneFields.mobile_phone.value = "+" + values.country_code + values.phone_number;

                validateXSS();

                // Form fields with attribute 'validate' are validated
                if (await App.validation.validateForm(formEl) && captcha) {
                    formEl.querySelector('ins-button').loading = true;
                    await this.processAttachments();
                    formEl.submit();
                } else {
                    return false;
                }
            },
            async processAttachments() {
                var testarr = [];
                if (insFileUploaderEl) {
                    let filesToUpload = await insFileUploaderEl.getFilesList().then(result => {
                        return result;
                    });
                    for (let index = 0; index < filesToUpload.length; index++) {
                        /*  This specific case only uploads 1 file, and return the uploaded S3 URL to the field in the form
                            Code implementation may change if your uploading multiple files / images at a time,
                            and assigning it to different fields, etc..
                        */
                        let s3URL = await this.uploadFile(filesToUpload[index]);
                        // assign to pOS hidden field s3 URL
                        //documentFieldEl.value = s3URL;
                        testarr.push(s3URL);
                    }
                    documentFieldEl.value = testarr;
                }
            },
            async uploadFile(file) {

                return new Promise(async resolve => {
                    uuidList = [];
                    const paths = [];

                    let fileUrl = "";
                    if (file.upload_url) {
                        fileUrl = file.upload_url;
                    } else {
                        // if file has not dataURL yet
                        if (!file.dataURL) {
                            file.dataURL = await S3UploaderService.methods.convertFileToBase64(file);
                        }
                        // pass 'document' as it is the pOS field name
                        // pass 'media' depending on pOS field type
                        const uploads3 = await S3UploaderService.methods.uploadToS3(
                          "/api/attachments/s3-form?name=modules/insites_core/attachment&field=file", 
                          file,
                          file.name,
                          "file",
                          true
                        );

                        documentFieldEl.value = uploadS3;
                        
                        const response = await this.createDatabaseFile(uploads3);
                        
                        if (response.state) {
                            const url = response.data.item.file.url;
                            const path = url.split('/property_uploads/')[1];
                            paths.push(path);
                            uuidList.push(response.data.item.uuid)
                        }
                    }
                    resolve(uuidList);
                });
            },
            async createDatabaseFile(data) {
              const URL = decodeURIComponent((data+'').replace(/\+/g, '%20'));

              return await FormServices.createAttachmentfile({
                  path: URL.split('/property_uploads/')[1],
                  url: data
              });
            },
            mapGetCoordinates(geocoder, map) {
                if (address.trim() !== '') {
                    geocoder.geocode({ 'address': address },
                        (results, status) => {
                            if (status === 'OK') {
                                map.setCenter(results[0].geometry.location);
                                let marker = new google.maps.Marker({
                                    map,
                                    position: results[0].geometry.location
                                });
                            } else {
                                console.error('Geocode was not successful for the following reason: ' + status);
                            }
                        });
                }
            },
            constructMarker(map) {
                if (!addressData.properties.geojson) return;
                let geojson = addressData.properties.geojson;
                let center, type = geojson.type.toLowerCase();
                polyOptions.map = map;

                if (type === "point") {
                    this.newMarker(geojson.coordinates, map);
                    center = this.mapLngLat(geojson.coordinates);

                } else if (type === "multipoint") {
                    geojson.coordinates.forEach(item => this.newMarker(item, map));
                    center = {
                        lng: geojson.coordinates[0][0],
                        lat: geojson.coordinates[0][1]
                    }

                    if (geojson.coordinates.length > 1)
                        this.setMapBounds(map, geojson.coordinates);

                } else if (type === "linestring") {
                    center = this.mapLngLat(geojson.coordinates[0]);
                    polyOptions.path = geojson.coordinates.map(this.mapLngLat)
                    new google.maps.Polyline(polyOptions);

                } else if (type === "polygon") {
                    center = this.mapLngLat(geojson.coordinates[0][0]);
                    polyOptions.paths = geojson.coordinates[0].map(this.mapLngLat)
                    new google.maps.Polygon(polyOptions);
                }

                map.setCenter(center);
            },
            newMarker(lnglat, map) {
                let position = this.mapLngLat(lnglat);
                let marker = new google.maps.Marker({ map, position })
                let infowindow = new google.maps.InfoWindow();
                google.maps.event.addListener(marker, "click", () => {
                    infowindow.setContent(this.constructContent(position));
                    infowindow.open(map, marker);
                });
                return marker;
            },
            mapLngLat(lnglat) {
                return { lng: lnglat[0], lat: lnglat[1] }
            },
            setMapBounds(map, markers) {
                let latlngbounds = new google.maps.LatLngBounds();
                markers.forEach(item => {
                    let latlng = new google.maps.LatLng(item[1], item[0]);
                    latlngbounds.extend(latlng);
                });
                map.fitBounds(latlngbounds);
            }
        },
        init: {
            /** 
             * Not Used: Set or customize other properties and functionalities of Google Map
             * Left here as sample should it needs to be reincorporated.
             * */
            initGoogleMap() {
                // default map center (Sydney, Australia)
                let defaultCenter = new google.maps.LatLng(-33.8671868, 151.2049769);
                let geocoder = new google.maps.Geocoder();

                let map = new google.maps.Map(mapEl, {
                    center: defaultCenter,
                    scrollwheel: false,
                    draggable: true,
                    disableDoubleClickZoom: true,
                    zoomControll: false,
                    streetViewControl: false,
                    gestureHandling: 'cooperative',
                    zoom: 15,
                    styles: mapStyle
                });

                if (addressData && addressData.properties.use_geojson) {
                    // GeoJSON feature not yet supported on INS global contents / data
                    ContactUs.methods.constructMarker(map);
                } else {
                    this.directionsURL = `https://www.google.com/maps/search/${address.fullAddress}`;
                    ContactUs.methods.mapGetCoordinates(geocoder, map);
                }
            }
        },
    }
})();

// Validate XSS
function validateXSS() {
    contactUsFields.first_name.value = escapeHTML(contactUsFields.first_name.value);
    contactUsFields.last_name.value = escapeHTML(contactUsFields.last_name.value);
    contactUsFields.email.value = escapeHTML(contactUsFields.email.value);
    contactUsFields.message.value = escapeHTML(contactUsFields.message.value);

    return true;
}

function escapeHTML(text) {
    var map = {
        '&': '',
        '<': '',
        '>': '',
        '"': ''
    };

    return text.replace(/[&<>"]/g, function (m) { return map[m]; });
}

// Function to validate the input
function validateInput(event) {
    var key = event.keyCode || event.which;
    var keyChar = String.fromCharCode(key);
    var allowedChars = /^[a-zA-Z0-9\s'-]+$/;

    // Check if the pressed key is allowed or not
    if (!allowedChars.test(keyChar)) {
        event.preventDefault();
        return false;
    }
}

// Function to handle paste event
function handlePaste(event) {
    var clipboardData = event.clipboardData || window.clipboardData;
    var pastedData = clipboardData.getData('text');
    var allowedChars = /^[a-zA-Z0-9\s'-]+$/;

    // Check if the pasted data contains any disallowed characters
    if (!allowedChars.test(pastedData)) {
        event.preventDefault();
        return false;
    }
}

//if (google) {
    //ContactUs.init.initGoogleMap();
//}