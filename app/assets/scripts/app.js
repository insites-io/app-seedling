/**
 * Scripts every page loads (from the footer, once per page): field checks shared by the
 * forms, toast messages, the mobile menu, and the header that hides while you scroll down.
 */
let App = (function () {
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const mobileMenuDrawer = document.getElementById('mobile-menu');
    let lastKnownScrollPosition = window.pageYOffset || document.body.scrollTop;

    return {
        // Field checks. Each marks the field valid or invalid through InsitesUtil.
        validation: {
            validateForm(containerEl) {
                containerEl.querySelectorAll('[validate]').forEach(field => {
                    switch (field.tagName.toLowerCase()) {
                        case 'div':
                            if (field.getAttribute('data-ui') == 'list_checkbox') {
                                this.validateCheckbox(field);
                            } else {
                                this.validateRadio(field);
                            }
                            break;
                        case 'ins-input-file':
                            this.validateFile(field);
                            break;
                        case 'ins-input-tel':
                            this.validateTel(field);
                            break;
                        case 'ins-textarea':
                            this.validateInput(field.querySelector('textarea'));
                            break;
                        case 'ins-input':
                        default:
                            field.field === 'email'
                                ? this.validateEmail(field)
                                : this.validateInput(field);
                            break;
                    }
                });
                return this.checkInvalidFields(containerEl);
            },
            // Waits for the components to show their state, then reports whether any field is invalid
            checkInvalidFields(containerEl) {
                return new Promise(resolve => {
                    setTimeout(() => {
                        resolve(!containerEl.querySelectorAll('.is-invalid').length);
                    }, 200);
                });
            },
            async validateFile(field) {
                (await field.getFilesList()).length <= 0
                    ? field.setAttribute('has-error', true)
                    : field.removeAttribute('has-error');
            },
            async validateTel(field) {
                (await field.getValues()).phone_number.length < 7
                    ? field.setAttribute('has-error', true)
                    : field.removeAttribute('has-error');
            },
            validateRadio(wrapper) {
                wrapper.querySelectorAll('ins-radio input:checked').length
                    ? wrapper.classList.remove('is-invalid')
                    : wrapper.classList.add('is-invalid');
            },
            validateCheckbox(wrapper) {
                wrapper.querySelectorAll('ins-checkbox input:checked').length
                    ? wrapper.classList.remove('is-invalid')
                    : wrapper.classList.add('is-invalid');
            },
            validateEmail(field) {
                const isEmail = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
                if (field.value && isEmail.test(String(field.value).toLowerCase())) {
                    InsitesUtil.validFieldNotif(field);
                    return true;
                }
                InsitesUtil.invalidFieldNotif(field);
                return false;
            },
            validateInput(field) {
                field = field.target ? field.target : field;
                if (!field.value) {
                    InsitesUtil.invalidFieldNotif(field);
                    return false;
                }
                InsitesUtil.validFieldNotif(field);
                return true;
            }
        },
        events: {
            // App.events.notyf('success', "Saved"); App.events.notyf('error', "Not saved");
            notyf(type, message) {
                new Notyf({
                    duration: 3000,
                    position: { x: 'right', y: 'top' }
                })[type](message);
            },
            toggleDrawerMenu() {
                mobileMenuDrawer.setDrawerState(!mobileMenuDrawer.isOpen);
            },
            toggleMobileMenuBtnIcon() {
                mobileMenuBtn.removeAttribute('class');
                mobileMenuBtn.classList.add(mobileMenuDrawer.isOpen ? 'icon-close-1' : 'icon-menu-1');
            },
            // Hides the header while scrolling down and shows it again when scrolling up
            checkScrollStatus(mainHeader, scrollPosition) {
                if (scrollPosition > mainHeader.offsetHeight && scrollPosition > lastKnownScrollPosition) {
                    mainHeader.style.transform = "translate3d(0px, -162px, 0px)";
                } else {
                    mainHeader.style.transform = "translate3d(0px, 0px, 0px)";
                }
                lastKnownScrollPosition = scrollPosition;
            }
        },
        init: {
            initMobileMenu() {
                if (mobileMenuBtn && mobileMenuDrawer) {
                    mobileMenuBtn.addEventListener('click', () => App.events.toggleDrawerMenu());
                    mobileMenuDrawer.addEventListener('insToggle', () => App.events.toggleMobileMenuBtnIcon());
                }
            },
            initScrollMenu() {
                const mainHeader = document.getElementById('main-header');
                let ticking = false;
                if (mainHeader) {
                    document.addEventListener('scroll', () => {
                        // At most one update per frame
                        if (!ticking) {
                            window.requestAnimationFrame(() => {
                                App.events.checkScrollStatus(mainHeader, window.scrollY);
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

window.App = App;

// Give the Insites components a moment to load first
setTimeout(() => {
    App.init.initMobileMenu();
    App.init.initScrollMenu();
}, 200);
