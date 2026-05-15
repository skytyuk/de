(function () {
    function getFieldWrapper(input) {
        return input.closest(".form-field");
    }

    function setErrors(input, messages) {
        const wrapper = getFieldWrapper(input);
        let errorList = wrapper.querySelector(".errorlist");

        if (!messages.length) {
            if (errorList) {
                errorList.remove();
            }
            wrapper.classList.remove("has-error");
            return;
        }

        if (!errorList) {
            errorList = document.createElement("ul");
            errorList.className = "errorlist";
            wrapper.appendChild(errorList);
        }

        errorList.innerHTML = messages.map((message) => `<li>${message}</li>`).join("");
        wrapper.classList.add("has-error");
    }

    function clearErrors(input) {
        setErrors(input, []);
    }

    function focusFirstInvalidField(form) {
        const firstInvalidField = form.querySelector(".form-field.has-error input, .form-field.has-error select, .form-field.has-error textarea");
        if (!firstInvalidField) {
            return;
        }

        firstInvalidField.scrollIntoView({
            behavior: "smooth",
            block: "center",
        });
        firstInvalidField.focus({ preventScroll: true });
    }

    function validateField(fieldConfig) {
        const { input, emptyMessage, validate, required = true } = fieldConfig;
        if (input.type === "checkbox") {
            if (required && !input.checked) {
                setErrors(input, [emptyMessage]);
                return false;
            }
            clearErrors(input);
            return true;
        }
        const value = input.value.trim();

        if (required && !value) {
            setErrors(input, [emptyMessage]);
            return false;
        }

        if (!required && !value) {
            clearErrors(input);
            return true;
        }

        const extraErrors = validate ? validate(value) : [];
        if (extraErrors.length) {
            setErrors(input, extraErrors);
            return false;
        }

        clearErrors(input);
        return true;
    }

    function validateFields(fields) {
        let isValid = true;

        fields.forEach((fieldConfig) => {
            fieldConfig.hasChanged = true;
            if (!validateField(fieldConfig)) {
                isValid = false;
            }
        });

        return isValid;
    }

    function bindRealtimeValidation(fields) {
        fields.forEach((fieldConfig) => {
            fieldConfig.hasChanged = false;
            fieldConfig.input.addEventListener("input", () => {
                fieldConfig.hasChanged = true;
                validateField(fieldConfig);
            });
            fieldConfig.input.addEventListener("change", () => {
                fieldConfig.hasChanged = true;
                validateField(fieldConfig);
            });
            fieldConfig.input.addEventListener("blur", () => {
                if (fieldConfig.hasChanged) {
                    validateField(fieldConfig);
                }
            });
        });
    }

    function getEmailErrors(value) {
        const normalizedValue = value.trim();
        if (!normalizedValue) {
            return [];
        }

        const errors = [];
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

        if (normalizedValue.includes(" ")) {
            errors.push("Почта не должна содержать пробелы.");
        }

        if (!emailPattern.test(normalizedValue)) {
            errors.push("Введите корректную почту, например: name@example.com.");
        }

        return errors;
    }

    function getPhoneErrors(value) {
        const normalizedValue = value.trim();
        if (!normalizedValue) {
            return [];
        }

        const errors = [];
        const phonePattern = /^\+?[0-9]{10,15}$/;

        if (!phonePattern.test(normalizedValue)) {
            errors.push("Введите телефон в формате +79991234567 или 89991234567.");
        }

        return errors;
    }

    function getNameErrors(value, fieldName = "Поле") {
        const normalizedValue = value.trim();
        if (!normalizedValue) {
            return [];
        }

        if (!/^\p{L}+$/u.test(normalizedValue)) {
            return [`Поле "${fieldName}" не должно содержать цифры или специальные символы.`];
        }

        return [];
    }

    window.FormUtils = {
        bindRealtimeValidation,
        clearErrors,
        focusFirstInvalidField,
        getEmailErrors,
        getFieldWrapper,
        getNameErrors,
        getPhoneErrors,
        setErrors,
        validateField,
        validateFields,
    };
})();
