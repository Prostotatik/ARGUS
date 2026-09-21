import sys
sys.path.insert(0, r"E:/Projects/Averis x Monash/backend")
from sdoc.classifier import classify_rules
cases = [
 ("BL_COMPARISON","logistics@partner-co.net","Docs for your review - vessel MOL GLORY","Good afternoon, please find the two shipping documents attached for this consignment. Kindly cross-check them and let us know if you spot any discrepancy in the container numbers or weight figures before we proceed.",["a/1.pdf","a/2.pdf"]),
 ("BL_COMPARISON","trade.desk@buyerside.com","Can you sanity-check these two files?","Attaching the paperwork for booking ref 90212. One is our instruction, the other is the carrier's draft - want a second set of eyes before we sign off.",["a/1.txt","a/2.txt"]),
 ("SI_REQUEST","export.team@factory.co","Need the instruction form for next week's container","We have cargo ready to move next Tuesday and need the standard instruction form to submit to the line. Can you send it over?",[]),
 ("SI_REQUEST","ops@vendor.com","Booking details for upcoming shipment","Please advise the format you need our shipment details in so we can get the booking confirmed with the carrier.",[]),
 ("INVOICE_QUERY","finance@client.org","Discrepancy on the latest bill","We reviewed the bill you sent and the numbers don't line up with what was quoted originally - can someone look into this?",[]),
 ("INVOICE_QUERY","payables@client.org","Reminder: unpaid balance from last quarter","Just following up, our records show an unpaid balance from Q2 that hasn't been settled. Can you send an updated statement?",[]),
 ("GENERAL","admin@partner.com","Team out for a conference next week","Just a heads up that most of our team will be traveling for a conference, response times may be a bit slower.",[]),
 ("GENERAL","ops@carrier.com","Vessel schedule update - no action needed","This is just an FYI that the sailing schedule has shifted slightly. Nothing needed from your side.",[]),
 ("GENERAL","team@client.com","Thanks for the quick turnaround","Really appreciate how fast your team handled that last request. Nothing further needed.",[]),
 ("SPAM","noreply@freegiftcard.top","You have unclaimed rewards waiting","Act now before your reward expires! Tap the link to unlock your free gift card.",[]),
 ("SPAM","it-helpdesk@corp-secure-verify.com","Immediate action: mailbox quota exceeded","Your mailbox will be suspended in 24 hours unless you verify your credentials at the link below.",[]),
 ("SPAM","finance@ceo-urgent.co","Are you at your desk?","I need you to handle something confidential right now, can't talk, reply here first.",[]),
 ("BL_COMPARISON","coordinator@freightops.com","Comparing SI to carrier's B/L draft","Team, please compare the instruction we filed against the carrier's draft bill and flag anything that looks off before departure.",["a/si.docx","a/bl.docx"]),
 ("SI_REQUEST","newclient@importer.com","First time shipper - what do you need from us?","This is our first shipment with you. What information do you need us to submit before the vessel departs?",[]),
 ("GENERAL","hr@partner.com","Public holiday schedule for next month","Attached is our office's holiday calendar for the coming month for your reference.",[]),
 ("INVOICE_QUERY","ap@client.com","Credit note request for overcharge","We were overcharged on the last shipment - can you issue a credit note for the difference?",[]),
 ("BL_COMPARISON","cs@forwarder.net","Please double check before we release the B/L","Attached are both documents. We'd like a check on the details before releasing the final bill of lading to the customer.",["a/x.pdf","a/y.pdf"]),
 ("GENERAL","captain@carrier.com","Delay due to weather - informational","Just letting everyone know the vessel is delayed a day due to weather. No response required.",[]),
]
bad=0
for exp,fr,sub,body,att in cases:
    r=classify_rules({"from":fr,"subject":sub,"body":body,"attachments":att},[a.split('/')[-1] for a in att])
    ok = r.category==exp
    if not ok: bad+=1
    print(("ok " if ok else "BAD"), exp, "->", r.category, round(r.confidence,2), "|", sub[:50])
print("bad", bad, "of", len(cases))
