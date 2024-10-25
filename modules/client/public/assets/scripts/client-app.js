let ClientApp = (function () {
    return {
        // data manipulation
        data: {
            
        },
        // Validation functions
        validation: {

        },
        // Events 
        events: {

        },
        // Methods 
        methods: {
            buildURLLink(arg) {
                let paramStr = productList.methods.buildParamlist(arg);
                let cat = productList.methods.getCatParam(urlParams.getAll('cat'));
                let loc = productList.methods.getLocParam(urlParams.getAll('loc'));
                let country = urlParams.getAll('country');

                urlStr = pageBaseUrl + "?" + paramStr + cat;

                if (selectCatergory != '') {
                    urlStr = pageFirstPathUrl + '/' + selectCatergory + "?" + paramStr + cat;
                    if (selectCatergory == 'all') {
                        urlStr = pageFirstPathUrl + "?" + paramStr + cat;
                    }
                }

                if (arg != "loc") {
                    if (country != '') {
                        urlStr += "&country=" + country + loc;
                    }
                }

                return urlStr;
            },
            pageSizeValueSelected(event) {
                //Function for pagination page size selected event
                let tmpVal = event.detail;
                productFilter.per_page = tmpVal;

                window.location.href = productList.methods.buildURLLink("paging");
            },
        },
        // Initialize elements & event listeners
        init: {
            initInterface() {
                let pageSizeSelect = document.getElementById('page-size-select');
                if (pageSizeSelect) {
                    pageSizeSelect.addEventListener('insValueChange', productList.methods.pageSizeValueSelected);
                }
            }

        }
    }
})();


// Set timeout, make sure INS components has been loaded
setTimeout(() => {
    ClientApp.init.initInterface();
}, 200);