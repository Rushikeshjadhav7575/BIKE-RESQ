
const bookingForm = document.getElementById("bookingForm");
const message = document.getElementById("bookingMessage");
const gpsButton = document.getElementById("getLocation");

gpsButton.addEventListener("click", () => {
  if (!navigator.geolocation) {
    message.textContent = "GPS is not supported by your browser.";
    return;
  }

  message.textContent = "Getting your location...";

  navigator.geolocation.getCurrentPosition(
    position => {
      const lat = position.coords.latitude;
      const lng = position.coords.longitude;

      document.getElementById("location").value =
        `${lat}, ${lng}`;

      message.textContent = "Location captured successfully.";
    },
    () => {
      message.textContent =
        "Location unavailable. Please enter it manually.";
    },
    { enableHighAccuracy: true, timeout: 10000 }
  );
});

bookingForm.addEventListener("submit", event => {
  event.preventDefault();

  const booking = {
    id: "BR" + Date.now(),
    name: document.getElementById("customerName").value.trim(),
    phone: document.getElementById("phone").value.trim(),
    service: document.getElementById("service").value,
    bike: document.getElementById("bike").value.trim(),
    location: document.getElementById("location").value.trim(),
    problem: document.getElementById("problem").value.trim(),
    status: "Demo Request Received",
    createdAt: new Date().toISOString()
  };

  const bookings = JSON.parse(
    localStorage.getItem("bikeResqBookings") || "[]"
  );

  bookings.push(booking);
  localStorage.setItem("bikeResqBookings", JSON.stringify(bookings));

  message.textContent =
    `Demo request saved! Booking ID: ${booking.id}`;

  bookingForm.reset();
});

