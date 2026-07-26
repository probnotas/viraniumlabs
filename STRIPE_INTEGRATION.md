# Stripe integration plan — Viranium Labs

Tailored for: a research lab (viraniumlabs.vercel.app) — static HTML site on Vercel, no
backend, no existing Stripe code. Products in scope: **Payments** and **Invoicing**.

Based on Stripe's current best-practices guidance (API version `2026-06-24.dahlia`,
Node SDK v22.x). Reference material lives in `skills/stripe-best-practices/`.

---

## 1. How money will actually flow

Two distinct flows, matching the two Stripe products you picked:

| Flow | Who initiates | Stripe product | Surface |
| --- | --- | --- | --- |
| One-time payments (supporters, workshop fees, one-off services) | The payer, from the website | Payments | Stripe-hosted Checkout via a Vercel serverless function |
| B2B billing (sponsored research, partnerships, consulting) | You, per agreement | Invoicing | Hosted invoice page, sent by email — driven from a local script or the Dashboard |

A research lab's invoicing is operator-initiated and low-volume, so invoices are
**not** exposed as a public API endpoint — they're created from
`scripts/send-invoice.js` (or the Dashboard, which needs no code at all).

## 2. Account and key setup (do this first)

1. Create a Stripe account (or a sandbox: `npm i -g @stripe/cli && stripe sandbox create`).
2. Create a **restricted API key** (`rk_…`), not the default secret key —
   Dashboard → Developers → API keys → Create restricted key. Grant only:
   - Checkout Sessions: Write
   - Customers: Write
   - Invoices: Write
   - Products/Prices: Write (only if you later move to catalog Prices)
3. Store keys in **Vercel sensitive environment variables**
   (Project → Settings → Environment Variables → mark as Sensitive), never in code
   or committed `.env` files. Locally, use `.env` (gitignored; template in `.env.example`).
4. Use separate keys per environment (test vs. live).
5. Turn on 2FA with a passkey or authenticator app for the Dashboard — not SMS.

## 3. Payments — Stripe-hosted Checkout

- **API**: Checkout Sessions (`checkout.sessions.create`) — the recommended API for
  on-session one-time payments. Never the legacy Charges API, Card Element, or Sources.
- **Surface**: Stripe-hosted Checkout page. The static site just needs one serverless
  function ([api/create-checkout-session.js](api/create-checkout-session.js)) that
  creates a session and redirects; no Stripe.js on your pages, no PCI surface.
- **Dynamic payment methods**: `payment_method_types` is deliberately omitted —
  Stripe picks the best-converting eligible methods per customer. Manage methods in
  the Dashboard, not code.
- **Flow tagging**: sessions carry an `integration_identifier` label so you can
  compare checkout flows in the Dashboard (supported on `2026-03-25.dahlia`+).
- **Amount safety**: the client sends a tier name (`supporter` / `patron` / `benefactor`);
  the server maps it to an amount. The client can never set an arbitrary price.
- Pages: [support.html](support.html) (payment page) → Checkout → [success.html](success.html).

Even simpler no-code alternative while volume is near zero: **Payment Links**
(Dashboard → Payment Links) — paste the URL anywhere. The serverless route above is
for when you want the flow on your own domain.

## 4. Invoicing

- Create a Customer, attach invoice items, then an Invoice with
  `collection_method: 'send_invoice'` and `days_until_due` — Stripe emails a hosted
  invoice page + PDF; the customer pays online, and Stripe handles receipts and
  reminders (configure reminders in Dashboard → Settings → Billing).
- Run [scripts/send-invoice.js](scripts/send-invoice.js) locally:

  ```
  node scripts/send-invoice.js --email cfo@partner.com --name "Partner Corp" \
    --desc "Sponsored research — Q3 2026" --amount 25000 --currency usd --due 30
  ```

- The script reuses an existing Customer by email so repeat invoices don't create
  duplicates.
- For low volume, the Dashboard's invoice editor is equally correct — the script
  just makes it repeatable.

## 5. Webhooks — the source of truth for "paid"

Never trust a redirect to `success.html` as proof of payment. The webhook endpoint
([api/stripe-webhook.js](api/stripe-webhook.js)):

- **Verifies the signature** on the raw request body before touching any event.
- Handles: `checkout.session.completed`, `checkout.session.async_payment_succeeded`/`_failed`,
  `invoice.paid`, `invoice.payment_failed`.
- Setup: Dashboard → Developers → Webhooks → Add endpoint →
  `https://viraniumlabs.vercel.app/api/stripe-webhook`, subscribe to the events above,
  and put the signing secret in `STRIPE_WEBHOOK_SECRET`.
- Local testing: `stripe listen --forward-to localhost:3000/api/stripe-webhook`.

## 6. Tax (flagging now so it doesn't bite later)

`automatic_tax` is **not** enabled in this scaffold. Enabling it does nothing —
silently — until you have an active tax registration in Stripe. If/when you have
US sales-tax or VAT obligations: register in Dashboard → Tax first, then enable
`automatic_tax: { enabled: true }` on Checkout Sessions and invoices.

## 7. Security checklist

- [x] No keys in source — env vars only; `.env` gitignored
- [x] Restricted key (`rk_`) recommended over secret key
- [x] Webhook signature verification on raw body
- [x] No client-controlled amounts
- [x] No Stripe.js / card data on your pages (hosted Checkout ⇒ minimal PCI scope: SAQ A)
- [ ] Pre-commit hook to catch `sk_live_`/`rk_live_` patterns (add when repo gains contributors)
- [ ] IP access policies on API keys (Dashboard → API keys)

## 8. Go-live checklist

1. Test end-to-end in test mode (card `4242 4242 4242 4242`, any future expiry/CVC).
2. Trigger webhook events with `stripe trigger checkout.session.completed`.
3. Create the live-mode restricted key; set it (and the live webhook secret) as
   sensitive env vars in Vercel; redeploy.
4. Register the live webhook endpoint in the live Dashboard.
5. Review Stripe's go-live checklist: https://docs.stripe.com/get-started/checklist/go-live
