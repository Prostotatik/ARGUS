import pytest

from sdoc.classifier import classify_rules, clean_body


def em(subject, body="", frm="staff@aprilasia.com", att=None):
    return {"email_id": "t", "subject": subject, "body": body, "from": frm, "attachments": att or []}


CASES = [
    (em("TO CONFIRM DOCS _ 5RAE-00543 _ JEBEL ALI _ ACME _ MEDUUD123456",
        "Dear Ann,\n\nAttached are the SI and draft BL for OC 5RAE-00543. Please check the details and confirm.",
        att=["attachments/x_SI.txt", "attachments/x_BL.txt"]), "BL_COMPARISON"),
    (em("Draft BL MARCOPOLO - amend BL 045", "Please assist to send the draft BL for booking X for checking asap."),
     "BL_COMPARISON"),
    (em("RE_ SI - MEDUUD123456 - DIRECT(MSC) - 5RAE-00543 - KARACHI - OBL - AIE - 3-Jan-26",
        "Hi\n\nPlease find Shipping instruction for 5RAE-00543.\n\nPOL: SINGAPORE\nPOD: KARACHI\n\nShipper:\nACME\n\n"
        "Documents Required:\n1) 3 Original invoice"), "SI_REQUEST"),
    (em("REQUEST SI _ 5RAE-1 _ HOUSTON", "Kindly send us the shipping instruction asap."), "SI_REQUEST"),
    (em("REQUEST TO CANCEL INVOICE -5250071234 - ACME", "Requesting to cancel invoice 5250071234 and reverse the PGI."),
     "INVOICE_QUERY"),
    (em("2100 RAK BILLING 5070146123 MISSING GR", "We note the GR is still missing for invoice 1."), "INVOICE_QUERY"),
    (em("daily Berthing Report - 04 JAN 2026", "Kindly find the daily berthing report attached."), "GENERAL"),
    (em("_RPA_ India HSS SD Billing Process Completed - V", "This is an automated notification. No action required."),
     "GENERAL"),
    (em("Pending BL Release 05_01_2026", "Please find the list."), "GENERAL"),
    (em("Congratulations! You have WON a $1,000 Gift Card - CLAIM NOW", "Click here http://bit.ly/claim-prize-now",
        frm="winner@prize-claims.info"), "SPAM"),
    (em("Re: Invoice payment - kindly confirm your bank details",
        "Hello Dear, I am a bank officer with an urgent business proposal", frm="x@secure-mailbox.org"), "SPAM"),
]


@pytest.mark.parametrize("email,expected", CASES)
def test_rules_classifier(email, expected):
    r = classify_rules(email)
    assert r.category == expected, (r.category, r.scores)
    assert r.engine == "rules" and r.reasons


def test_boilerplate_and_quoted_thread_cannot_vote():
    body = ("Dear Team,\n\nHappy New Year to all.\n\nBest Regards,\nAnn\nShipping Documentation\n\n" + "_" * 30 +
            "\nFrom: Bob <b@x.com>\nSent: Monday, January 5, 2026 10:00 AM\nSubject: RE: draft BL\n\n"
            "Please check the draft BL against the SI.")
    assert "draft BL" not in clean_body(body)
    assert classify_rules(em("Welcoming the New Year 2026", body)).category == "GENERAL"


def test_warning_banner_removed():
    b = ("WARNING: This email originated outside of our organisation. As a security measure, please exercise caution "
         "with E-Mail content and any links or attachments.\n\nHello")
    assert clean_body(b) == "Hello"


def test_no_signal_defaults_to_general_with_low_confidence():
    r = classify_rules(em("hello", "ok"))
    assert r.category == "GENERAL" and r.confidence < 0.5
