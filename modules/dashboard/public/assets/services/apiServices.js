var apiServices = (function () {
    const
        apiUrl = "/api",
        request = axios.create({});

    // Logging is disabled in production unless APP_DEBUG flag is explicitly set
    // This prevents console.error from appearing in production builds
    const enableLogging = typeof window !== 'undefined' && (window.APP_DEBUG === true || window.appDebug === true);

    let config = {
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-CSRF-TOKEN': document.querySelector('[name="csrf-token"]').content
        }
    };

    // Axios Processor
    async function processRequest(method, url, payload, headers = config.headers) {
        let endpoint = apiUrl + url;
        let process = method.toLowerCase() === 'get'
            ? request.get(endpoint, { headers })
            : request[method](endpoint, payload, { headers });

        return await process.then(response => {
            // Standardized response format: { state: boolean, data: object }
            if (response.data.errors) {
                if (typeof response.data.errors === "object" && !Object.keys(response.data.errors).length) {
                    return { state: true, data: response.data };
                } else {
                    if (enableLogging) {
                        console.error(`API Error: ${url}`, response.data.errors);
                    }
                    return { state: false, data: response.data };
                }
            }
            return { state: true, data: response.data };
        }).catch(error => {
            // Standardized error format: always return { state: false, data: object }
            let errorData = null;
            
            if (error.response) {
                // HTTP error response (4xx, 5xx)
                errorData = error.response.data || {};
                if (error.response.data && error.response.data.errors) {
                    if (enableLogging) {
                        console.error(`API Error: ${url}`, error.response.data.errors);
                    }
                }
            } else if (error.request) {
                // Network error (no response received)
                errorData = { 
                    errors: { 
                        network: ['Network error: Unable to reach server'] 
                    } 
                };
                if (enableLogging) {
                    console.error(`Network Error: ${url}`, error.message);
                }
            } else {
                // Request setup error
                errorData = { 
                    errors: { 
                        request: ['Request error: ' + error.message] 
                    } 
                };
                if (enableLogging) {
                    console.error(`Request Error: ${url}`, error.message);
                }
            }
            
            return { state: false, data: errorData };
        });
    }

    return {
        processRequest: processRequest
    }
})();