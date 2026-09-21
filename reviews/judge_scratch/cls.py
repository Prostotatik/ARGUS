import sys
sys.path.insert(0, r"E:/Projects/Averis x Monash/backend")
from sdoc.classifier import classify_rules
cases = [
 # (expected, from, subject, body, attachments)
 ("BL_COMPARISON","ops@newforwarder.com","Draft BL check - MSKU booking 88231","Hi team, could you please review the attached draft bill of lading against our shipping instructions and tell us if anything is off? Thanks.",["a/SI.pdf","a/BL.pdf"]),
 ("BL_COMPARISON","a@x.com","Please verify BL","Hello, kindly verify the enclosed B/L draft matches the SI we submitted last Friday. Regards",["a/x_SI.docx","a/x_BL.docx"]),
 ("BL_COMPARISON","a@x.com","RE: Invoice 4412 - shipment 55","Hi, both docs attached (SI and draft BL). Please cross-check consignee, ports and weights before we release.",["a/SI.txt","a/BL.txt"]),
 ("BL_COMPARISON","a@x.com","Urgent: check documents for vessel EVER GIVEN","Attached: shipping instruction and bill of lading draft. Any discrepancies?",["a/SI.txt","a/BL.txt"]),
 ("BL_COMPARISON","x@y.com","Fwd: docs","see attached SI + draft BL, pls compare",["a/SI.txt","a/BL.txt"]),
 ("SI_REQUEST","a@x.com","Need shipping instruction for booking 7781","Dear team, please send us the shipping instruction template for the upcoming vessel. We have cargo to book.",[]),
 ("SI_REQUEST","a@x.com","SI submission - Coated Board","Please find our SI details below.\nShipper: ABC\nConsignee: XYZ\nPOL: Port Klang\nPOD: Busan\nDescription of goods: paper reels",[]),
 ("SI_REQUEST","a@x.com","New booking - please raise BL instruction","Hi, we want to submit instructions for a new booking, container 2x40HC to Rotterdam. Please advise the cut-off.",[]),
 ("INVOICE_QUERY","acct@x.com","Query on invoice INV-2026-0091","Hello, we noticed the THC amount on your invoice is higher than quoted. Can you confirm and issue a credit note?",[]),
 ("INVOICE_QUERY","acct@x.com","Payment status - freight charges","Kindly advise when the freight payment was received for shipment 4412.",[]),
 ("INVOICE_QUERY","acct@x.com","Statement of account August","Please send the statement of account and outstanding balance for August.",[]),
 ("GENERAL","hr@x.com","Office closed on Friday","Please note the office will be closed this Friday for the public holiday.",[]),
 ("GENERAL","ops@x.com","Vessel delay notice - ETA changed","FYI the vessel ETA has changed to 24 Sept. No action required.",[]),
 ("GENERAL","ops@x.com","Weekly meeting minutes","Attached are the minutes from Monday's meeting.",[]),
 ("GENERAL","ops@x.com","Re: Draft BL update","Thanks, we received it. Will review next week. Have a nice weekend.",[]),
 ("SPAM","promo@deals.xyz","You've been selected!","Click here to claim your reward now. Limited time only!!",[]),
 ("SPAM","seo@growth.biz","Boost your website traffic","We can rank your site #1 on Google in 7 days. Reply for a free audit.",[]),
 ("SPAM","ceo@rnail.co","Wire transfer needed urgently","Hi, I need you to process a payment today. I'm in a meeting, do not call. Reply asap.",[]),
 ("SPAM","lottery@win.com","Claim your prize","Congratulations, you won 1,000,000 USD, send bank details.",[]),
 ("SPAM","support@paypa1-secure.com","Your account is locked","Your account has been limited. Please confirm your password at http://paypa1-secure.com/login",[]),
 ("GENERAL","hr@x.com","Happy Diwali","Wishing everyone a happy Diwali.",[]),
 ("INVOICE_QUERY","acct@x.com","Debit note for demurrage container TCLU1234567","Please find debit note. Kindly settle demurrage charges.",[]),
 ("BL_COMPARISON","a@x.com","BL draft for approval","Dear Sir, attached is the SI and the draft BL for your kind confirmation.",["a/SI.pdf","a/BL.pdf"]),
]
bad=0
for exp,fr,sub,body,att in cases:
    r=classify_rules({"from":fr,"subject":sub,"body":body,"attachments":att},[a.split('/')[-1] for a in att])
    ok = r.category==exp
    if not ok: bad+=1
    print(("ok " if ok else "BAD"), exp, "->", r.category, round(r.confidence,2), "|", sub[:50], "|", r.reasons[:2])
print("bad", bad, "of", len(cases))
