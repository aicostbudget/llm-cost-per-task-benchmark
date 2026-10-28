"""Task 5: label a customer message with one of 20 support intents."""

from __future__ import annotations

import random

from ..common import Verdict, strip_fence

TASK_ID = "intent_classification"
TITLE = "Support ticket intent classification"
DEFAULT_COUNT = 50

# intent -> (definition shown to the model, message templates). {x} slots are filled from FILLERS.
INTENTS = {
    "card_lost": ("The customer's card is lost or stolen and needs blocking.", [
        "I can't find my card anywhere since {when}, please block it", "my wallet got stolen {when} and my card was in it",
        "Pretty sure I left my card at {place}. Can you freeze it?"]),
    "card_not_arrived": ("A new or replacement card has not been delivered yet.", [
        "It's been {days} days and my new card still hasn't shown up", "where is my replacement card? ordered it {when}",
        "card delivery is late, the tracking hasn't moved in {days} days"]),
    "card_declined": ("A card payment was declined at a merchant.", [
        "my card got declined at {place} even though I have money", "Why was my payment refused at {place}?",
        "tried paying {amount} at {place} and it said declined"]),
    "pin_reset": ("The customer forgot or wants to change their PIN.", [
        "forgot my PIN, how do I get a new one", "I typed the wrong PIN three times and now it's blocked",
        "Can I change my card PIN in the app?"]),
    "refund_status": ("Asking when a merchant refund will appear on the account.", [
        "{place} said they refunded me {amount} {when}, when will I see it?", "still waiting on a refund from {place}",
        "the shop processed my return {when} but no money back yet"]),
    "duplicate_charge": ("The same purchase was charged more than once.", [
        "I was charged twice for the same thing at {place}", "there are two identical {amount} payments to {place}",
        "double charge on my account from {place}, please fix"]),
    "unrecognized_transaction": ("A transaction the customer does not recognise and did not make.", [
        "there's a {amount} payment to a company I've never heard of", "I didn't make this purchase from {place}",
        "what is this {amount} charge? it wasn't me"]),
    "transfer_pending": ("A bank transfer has been sent but is still pending.", [
        "my transfer to my landlord has been pending since {when}", "sent {amount} {when} and it still says pending",
        "why is my bank transfer stuck in processing?"]),
    "transfer_wrong_recipient": ("Money was sent to the wrong person or account.", [
        "I sent {amount} to the wrong account by mistake, can you get it back?", "typo in the IBAN, money went to someone else",
        "accidentally paid the wrong {who}"]),
    "exchange_rate": ("Question about the currency exchange rate applied.", [
        "the exchange rate you gave me for my {amount} purchase abroad looks bad", "what rate do you use to convert to euros?",
        "why did I get less than the market rate when exchanging?"]),
    "fee_question": ("Question about a fee that was charged.", [
        "why was I charged a fee for withdrawing cash at {place}?", "what is this monthly fee on my statement?",
        "there's a {amount} fee I don't understand"]),
    "top_up_failed": ("Adding money to the account failed.", [
        "tried to top up {amount} and it failed", "my top-up didn't go through but the money left my other bank",
        "can't add money to my account, the top up keeps failing"]),
    "atm_cash_not_received": ("The ATM did not dispense cash but the account was debited.", [
        "the ATM at {place} didn't give me the cash but took {amount} from my account", "no money came out of the machine, still charged",
        "ATM swallowed my withdrawal, {amount} gone"]),
    "account_closure": ("The customer wants to close their account.", [
        "I want to close my account please", "how do I delete my account and get my balance back?",
        "please shut down my account, I'm moving to another bank"]),
    "update_address": ("The customer wants to change their postal address.", [
        "I moved to {place_city}, how do I update my address?", "need to change my home address on file",
        "my address is out of date, I live in {place_city} now"]),
    "verify_identity": ("Problems with identity verification or uploading ID documents.", [
        "my ID verification keeps getting rejected", "the app won't accept my passport photo",
        "how long does identity verification take? submitted {when}"]),
    "app_login": ("Cannot log in to the app or website.", [
        "can't log in to the app, it keeps saying error", "I'm locked out of my account after updating my phone",
        "login code never arrives so I can't sign in"]),
    "statement_request": ("Wants an account statement or proof of balance.", [
        "I need a bank statement for {when} for my mortgage application", "how do I download my statements as PDF?",
        "can you send me proof of my account balance?"]),
    "card_limit": ("Wants to know or change spending or withdrawal limits.", [
        "what's my daily withdrawal limit?", "can I raise my card spending limit for a trip?",
        "I hit a limit trying to pay {amount}, can it be increased?"]),
    "contactless_not_working": ("Contactless payments do not work.", [
        "tap to pay isn't working on my card", "contactless keeps failing at {place}, chip and pin works fine",
        "why doesn't my card work with contactless?"]),
}

FILLERS = {
    "when": ["yesterday", "last Tuesday", "on Friday", "two days ago", "this morning", "last week"],
    "place": ["the supermarket", "a petrol station", "the airport", "an online shop", "the pharmacy", "a hotel in Lisbon"],
    "place_city": ["Bristol", "Ghent", "Bilbao", "Tartu", "Bologna"],
    "days": ["10", "12", "15", "20"],
    "amount": ["€24.99", "£180", "$62.40", "€1,200", "£9.50"],
    "who": ["contractor", "friend", "plumber", "seller"],
}
STYLE = [lambda s: s, lambda s: s.capitalize() + ".", lambda s: "Hi, " + s + ". Thanks", lambda s: s.lower() + "??",
         lambda s: "Hello support team. " + s.capitalize() + "."]

LABELS = list(INTENTS)
SYSTEM = ("Classify the customer message into exactly one intent. Reply with the intent label only, nothing else.\n"
          "Labels:\n" + "\n".join(f"- {label}: {INTENTS[label][0]}" for label in LABELS))


def generate(rng: random.Random, count: int) -> list[dict]:
    items = []
    labels = (LABELS * ((count // len(LABELS)) + 1))[:count]
    rng.shuffle(labels)
    for index, label in enumerate(labels):
        template = rng.choice(INTENTS[label][1])
        text = template
        for slot, values in FILLERS.items():
            text = text.replace("{" + slot + "}", rng.choice(values))
        text = rng.choice(STYLE)(text)
        items.append({"id": f"{TASK_ID}-{index + 1:03d}", "input": {"message": text}, "expected": {"label": label}})
    return items


def prompt(item: dict, shared: dict | None = None) -> dict:
    return {"system": SYSTEM, "user": item["input"]["message"]}


def validate(item: dict, output: str) -> Verdict:
    answer = strip_fence(output).strip().strip("`'\".").strip()
    if answer not in INTENTS:
        return Verdict.failed(f"not a label: {answer[:60]!r}")
    if answer != item["expected"]["label"]:
        return Verdict.failed(f"expected {item['expected']['label']}, got {answer}")
    return Verdict.passed()


def reference_output(item: dict) -> str:
    return item["expected"]["label"]


def wrong_outputs(item: dict) -> list[str]:
    other = next(label for label in LABELS if label != item["expected"]["label"])
    return [other, f"The intent is {item['expected']['label']}", item["expected"]["label"].upper()]
