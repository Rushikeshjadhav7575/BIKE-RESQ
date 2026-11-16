
const registerForm = document.getElementById("registerForm");

if (registerForm) {
  registerForm.addEventListener("submit", event => {
    event.preventDefault();

    document.getElementById("registerMessage").textContent =
      "Registration screen is ready. Connect the secure backend to create your account.";
  });
}

const loginForm = document.getElementById("loginForm");

if (loginForm) {
  loginForm.addEventListener("submit", event => {
    event.preventDefault();

    document.getElementById("loginMessage").textContent =
      "Login screen is ready. Backend authentication is not connected yet.";
  });
}
