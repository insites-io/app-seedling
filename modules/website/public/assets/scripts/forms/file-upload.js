// Set these variables on form page
 let insFileUploaderEl = document.getElementById('document-input');
  let documentFieldEl = document.getElementById('document');
// let table = "modules/client/questionnaires";
 let property = "attach_documents";
let s3CredentialsURL = `${window.location.origin}/api/s3-upload?table=${table}&property=${property}`;


let FileUpload = (function () {
    return {
        methods: {
            async processAttachments() {
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
                        documentFieldEl.value = s3URL;
                    }
                }
            },
            async uploadFile(file) {
                return new Promise(async resolve => {
                    let fileUrl = "";
                    if (file.url) {
                        fileUrl = file.url; //upload_url
                    } else {
                        // if file has not dataURL yet
                        if (!file.dataURL) {
                            file.dataURL = await S3UploaderService.methods.convertFileToBase64(file);
                        }
                        // pass 'document' as it is the pOS field name
                        // pass 'media' depending on pOS field type
                        fileUrl = await S3UploaderService.methods.uploadToS3(s3CredentialsURL, file, file.name);
                    }
                    resolve(fileUrl);
                });
            }
        }
    }
})();