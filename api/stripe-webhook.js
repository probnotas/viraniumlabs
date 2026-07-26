import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY, {
  apiVersion: '2026-06-24.dahlia',
});

export async function POST(request) {
  const signature = request.headers.get('stripe-signature');
  // Signature verification requires the raw, unparsed body.
  const payload = await request.text();

  let event;
  try {
    event = await stripe.webhooks.constructEventAsync(
      payload,
      signature,
      process.env.STRIPE_WEBHOOK_SECRET,
    );
  } catch (err) {
    console.error('Webhook signature verification failed:', err.message);
    return new Response('Invalid signature', { status: 400 });
  }

  switch (event.type) {
    case 'checkout.session.completed': {
      const session = event.data.object;
      // payment_status is 'unpaid' here for delayed methods (e.g. bank
      // debits) — fulfillment for those happens on async_payment_succeeded.
      if (session.payment_status === 'paid') {
        console.log(`Checkout paid: ${session.id} (${session.amount_total} ${session.currency})`);
        // TODO: record the payment / send a thank-you email
      }
      break;
    }
    case 'checkout.session.async_payment_succeeded': {
      const session = event.data.object;
      console.log(`Delayed payment succeeded: ${session.id}`);
      // TODO: record the payment / send a thank-you email
      break;
    }
    case 'checkout.session.async_payment_failed': {
      const session = event.data.object;
      console.log(`Delayed payment failed: ${session.id}`);
      break;
    }
    case 'invoice.paid': {
      const invoice = event.data.object;
      console.log(`Invoice paid: ${invoice.number} by ${invoice.customer_email}`);
      // TODO: mark the agreement as paid in your records
      break;
    }
    case 'invoice.payment_failed': {
      const invoice = event.data.object;
      console.log(`Invoice payment failed: ${invoice.number} (${invoice.customer_email})`);
      // TODO: follow up with the partner
      break;
    }
    default:
      break;
  }

  return Response.json({ received: true });
}
