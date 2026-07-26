import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY, {
  apiVersion: '2026-06-24.dahlia',
});

// Amounts live server-side only — the client picks a tier by name and can
// never set its own price.
const TIERS = {
  supporter: { amount: 100, label: 'Research support — Supporter' },
  patron: { amount: 500, label: 'Research support — Patron' },
  benefactor: { amount: 1000, label: 'Research support — Benefactor' },
};

export async function POST(request) {
  let tier;
  try {
    ({ tier } = await request.json());
  } catch {
    return Response.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const selected = TIERS[tier];
  if (!selected) {
    return Response.json({ error: 'Unknown tier' }, { status: 400 });
  }

  const siteUrl = process.env.SITE_URL || 'https://viraniumlabs.vercel.app';

  try {
    const session = await stripe.checkout.sessions.create({
      mode: 'payment',
      // payment_method_types is intentionally omitted so Stripe shows each
      // customer the eligible methods most likely to convert.
      line_items: [
        {
          price_data: {
            currency: 'usd',
            unit_amount: selected.amount,
            product_data: { name: selected.label },
          },
          quantity: 1,
        },
      ],
      integration_identifier: 'viranium-support-checkout-qkzmwrtb',
      success_url: `${siteUrl}/success.html?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${siteUrl}/support.html`,
    });

    return Response.json({ url: session.url });
  } catch (err) {
    console.error('Checkout session creation failed:', err.message);
    return Response.json({ error: 'Unable to start checkout' }, { status: 500 });
  }
}
