document.addEventListener("DOMContentLoaded", function () {

    // 1. Confirm before deleting records
    const deleteForms = document.querySelectorAll(".delete-form");

    deleteForms.forEach(function (form) {
        form.addEventListener("submit", function (event) {
            const confirmed = confirm(
                "Are you sure you want to delete this record?"
            );

            if (!confirmed) {
                event.preventDefault();
            }
        });
    });

    // 2. Automatically hide success messages
    const successMessages = document.querySelectorAll(
        ".alert-success"
    );

    successMessages.forEach(function (message) {
        setTimeout(function () {
            message.style.transition = "opacity 0.5s ease";
            message.style.opacity = "0";

            setTimeout(function () {
                message.remove();
            }, 500);

        }, 4000);
    });

    // 3. Prevent accidental double form submission
    const forms = document.querySelectorAll(
        "form:not(.delete-form)"
    );

    forms.forEach(function (form) {
        form.addEventListener("submit", function () {
            const submitButton = form.querySelector(
                'button[type="submit"], input[type="submit"]'
            );

            if (submitButton && form.checkValidity()) {
                submitButton.disabled = true;
                submitButton.textContent = "Please wait...";
            }
        });
    });

});