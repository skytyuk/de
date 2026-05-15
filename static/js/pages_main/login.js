(() => {
    const form = document.getElementById("login-form");
    if (!form || !window.FormUtils) {
        return;
    }

    const requiredFields = [
        {
            input: form.querySelector("#id_email"),
            emptyMessage: "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043f\u043e\u0447\u0442\u0443.",
            validate: window.FormUtils.getEmailErrors,
        },
        {
            input: form.querySelector("#id_password"),
            emptyMessage: "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043f\u0430\u0440\u043e\u043b\u044c.",
        },
    ].filter((item) => item.input);

    window.FormUtils.bindRealtimeValidation(requiredFields);

    const credentialsError = form.querySelector("[data-login-credentials-error]");
    function clearCredentialsError() {
        if (!credentialsError || !credentialsError.isConnected) {
            return;
        }

        credentialsError.remove();
        requiredFields.forEach(({ input }) => {
            window.FormUtils.clearErrors(input);
        });
    }

    if (credentialsError) {
        requiredFields.forEach((fieldConfig) => {
            fieldConfig.input.addEventListener("focus", () => {
                clearCredentialsError();
            }, { once: true });
        });
    }

    form.addEventListener("submit", (event) => {
        clearCredentialsError();
        const isValid = window.FormUtils.validateFields(requiredFields);
        if (!isValid) {
            event.preventDefault();
            window.FormUtils.focusFirstInvalidField(form);
        }
    });
})();
