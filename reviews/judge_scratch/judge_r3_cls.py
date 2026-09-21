import sys
sys.path.insert(0, r"E:/Projects/Averis x Monash/backend")
from sdoc.classifier import classify_rules

# Fresh batch, JUDGE Round 3: new phrasing, new sender domains (never used in cls.py, cls_fresh2.py,
# or the developer.md Round 3 write-up), including several spammy-TLD senders paired with real
# attachments (the exact bug class that was fixed) and a couple of harder edge cases.
cases = [
 ("BL_COMPARISON", "docs@oceanline-agents.net", "Two files attached, need eyes on them",
  "Morning - dropping the shipper's paperwork and the carrier's draft in this thread. Could someone run through both and flag anything that doesn't line up before we tell the customer it's clean?",
  ["shipping_instruction.pdf", "draft_bl.pdf"]),
 ("BL_COMPARISON", "ops@westbridge-cargo.biz", "Final look before we confirm to customer",
  "Please give the attached instruction and the carrier's draft a proper read-through - want to be sure everything reconciles before we tell the client it's good to go.",
  ["si.xlsx", "bl_draft.docx"]),
 ("BL_COMPARISON", "coordination@harbor-trade.info", "Two docs, need a match check",
  "See attached - our filed instruction plus the draft bill the line issued. Please match them line by line and shout if anything is off.",
  ["instruction.txt", "carrier_draft.txt"]),
 ("SI_REQUEST", "newaccounts@brightfield-imports.com", "What do we send you to get a booking started?",
  "We're setting up as a new shipper with your line and aren't sure what paperwork you need from us before a container gets booked. Can you point us to the right form?", []),
 ("SI_REQUEST", "logistics@vantagepoint.co", "Container details still needed on our end",
  "We haven't yet sent through the cargo details for the upcoming sailing - what do you need from us and by when?", []),
 ("INVOICE_QUERY", "billing@meridiantrade.org", "Totals on this statement look off",
  "Went through the statement you sent and a couple of the freight charges don't match what we agreed at booking. Could someone reconcile this?", []),
 ("INVOICE_QUERY", "ap.team@brightfield-imports.com", "Refund needed for duplicate charge",
  "It looks like we were billed twice for the same container on this shipment. Please confirm and process a refund.", []),
 ("GENERAL", "notifications@carrierline.com", "Terminal cut-off moved earlier",
  "Heads up that the terminal has pulled the cut-off time forward by a few hours for next week's sailing. No response needed, just keeping you posted.", []),
 ("GENERAL", "pa@westbridge-cargo.biz", "Out of office this Friday",
  "Just a quick note that I'll be out of office Friday - back Monday, nothing urgent pending on our side.", []),
 ("GENERAL", "team@harbor-trade.info", "Appreciate the fast handling last week",
  "Wanted to say thanks for turning that request around so quickly last week - all sorted on our end now.", []),
 ("SPAM", "prize@luckywinner.click", "You've been selected for a cash reward",
  "Congratulations! You are one of today's lucky winners. Click below within 24 hours to claim your prize before it expires.", []),
 ("SPAM", "security@account-alert-team.top", "Unusual sign-in detected - verify now",
  "We detected a login from a new device. Verify your account credentials immediately at the secure link below or access will be suspended.", []),
 ("SPAM", "ceo.office@urgentrequest.xyz", "Quick favor, are you free",
  "Are you at your desk right now? I need you to handle a wire transfer discreetly and can't call - reply asap.", []),
 # Spammy-TLD sender + real BL_COMPARISON content + attachments - the specific bug class
 ("BL_COMPARISON", "review@pacificgateway-forwarding.net", "Please compare before release",
  "Attached is our shipping instruction and the carrier's draft bill of lading. Please cross-check every field before we authorise release to the consignee.",
  ["si_final.pdf", "bl_draft_v2.pdf"]),
 ("SI_REQUEST", "firsttime@newshipperco.biz", "Our first booking - unsure what's required",
  "This will be our first shipment through your line and we don't want to hold things up - what information should we be submitting ahead of the sailing?", []),
 ("INVOICE_QUERY", "accounts@meridiantrade.org", "Numbers don't add up on invoice 4471",
  "Checked invoice 4471 against our own records and the freight and THC lines don't reconcile with the quote. Can someone take a look?", []),
 ("GENERAL", "ops@vantagepoint.co", "Public holiday next Monday - office closed",
  "Just a reminder our office will be closed next Monday for the public holiday, back to normal Tuesday.", []),
 ("BL_COMPARISON", "docdesk@oceanline-agents.net", "Sanity check requested on attached pair",
  "Could someone give the two attached documents a sanity check? Want to confirm the shipper, weight and container count all agree before we sign off.",
  ["docA.docx", "docB.docx"]),
]

bad = 0
for exp, fr, sub, body, att in cases:
    r = classify_rules({"from": fr, "subject": sub, "body": body, "attachments": att}, att)
    ok = r.category == exp
    if not ok:
        bad += 1
    print(("ok " if ok else "BAD"), exp, "->", r.category, round(r.confidence, 2), "|", fr, "|", sub[:55])
print(f"\n{len(cases)-bad}/{len(cases)} correct")
