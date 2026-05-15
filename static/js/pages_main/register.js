(() => {
    const form = document.getElementById("register-form");
    if (!form || !window.FormUtils) {
        return;
    }

    const passwordInput = form.querySelector("#id_password");
    const confirmInput = form.querySelector("#id_password_confirm");
    const actionInput = form.querySelector("[data-register-action]");

    if (!passwordInput || !confirmInput) {
        return;
    }

    const requiredFields = [
        {
            input: form.querySelector("#id_last_name"),
            emptyMessage: "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u0444\u0430\u043c\u0438\u043b\u0438\u044e.",
            validate: (value) => window.FormUtils.getNameErrors(value, "\u0424\u0430\u043c\u0438\u043b\u0438\u044f"),
        },
        {
            input: form.querySelector("#id_first_name"),
            emptyMessage: "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u0438\u043c\u044f.",
            validate: (value) => window.FormUtils.getNameErrors(value, "\u0418\u043c\u044f"),
        },
        {
            input: form.querySelector("#id_email"),
            emptyMessage: "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043f\u043e\u0447\u0442\u0443.",
            validate: window.FormUtils.getEmailErrors,
        },
    ].filter((item) => item.input);

    const optionalFields = [
        {
            input: form.querySelector("#id_middle_name"),
            required: false,
            validate: (value) => window.FormUtils.getNameErrors(value, "\u041e\u0442\u0447\u0435\u0441\u0442\u0432\u043e"),
        },
        {
            input: form.querySelector("#id_phone"),
            required: false,
            validate: window.FormUtils.getPhoneErrors,
        },
    ].filter((item) => item.input);

    const agreementFields = [
        {
            input: form.querySelector("#id_accept_terms"),
            emptyMessage: "Необходимо принять условия Пользовательского соглашения.",
        },
        {
            input: form.querySelector("#id_accept_privacy"),
            emptyMessage: "Необходимо согласиться на обработку персональных данных.",
        },
    ].filter((item) => item.input);

    const passwordWrapper = window.FormUtils.getFieldWrapper(passwordInput);
    const passwordRules = Array.from(form.querySelectorAll("#password-rules [data-rule]"));
    const passwordChecks = {
        length: (value) => value.length >= 8,
        lower: (value) => /[a-z\u0430-\u044f\u0451]/.test(value),
        upper: (value) => /[A-Z\u0410-\u042f\u0401]/.test(value),
        digit: (value) => /\d/.test(value),
        special: (value) => /[^A-Za-z0-9\u0410-\u042f\u0430-\u044f\u0401\u0451]/.test(value),
    };

    function setPasswordErrorState(isInvalid) {
        const errorList = passwordWrapper.querySelector(".errorlist");
        if (errorList) {
            errorList.remove();
        }
        passwordWrapper.classList.toggle("has-error", isInvalid);
    }

    function updatePasswordRules(options = {}) {
        const { forceInvalid = false, highlightEmpty = false } = options;
        const value = passwordInput.value;
        const shouldHighlightMissing = value.length > 0 || highlightEmpty;
        let isEveryRuleValid = true;

        passwordRules.forEach((rule) => {
            const check = passwordChecks[rule.dataset.rule];
            const isValid = !forceInvalid && check ? check(value) : false;
            rule.classList.toggle("is-valid", isValid);
            rule.classList.toggle("is-invalid", shouldHighlightMissing && !isValid);
            if (!isValid) {
                isEveryRuleValid = false;
            }
        });

        return isEveryRuleValid;
    }

    function validatePassword(options = {}) {
        const { highlightEmpty = false } = options;
        const value = passwordInput.value;

        if (!value.trim()) {
            updatePasswordRules({ forceInvalid: highlightEmpty, highlightEmpty });
            setPasswordErrorState(highlightEmpty);
            return false;
        }

        const isEveryRuleValid = updatePasswordRules();
        setPasswordErrorState(!isEveryRuleValid);
        return isEveryRuleValid;
    }

    function validatePasswordConfirm(options = {}) {
        const { showMismatch = false } = options;
        const confirmValue = confirmInput.value.trim();

        if (!confirmValue) {
            window.FormUtils.setErrors(confirmInput, ["\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435 \u043f\u0430\u0440\u043e\u043b\u044c."]);
            return false;
        }

        if (passwordInput.value !== confirmInput.value) {
            if (showMismatch) {
                window.FormUtils.setErrors(confirmInput, ["\u041f\u0430\u0440\u043e\u043b\u0438 \u043d\u0435 \u0441\u043e\u0432\u043f\u0430\u0434\u0430\u044e\u0442."]);
            } else {
                window.FormUtils.clearErrors(confirmInput);
            }
            return false;
        }

        window.FormUtils.clearErrors(confirmInput);
        return true;
    }

    window.FormUtils.bindRealtimeValidation(requiredFields);
    window.FormUtils.bindRealtimeValidation(optionalFields);
    window.FormUtils.bindRealtimeValidation(agreementFields);
    updatePasswordRules();

    let hasPasswordChanged = false;
    let hasConfirmChanged = false;
    const notificationScrollKey = "registerNotificationScrollY";

    passwordInput.addEventListener("input", () => {
        hasPasswordChanged = true;
        validatePassword({ highlightEmpty: true });
        if (hasConfirmChanged || window.FormUtils.getFieldWrapper(confirmInput).classList.contains("has-error")) {
            validatePasswordConfirm();
        }
    });
    passwordInput.addEventListener("blur", () => {
        if (hasPasswordChanged) {
            validatePassword({ highlightEmpty: true });
        }
    });
    confirmInput.addEventListener("input", () => {
        hasConfirmChanged = true;
        validatePasswordConfirm();
    });
    confirmInput.addEventListener("blur", () => {
        if (hasConfirmChanged) {
            validatePasswordConfirm();
        }
    });

    form.addEventListener("submit", (event) => {
        hasPasswordChanged = true;
        hasConfirmChanged = true;
        const areRequiredFieldsValid = window.FormUtils.validateFields(requiredFields);
        const areOptionalFieldsValid = window.FormUtils.validateFields(optionalFields);
        const areAgreementFieldsValid = window.FormUtils.validateFields(agreementFields);
        const isPasswordValid = validatePassword({ highlightEmpty: true });
        const isPasswordConfirmValid = validatePasswordConfirm({ showMismatch: true });

        if (!areRequiredFieldsValid || !areOptionalFieldsValid || !areAgreementFieldsValid || !isPasswordValid || !isPasswordConfirmValid) {
            event.preventDefault();
            if (form.querySelector(".form-field.has-error")) {
                window.FormUtils.focusFirstInvalidField(form);
            } else if (!isPasswordValid) {
                passwordInput.scrollIntoView({
                    behavior: "smooth",
                    block: "center",
                });
                passwordInput.focus({ preventScroll: true });
            }
        } else {
            window.sessionStorage.setItem(notificationScrollKey, String(window.scrollY));
        }
    });

    Array.from(form.querySelectorAll("input, select, textarea")).forEach((input) => {
        if (input.type === "hidden") {
            return;
        }

        input.addEventListener("input", () => {
            if (actionInput) {
                actionInput.value = "start_registration";
            }
        });
        input.addEventListener("change", () => {
            if (actionInput) {
                actionInput.value = "start_registration";
            }
        });
    });

    const codeForm = document.getElementById("registration-code-form");
    const codeModal = document.querySelector("[data-registration-code-modal]");
    if (codeForm) {
        const codeInput = codeForm.querySelector("#id_code");
        const backButton = codeForm.querySelector("[data-registration-code-back]");
        const codeFields = [
            {
                input: codeInput,
                emptyMessage: "Введите код подтверждения.",
                validate: (value) => /^\d{6}$/.test(value) ? [] : ["Введите 6 цифр из письма."],
            },
        ].filter((item) => item.input);

        window.FormUtils.bindRealtimeValidation(codeFields);

        if (codeInput) {
            codeInput.addEventListener("input", () => {
                codeInput.value = codeInput.value.replace(/\D/g, "").slice(0, 6);
            });
            if (codeModal && codeModal.classList.contains("is-open")) {
                codeInput.focus();
            }
        }

        codeForm.addEventListener("submit", (event) => {
            if (!window.FormUtils.validateFields(codeFields)) {
                event.preventDefault();
                window.FormUtils.focusFirstInvalidField(codeForm);
            }
        });

        if (backButton && codeModal) {
            backButton.addEventListener("click", () => {
                codeModal.classList.remove("is-open");
                if (actionInput && form.dataset.hasPendingRegistration === "true") {
                    actionInput.value = "resend_registration_code";
                }
                if (codeInput) {
                    codeInput.value = "";
                    window.FormUtils.clearErrors(codeInput);
                }
            });
        }
    }

    const notification = document.querySelector("[data-auth-notification]");
    if (notification) {
        if (notification.hasAttribute("data-auth-notification-preserve-scroll")) {
            const savedScrollY = Number(window.sessionStorage.getItem(notificationScrollKey));
            if (Number.isFinite(savedScrollY)) {
                window.requestAnimationFrame(() => {
                    window.scrollTo(0, savedScrollY);
                });
            }
        } else {
            window.sessionStorage.removeItem(notificationScrollKey);
        }

        const notificationClose = notification.querySelector("[data-auth-notification-close]");
        if (notificationClose) {
            notificationClose.addEventListener("click", () => {
                notification.classList.add("is-hiding");
                notification.addEventListener("transitionend", () => {
                    notification.remove();
                    window.sessionStorage.removeItem(notificationScrollKey);
                }, { once: true });
            });
        }
    } else {
        window.sessionStorage.removeItem(notificationScrollKey);
    }
})();
