// Scroll to top
const scrollElement = document.getElementById('scroll-to-top-btn');
const scrollTopBtn = document.getElementById('scroll-to-top');

// Mobile Menu
const mobileMenuBtn = document.getElementById('mobile-menu-btn');
const mobileMenuDrawer = document.getElementById('mobile-menu');

let lastKnownScrollPosition = window.pageYOffset || document.body.scrollTop;
const mobileWindowWidthLimit = 1023;

// MAIN JS
let App = (function () {
    return {
        // data manipulation
        data: {
            formatDatePayload(date, format) {
                let formatted = "";
                if (date) {
                    let currentFormat = format || this.datetimeFormat;
                    let meridiem = moment(date, currentFormat).format('YYYY-MM-DD HH:mm');
                    formatted = moment(meridiem, 'YYYY-MM-DD HH:mm').utc().format('YYYY-MM-DD HH:mm');
                }
                return formatted;
            },
            setNow() {
                return this.formatDatePayload(moment().format('YYYY-MM-DD HH:mm'), 'YYYY-MM-DD HH:mm');
            },
            constructImage(file) {
                let imageRegex = /\(gif|jpg|jpeg|tiff|png\)$/i;
                let type = file.image.url.split(".");
                type = type[type.length - 1].split("?")[0];
                let filename = file.image.url.split("/")
                filename = filename[filename.length - 1];
                let data = {
                    id: file.id,
                    name: filename,
                    type: imageRegex.test(type) ? `image/${type}` : `application/${type}`,
                    url: file.image.url
                }
                return data;
            },
            stringifyBoolean(data) {
                let text = ""
                if (data === true || data === 'true') {
                    text = "Yes"
                } else if (data === false || data === 'false') {
                    text = "No"
                }
                return text;
            },
            capitalize(item) {
                return item.split("_").map((s) => s.charAt(0).toUpperCase() + s.substring(1)).join(' ');
            },
            convertToSnakeCase(name) {
                return name
                    ? InsitesUtil.removeWhitespace(name).trim().replace(/[ -]/g, "_").replace(/[^a-zA-Z0-9_]/g, "").toLowerCase()
                    : '';
            },
            convertToKebabCase(text) {
                let kebab = text
                    ? text.trim().replace(/[ ]/g, "-").replace(/[_]/g, "")
                    : '';
                return InsitesUtil.removeWhitespace(kebab);
            },
            getFillerHeight() {
                /* Get the width of the window to check if it will get the height of the filler for the mobile or desktop then return it. */
                let windowWidth = window.innerWidth;
                let fillerContainer = document.getElementById("head-filler");
                let fillerHeight = 0;
                //dashboardHeight includes the padding only
                if (windowWidth <= mobileWindowWidthLimit) {
                    fillerHeight = fillerContainer.getElementsByClassName("mobile")[0].clientHeight;
                } else {
                    fillerHeight = fillerContainer.getElementsByClassName("desktop")[0].clientHeight;
                }
                return fillerHeight;
            }
        },
        // Validation functions
        validation: {
            validateForm(containerEl) {
                for (let index = 0; index < containerEl.querySelectorAll('[validate]').length; index++) {
                    let field = containerEl.querySelectorAll('[validate]')[index];
                    let type = field.tagName.toLowerCase();
                    switch (type) {
                        case 'div':
                            if(field.getAttribute('data-ui') == 'list_checkbox')
                                this.validateChekbox(field);
                            else
                                this.validateRadio(field);
                            break;
                        case 'ins-input-file':
                            this.validateFile(field);
                            break;
                        case 'ins-input-tel':
                            this.validateTel(field);
                            break;
                        case 'ins-textarea':
                            this.validateInput(field.querySelector('textarea'));
                            break
                        case 'ins-input':
                        default:
                            field.field === 'email'
                                ? this.validateEmail(field)
                                : this.validateInput(field)
                            break;
                    }                    
                }
                return this.checkInvalidFields(containerEl);
            },
            checkRecaptcha() {
                let isValid = grecaptcha.getResponse().length == 0 
                    ? false : true;
                isValid
                
                    ? document.getElementById('recaptcha-v2-wrapper').classList.remove("error-recaptcha")
                    : document.getElementById('recaptcha-v2-wrapper').classList.add('error-recaptcha');
                return isValid;
                
            },
            checkInvalidFields(containerEl) {
                return new Promise(resolve => {
                    setTimeout(() => {
                        resolve(!containerEl.querySelectorAll('.is-invalid').length);
                    }, 200)
                });
            },
            validateTabs(tabEl) {
                for (let i = 0; i < tabEl.querySelectorAll('ins-tab-item').length; i++) {
                    let fields = tabEl.querySfieldelectorAll('ins-tab-item')[i];
                    fields.hasError = fields.querySelectorAll('.is-invalid').length ?
                        true :
                        false;
                }
                return !tabEl.querySelectorAll('.is-invalid').length;
            },
            async validateFile(field) {
                (await field.getFilesList()).length <= 0 ?
                    field.setAttribute('has-error', true) :
                    field.removeAttribute('has-error')
            },
            async validateTel(field) {
                (await field.getValues()).phone_number.length < 7 ?
                    field.setAttribute('has-error', true) :
                    field.removeAttribute('has-error')                                    
            },
            validateRadio(wrapper) {                
                wrapper.querySelectorAll('ins-radio input:checked').length ?
                    wrapper.classList.remove('is-invalid') :
                    wrapper.classList.add('is-invalid');
            },
            validateChekbox(wrapper) {                
                wrapper.querySelectorAll('ins-checkbox input:checked').length ?
                    wrapper.classList.remove('is-invalid') :
                    wrapper.classList.add('is-invalid');
            },            
            validateEmail(field) {
                let isEmail = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
                if (field.value) {
                    if (isEmail.test(String(field.value).toLowerCase()) === true) {
                        InsitesUtil.validFieldNotif(field);
                        return true;
                    } else {
                        InsitesUtil.invalidFieldNotif(field);
                        return false;
                    }
                }
                InsitesUtil.invalidFieldNotif(field);
                return false;
            },
            async validateInput(field) {                
                field = field.target ? field.target : field;
                if (!field.value) {
                    InsitesUtil.invalidFieldNotif(field);
                    return true;
                } else {
                    InsitesUtil.validFieldNotif(field);
                    return false;
                }
            }
        },
        // Events 
        events: {
            // App.events.notyf('error', "Error message here");
            // App.events.notyf('success', "Success message here");
            notyf(type, message) {
                new Notyf({
                    duration: 3000,
                    position: {
                        x: 'right',
                        y: 'top'
                    }
                })[type](message);
            },
            async swal(type = "warning", title, message, label = "OK", showCancel = true, iconConfirm = "icon-check-2") {
                let btnLabel = App.data.capitalize(label);
                return await new Promise(resolve => {
                    Swal.fire({
                        html: `
                        <ins-loader
                            icon="icon-close-1"
                            state-icon="${type}"
                            icon-color="${type}"
                            state-title="${title}"
                            state-message="${message}">
                        </ins-loader>`,
                        showCancelButton: showCancel,
                        customClass: {
                            confirmButton:
                                btnLabel.indexOf("Delete") >= 0 ||
                                    btnLabel.indexOf("Archive") >= 0 ||
                                    btnLabel.indexOf("Disable") >= 0 ||
                                    btnLabel.indexOf("Remove") >= 0
                                    ? "negative" : "",
                        },
                        confirmButtonText: `${btnLabel}`,
                        cancelButtonText: 'Cancel'
                    }).then(result => {
                        result.value
                            ? resolve(true)
                            : resolve(false);
                    });
                });
            },
            // Scroll to top show / hide buton
            initWindowOnScroll() {
                let vh = window.innerHeight + 100;
                window.onscroll = () => {
                    if (window.pageYOffset > vh) {
                        scrollElement.classList.add('visible');
                    } else {
                        scrollElement.classList.remove('visible');
                    }
                };
            },
            toggleDrawerMenu() {
                let state = !mobileMenuDrawer.isOpen ? true : false;
                mobileMenuDrawer.setDrawerState(state);
            },
            toggleMobileMenuBtnIcon() {
                let state = mobileMenuDrawer.isOpen ? true : false;
                let setIcon = state
                    ? 'icon-close-1'
                    : 'icon-menu-1';
                mobileMenuBtn.removeAttribute('class');
                mobileMenuBtn.classList.add(setIcon);
            },
            checkScrollStatus(scrollPosition) {
                let mainHeader = document.getElementById('main-header');
                let fillerGuide = App.data.getFillerHeight();
                // Check if guide is breached before initiating animation
                if (scrollPosition > fillerGuide) {
                    if (scrollPosition <= lastKnownScrollPosition) {
                        //show Menu
                        mainHeader.style.transform = "translate3d(0px, 0px, 0px)";
                    } else {
                        //hide Menu
                        mainHeader.style.transform = "translate3d(0px, -162px, 0px)";
                    }
                } else {
                    //If less than the Guide put back Header to initial looks
                    mainHeader.style.transform = "translate3d(0px, 0px, 0px)";
                }
                lastKnownScrollPosition = scrollPosition;
            }
        },
        // Initialize elements & event listeners
        init: {
            // Scroll to top event
            initScrollToTopBtn() {
                if (scrollTopBtn) {
                    App.events.initWindowOnScroll();

                    scrollTopBtn.addEventListener('click', () => {
                        window.scrollTo({
                            top: 0,
                            behavior: 'smooth'
                        });
                    });
                }
            },
            // Mobile Menu
            initMobileMenu() {
                if (mobileMenuBtn && mobileMenuDrawer) {
                    mobileMenuBtn.addEventListener('click', () => {
                        App.events.toggleDrawerMenu();
                    });
                    mobileMenuDrawer.addEventListener('insToggle', () => {
                        App.events.toggleMobileMenuBtnIcon();
                    });
                }
            },
            // Scrolling Event for Menu
            initScrollMenu() {
                let mainHeader = document.getElementById('main-header');
                let ticking = false;

                if (mainHeader) {
                    document.addEventListener('scroll', function (e) {
                        //this is done to avoid throtling the function too much
                        if (!ticking) {
                            window.requestAnimationFrame(function () {
                                App.events.checkScrollStatus(window.scrollY);
                                ticking = false;
                            });
                            ticking = true;
                        }
                    });
                }
            }

        }
    }
})();

// Initialize javascript on load
window.App = App;

// Set timeout, make sure INS components has been loaded
setTimeout(() => {
    App.init.initScrollToTopBtn();
    App.init.initMobileMenu();
    App.init.initScrollMenu();
}, 200);