# BIKE RESQ — Local Website + Backend MVP

## Requirements
- Install Node.js 20 or newer.
- VS Code is recommended.

## Run locally
1. Extract this folder and open it in VS Code.
2. Open Terminal in the `BIKE-RESQ-LOCAL` folder.
3. Run `npm install`.
4. Copy `.env.example` to a new file named `.env`.
5. Change `SESSION_SECRET` and `ADMIN_PASSWORD` in `.env`.
6. Run `npm start`.
7. Open `http://localhost:3000`.

Default local admin email/password are shown in `.env.example`. Change them before starting. The server creates the admin account on first run.

## Included
- Customer and partner registration/login.
- Admin account and admin assignment dashboard.
- Customer service requests.
- Browser location permission and coordinates saved with the request.
- Partner job status flow.
- Basic partner earnings ledger.
- Partner PhonePe payment note field.

## Important limitations / safety
- This is a local development MVP, not production-ready. The default Express session store is in-memory; use a persistent session store, HTTPS, secure cookies, CSRF protection, stronger validation, backups, monitoring, and a security review before public deployment.
- Browser geolocation works on `localhost` and HTTPS. It will not work reliably on a plain HTTP public website. A real map needs a map provider/API key; this starter displays the captured coordinates rather than a street map.
- Fuel options are referral-only to authorised fuel stations. This project intentionally does not coordinate fuel transport, storage, dispatch or delivery.
- PhonePe is NOT connected. A PhonePe QR scanner does not automatically transfer partner earnings. This MVP records estimated earnings only; it does not collect customer payments or send payouts. Real payment collection/payouts require an approved merchant setup and official payment-provider integration. Never collect or store UPI PINs, OTPs, passwords, or card details.
- The admin dashboard assigns jobs and partner earnings are created after completion. Admin payout reconciliation and mark-paid UI are not included in this first local version.
- Do not use real customer location or contact information while testing. Use test accounts and sample data.

## Main files
- `server.js` — Express backend and SQLite database.
- `public/index.html` — website and dashboards.
- `public/style.css` — design.
- `public/app.js` — frontend logic.
- `data/bike-resq.sqlite` — created automatically at first run.
