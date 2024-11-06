//Initial references
const input = document.querySelectorAll(".otp_input");
const inputField = document.querySelector(".otp_input_fields");
const otpInput = document.querySelector("input[name='2fa[otp_code]']");
const submitButton = document.getElementById("submit_button");
console.log(submitButton)
const setupCode = document.getElementById("setup_code");
const copyButton = document.querySelector(".copy-btn")
let inputCount = 0,
finalInput = "";

//Update input
const updateInputConfig = (element, disabledStatus) => {
    element.disabled = disabledStatus;
    if (!disabledStatus) {
      element.focus();
    } else {
      element.blur();
    }
  };
input.forEach((element) => {
    const optInputs = [...inputField.children];
    const len = optInputs.length;

    element.addEventListener("keyup", (e) => {
        if (e.key == "Backspace") {
            finalInput = finalInput.substring(0, finalInput.length - 1);
            if (inputCount == 0) {
                return false;
            }
            inputCount -= 1;
        }else {
            if (inputCount <= 5 && e.key != "Backspace") {
                finalInput += e.key;
            }
            inputCount += 1;
        }
        submitButton.classList.add("hide");
    });

    element.addEventListener("input", (ev) => {
        const elInp = ev.currentTarget;
        const i = optInputs.indexOf(elInp);
        if (elInp.value && (i+1) % len) {
            optInputs[i + 1].disabled = false;
            optInputs[i + 1].focus();
        }
    });

    element.addEventListener("paste", (ev) => {
        const clip = ev.clipboardData.getData('text');
        const pin = clip.replace(/\s/g, "");
        const ch = [...pin];

        optInputs.forEach((el, i) => el.value = ch[i] || "");
        if(pin.length <= 6) {
            optInputs[pin.length - 1].disabled = false;
            optInputs[pin.length - 1].focus();
            inputCount += (pin.length - 1);
        }else {
            optInputs[5].disabled = false;
            optInputs[5].focus();
            inputCount  = 6;
        }
    });

    element.addEventListener("keydown", (ev) => {
        const elInp = ev.currentTarget;
        const i = optInputs.indexOf(elInp);
        if (!elInp.value && ev.key === "Backspace" && i){
            optInputs[i].disabled = true;
            optInputs[i - 1].disabled = false;
            optInputs[i - 1].focus();
        }
    });
});

window.addEventListener("keyup", (e) => {
    if (inputCount > 5) {
        submitButton.classList.remove("hide");
        if (e.key == "Backspace") {
            finalInput = finalInput.substring(0, finalInput.length - 1);
            inputField.lastElementChild.value = "";
            inputCount -= 1;
            submitButton.classList.add("hide");
        }
        otpInput.value = finalInput;
    }
});

const copyToClipboardHandler = () => {
    const text = setupCode.innerHTML;
    if (navigator.clipboard) {
        // default: modern asynchronous API
        navigator.clipboard.writeText(text);
    } else if (window.clipboardData && window.clipboardData.setData) {
        // for IE11
        window.clipboardData.setData("Text", text);
        Promise.resolve();
    } else {
        // workaround: create dummy input
        const input = document.createElement("input", { type: "text" });
        input.setAttribute("type", "text");
        input.value = text;
        document.body.append(input);
        input.focus();
        input.select();
        document.execCommand("copy");
        input.remove();
        Promise.resolve();
    }
    copyButton.classList.add("active");
    setTimeout(() => {
        copyButton.classList.remove("active");
    }, 1200);
};
const manualCodeWrap = document.querySelector(".manual-code-wrap");


//Start
const startInput = () => {
    inputCount = 0;
    finalInput = "";
    input.forEach(function (element, i) {
        element.value = "";
        if(i == 0) {
            input[i].disabled = false;
            input[i].focus();
        }
    });

    if(manualCodeWrap) {
        manualCodeWrap.addEventListener("click", copyToClipboardHandler);
    }

    if(submitButton) {
        submitButton.addEventListener('insClick', event => {
            submitButton.loading = true;
        });
    }
};

window.onload = startInput();