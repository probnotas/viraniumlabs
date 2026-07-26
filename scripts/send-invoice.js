// Create and email a Stripe invoice with a hosted payment page.
// Operator-run only — this is intentionally not a public API endpoint.
//
// Usage:
//   node scripts/send-invoice.js --email cfo@partner.com --name "Partner Corp" \
//     --desc "Sponsored research — Q3 2026" --amount 25000 --currency usd --due 30
//
// --amount is in whole currency units (25000 = $25,000.00).
// Reads STRIPE_SECRET_KEY from the environment (or a local .env).

import Stripe from 'stripe';
import { readFileSync } from 'node:fs';

// Minimal .env loader so the script works without extra dependencies.
try {
  for (const line of readFileSync(new URL('../.env', import.meta.url), 'utf8').split('\n')) {
    const m = line.match(/^([A-Z_]+)=(.*)$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2];
  }
} catch {}

function arg(flag, fallback) {
  const i = process.argv.indexOf(`--${flag}`);
  if (i === -1 || i === process.argv.length - 1) {
    if (fallback !== undefined) return fallback;
    console.error(`Missing required argument: --${flag}`);
    process.exit(1);
  }
  return process.argv[i + 1];
}

const email = arg('email');
const name = arg('name');
const description = arg('desc');
const amount = Math.round(Number(arg('amount')) * 100);
const currency = arg('currency', 'usd');
const daysUntilDue = Number(arg('due', '30'));

if (!Number.isFinite(amount) || amount <= 0) {
  console.error('--amount must be a positive number (whole currency units)');
  process.exit(1);
}
if (!process.env.STRIPE_SECRET_KEY) {
  console.error('STRIPE_SECRET_KEY is not set (set it in the environment or .env)');
  process.exit(1);
}

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY, {
  apiVersion: '2026-06-24.dahlia',
});

// Reuse an existing customer by email so repeat invoices don't create duplicates.
const existing = await stripe.customers.list({ email, limit: 1 });
const customer =
  existing.data[0] ?? (await stripe.customers.create({ email, name }));

const invoice = await stripe.invoices.create({
  customer: customer.id,
  collection_method: 'send_invoice',
  days_until_due: daysUntilDue,
  auto_advance: false,
});

await stripe.invoiceItems.create({
  customer: customer.id,
  invoice: invoice.id,
  description,
  amount,
  currency,
});

const finalized = await stripe.invoices.finalizeInvoice(invoice.id);
await stripe.invoices.sendInvoice(finalized.id);

console.log(`Invoice ${finalized.number} sent to ${email}`);
console.log(`Hosted payment page: ${finalized.hosted_invoice_url}`);
