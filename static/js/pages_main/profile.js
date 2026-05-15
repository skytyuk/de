(() => {
    const profileForm = document.getElementById("profile-form");
    const passwordForm = document.getElementById("password-form");
    let resetPasswordModalErrors = () => {};

    if (profileForm && window.FormUtils) {
        const saveButton = document.querySelector('button[form="profile-form"][type="submit"]');
        const requiredFields = [
            {
                input: profileForm.querySelector("#id_last_name"),
                emptyMessage: "Введите фамилию.",
                validate: (value) => window.FormUtils.getNameErrors(value, "Фамилия"),
            },
            {
                input: profileForm.querySelector("#id_first_name"),
                emptyMessage: "Введите имя.",
                validate: (value) => window.FormUtils.getNameErrors(value, "Имя"),
            },
            {
                input: profileForm.querySelector("#id_email"),
                emptyMessage: "Введите почту.",
                validate: window.FormUtils.getEmailErrors,
            },
        ].filter((item) => item.input);

        const optionalFields = [
            {
                input: profileForm.querySelector("#id_middle_name"),
                required: false,
                validate: (value) => window.FormUtils.getNameErrors(value, "Отчество"),
            },
            {
                input: profileForm.querySelector("#id_phone"),
                required: false,
                validate: window.FormUtils.getPhoneErrors,
            },
        ].filter((item) => item.input);

        const trackedInputs = Array.from(
            profileForm.querySelectorAll("input, select, textarea"),
        ).filter((input) => input.type !== "hidden" && input.type !== "submit" && input.type !== "button");
        const initialValues = new Map(
            trackedInputs.map((input) => [
                input,
                input.type === "file" ? "" : input.value,
            ]),
        );

        function hasProfileChanges() {
            return trackedInputs.some((input) => {
                if (input.type === "file") {
                    return input.files && input.files.length > 0;
                }

                return input.value !== initialValues.get(input);
            });
        }

        function isProfileValid() {
            const fields = [...requiredFields, ...optionalFields];
            return fields.every((fieldConfig) => {
                const { input, required = true, validate } = fieldConfig;
                const value = input.value.trim();
                const hasVisibleError = window.FormUtils.getFieldWrapper(input).classList.contains("has-error");

                if (hasVisibleError) {
                    return false;
                }

                if (required && !value) {
                    return false;
                }

                if (!required && !value) {
                    return true;
                }

                return !validate || validate(value).length === 0;
            });
        }

        function updateSaveButtonState() {
            if (!saveButton) {
                return;
            }

            saveButton.disabled = !hasProfileChanges() || !isProfileValid();
        }

        window.FormUtils.bindRealtimeValidation(requiredFields);
        window.FormUtils.bindRealtimeValidation(optionalFields);
        updateSaveButtonState();

        trackedInputs.forEach((input) => {
            input.addEventListener("input", updateSaveButtonState);
            input.addEventListener("change", updateSaveButtonState);
        });

        profileForm.addEventListener("submit", (event) => {
            const areRequiredFieldsValid = window.FormUtils.validateFields(requiredFields);
            const areOptionalFieldsValid = window.FormUtils.validateFields(optionalFields);

            if (!hasProfileChanges() || !areRequiredFieldsValid || !areOptionalFieldsValid) {
                event.preventDefault();
                updateSaveButtonState();
                if (!areRequiredFieldsValid || !areOptionalFieldsValid) {
                    window.FormUtils.focusFirstInvalidField(profileForm);
                }
            }
        });
    }

    if (passwordForm && window.FormUtils) {
        const currentPasswordInput = passwordForm.querySelector("#id_current_password");
        const newPasswordInput = passwordForm.querySelector("#id_new_password");
        const confirmInput = passwordForm.querySelector("#id_new_password_confirm");
        const newPasswordWrapper = newPasswordInput ? window.FormUtils.getFieldWrapper(newPasswordInput) : null;
        const passwordRules = Array.from(passwordForm.querySelectorAll("#profile-password-rules [data-rule]"));
        const passwordInputs = [currentPasswordInput, newPasswordInput, confirmInput].filter(Boolean);
        let hasNewPasswordChanged = false;
        let hasConfirmChanged = false;

        const requiredFields = [
            {
                input: currentPasswordInput,
                emptyMessage: "Введите текущий пароль.",
            },
        ].filter((item) => item.input);

        const passwordChecks = {
            length: (value) => value.length >= 8,
            lower: (value) => /[a-z\u0430-\u044f\u0451]/.test(value),
            upper: (value) => /[A-Z\u0410-\u042f\u0401]/.test(value),
            digit: (value) => /\d/.test(value),
            special: (value) => /[^A-Za-z0-9\u0410-\u042f\u0430-\u044f\u0401\u0451]/.test(value),
        };

        function getPasswordGroupError() {
            return passwordForm.querySelector("[data-password-group-error]");
        }

        function hasPasswordGroupError() {
            return Boolean(getPasswordGroupError() || passwordForm.dataset.hasPasswordGroupError === "true");
        }

        function setPasswordGroupErrorState(isInvalid) {
            passwordInputs.forEach((input) => {
                window.FormUtils.getFieldWrapper(input).classList.toggle("has-error", isInvalid);
            });
            passwordRules.forEach((rule) => {
                rule.classList.toggle("is-invalid", isInvalid);
                if (isInvalid) {
                    rule.classList.remove("is-valid");
                }
            });
        }

        function setNewPasswordErrorState(isInvalid) {
            if (!newPasswordWrapper) {
                return;
            }

            const errorList = newPasswordWrapper.querySelector(".errorlist");
            if (errorList) {
                errorList.remove();
            }
            newPasswordWrapper.classList.toggle("has-error", isInvalid);
        }

        function clearPasswordGroupError() {
            const groupError = getPasswordGroupError();
            if (groupError) {
                groupError.remove();
            }

            delete passwordForm.dataset.hasPasswordGroupError;
            passwordInputs.forEach((input) => {
                window.FormUtils.clearErrors(input);
            });
            setNewPasswordErrorState(false);
            passwordRules.forEach((rule) => {
                rule.classList.remove("is-valid", "is-invalid");
            });
        }

        function updatePasswordRules(options = {}) {
            const { forceInvalid = false, highlightEmpty = false } = options;
            const value = newPasswordInput ? newPasswordInput.value : "";
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

        function validateNewPassword(options = {}) {
            const { highlightEmpty = false } = options;
            if (!newPasswordInput) {
                return true;
            }

            const value = newPasswordInput.value;

            if (!value.trim()) {
                updatePasswordRules({ forceInvalid: highlightEmpty, highlightEmpty });
                setNewPasswordErrorState(highlightEmpty);
                return false;
            }

            const isEveryRuleValid = updatePasswordRules();
            setNewPasswordErrorState(!isEveryRuleValid);
            return isEveryRuleValid;
        }

        function validatePasswordConfirm(options = {}) {
            const { showMismatch = false } = options;
            if (!confirmInput || !newPasswordInput) {
                return true;
            }

            const confirmValue = confirmInput.value.trim();

            if (!confirmValue) {
                window.FormUtils.setErrors(confirmInput, ["Подтвердите новый пароль."]);
                return false;
            }

            if (newPasswordInput.value !== confirmInput.value) {
                if (showMismatch) {
                    window.FormUtils.setErrors(confirmInput, ["Пароли не совпадают."]);
                } else {
                    window.FormUtils.clearErrors(confirmInput);
                }
                return false;
            }

            window.FormUtils.clearErrors(confirmInput);
            return true;
        }

        resetPasswordModalErrors = () => {
            passwordInputs.forEach((input) => {
                if (input) {
                    window.FormUtils.clearErrors(input);
                }
            });

            const groupError = getPasswordGroupError();
            if (groupError) {
                groupError.remove();
            }
            delete passwordForm.dataset.hasPasswordGroupError;
            setNewPasswordErrorState(false);
            passwordRules.forEach((rule) => {
                rule.classList.remove("is-valid", "is-invalid");
            });
            requiredFields.forEach((fieldConfig) => {
                fieldConfig.hasChanged = false;
            });
            hasNewPasswordChanged = false;
            hasConfirmChanged = false;
        };

        window.FormUtils.bindRealtimeValidation(requiredFields);

        if (newPasswordInput) {
            newPasswordInput.addEventListener("input", () => {
                hasNewPasswordChanged = true;
                validateNewPassword({ highlightEmpty: true });
                if (hasConfirmChanged || window.FormUtils.getFieldWrapper(confirmInput).classList.contains("has-error")) {
                    validatePasswordConfirm();
                }
            });
            newPasswordInput.addEventListener("blur", () => {
                if (hasNewPasswordChanged) {
                    validateNewPassword({ highlightEmpty: true });
                }
            });
            updatePasswordRules();
        }

        if (confirmInput) {
            confirmInput.addEventListener("input", () => {
                hasConfirmChanged = true;
                validatePasswordConfirm();
            });
            confirmInput.addEventListener("blur", () => {
                if (hasConfirmChanged) {
                    validatePasswordConfirm();
                }
            });
        }

        if (hasPasswordGroupError()) {
            setPasswordGroupErrorState(true);
        }

        passwordInputs.forEach((input) => {
            input.addEventListener("focus", () => {
                if (!hasPasswordGroupError()) {
                    return;
                }

                clearPasswordGroupError();
                requiredFields.forEach((fieldConfig) => {
                    fieldConfig.hasChanged = false;
                });
                hasNewPasswordChanged = false;
                hasConfirmChanged = false;
            });
        });

        passwordForm.addEventListener("submit", (event) => {
            hasNewPasswordChanged = true;
            hasConfirmChanged = true;
            const areRequiredFieldsValid = window.FormUtils.validateFields(requiredFields);
            const isNewPasswordValid = validateNewPassword({ highlightEmpty: true });
            const isPasswordConfirmValid = validatePasswordConfirm({ showMismatch: true });

            if (!areRequiredFieldsValid || !isNewPasswordValid || !isPasswordConfirmValid) {
                event.preventDefault();
                if (passwordForm.querySelector(".form-field.has-error")) {
                    window.FormUtils.focusFirstInvalidField(passwordForm);
                } else if (!isNewPasswordValid && newPasswordInput) {
                    newPasswordInput.scrollIntoView({
                        behavior: "smooth",
                        block: "center",
                    });
                    newPasswordInput.focus({ preventScroll: true });
                }
            }
        });
    }

    function setupModal(config) {
        const modal = document.querySelector(config.modalSelector);
        const openButton = document.querySelector(config.openSelector);
        const closeButtons = document.querySelectorAll(config.closeSelector);

        if (!modal || !openButton) {
            return;
        }

        function syncBodyScroll() {
            const hasOpenModal = document.querySelector(".profile-modal.is-open");
            document.body.style.overflow = hasOpenModal ? "hidden" : "";
        }

        function openModal() {
            modal.classList.add("is-open");
            syncBodyScroll();
        }

        function closeModal() {
            modal.classList.remove("is-open");
            if (config.onClose) {
                config.onClose();
            }
            syncBodyScroll();
        }

        openButton.addEventListener("click", openModal);
        closeButtons.forEach((button) => {
            button.addEventListener("click", closeModal);
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && modal.classList.contains("is-open")) {
                closeModal();
            }
        });

        syncBodyScroll();
    }

    setupModal({
        modalSelector: "[data-password-modal]",
        openSelector: "[data-password-open]",
        closeSelector: "[data-password-close]",
        onClose: resetPasswordModalErrors,
    });

    setupModal({
        modalSelector: "[data-delete-modal]",
        openSelector: "[data-delete-open]",
        closeSelector: "[data-delete-close]",
    });
})();
