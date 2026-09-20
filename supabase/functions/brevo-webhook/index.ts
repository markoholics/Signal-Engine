// Supabase Edge Function: receives Brevo webhooks and writes the outcome ledger.
// Deploy from the Supabase dashboard (Edge Functions, New function, paste this).
// No server of your own required.
//
// In Brevo: Settings, Webhooks, add this function's URL and tick
// delivered, opened, click, hard bounce, soft bounce, unsubscribe, spam.
// Replies are not a Brevo webhook event; log those by hand, they are few and
// you want to read them anyway.
//
// Correlation: every send goes out with a custom header X-Send-Id carrying the
// send row id. Brevo echoes custom headers back on the webhook payload.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const MAP: Record<string, string> = {
  delivered: "delivered",
  opened: "open",
  unique_opened: "open",
  click: "open",
  hard_bounce: "bounce",
  soft_bounce: "bounce",
  blocked: "bounce",
  spam: "unsubscribe",
  unsubscribed: "unsubscribe",
};

Deno.serve(async (req) => {
  const secret = req.headers.get("x-webhook-secret");
  if (secret !== Deno.env.get("WEBHOOK_SECRET")) {
    return new Response("forbidden", { status: 403 });
  }

  const body = await req.json();
  const outcome = MAP[body.event];
  if (!outcome) return new Response("ignored", { status: 200 });

  const sendId = Number(body["X-Send-Id"] ?? body.tags?.[0]);
  if (!sendId) return new Response("no send id", { status: 200 });

  const db = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );

  await db.from("outcome").insert({
    send_id: sendId,
    outcome_type: outcome,
    notes: body.event,
    source: "brevo",
  });

  if (outcome === "unsubscribe" || outcome === "bounce") {
    await db.from("suppression").insert({
      email: body.email,
      reason: body.event,
    });
  }

  return new Response("ok", { status: 200 });
});
