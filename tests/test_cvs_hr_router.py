"""
Tests for the CVS HR reply router (cvs_hr_router_rules + cvs_hr_router server).

Every caller line of Mike's recorded golden dialog (research/aiquorum/
data-CALL.json, lines 2-18) is reproduced verbatim below, plus the variance
rows from the Savvy plan.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import json

import pytest
from fastmcp import Client

from mcp_server_kit import cvs_hr_router_rules as r
from mcp_server_kit.cvs_hr_database import CvsHrDatabase
from mcp_server_kit.cvs_hr_router import CvsHrRouterMCPServer

# Caller lines from data-CALL.json, keyed by their line index there.
GOLDEN = {
    2: "Yeah, my paycheck does not look right for this week. It's short, and I really can't "
       "figure out why. Can you look into that for me?",
    6: "Yeah, yeah, please. When will that show up for me? Will I get it right away?",
    8: "Okay. Well, while I have you, what is my PTO balance?",
    10: "And I forget how it accrues. When will I have enough to take ten solid days together?",
    12: "Okay, and then one more thing. We are expecting sometime in February. As the father, "
        "do I get paid time off?",
    14: "Okay. My wife is here. Could you just quickly recap everything we talked about, but do "
        "it in Spanish?",
    16: "Excellent. And, parlez-vous français?",
    18: "Okay, great. Thanks very much.",
}


def interp(text, expecting=""):
    return r.interpret_reply(text, expecting).to_dict()


class TestGoldenDialog:

    def test_line_2_pay(self):
        assert interp(GOLDEN[2])["intent"] == "pay"

    def test_line_6_consent_yes(self):
        out = interp(GOLDEN[6], "consent")
        assert out["consent"] == "yes"

    def test_line_8_pto(self):
        assert interp(GOLDEN[8])["intent"] == "pto"

    def test_line_10_pto_target_80(self):
        out = interp(GOLDEN[10], "next")
        assert (out["intent"], out["target_hours"]) == ("pto", "80")

    def test_line_12_leave_beats_paid_time_off(self):
        out = interp(GOLDEN[12])
        assert out["intent"] == "leave" and "pto" not in out["intents"].split(",")
        assert out["leave_topic"] == "parental"

    def test_line_14_recap_in_spanish(self):
        out = interp(GOLDEN[14])
        assert (out["intent"], out["recap_language"]) == ("recap", "es")
        assert out["wants_spanish"] == "no"  # one-off recap, not a switch for the call

    def test_line_16_french(self):
        out = interp(GOLDEN[16])
        assert (out["intent"], out["language_name"]) == ("language", "French")
        assert out["wants_spanish"] == "no"

    def test_line_18_close(self):
        assert interp(GOLDEN[18])["intent"] == "close"

    def test_lines_match_the_recording(self):
        path = "/Users/dgwartney/git/kore-agent-v2-bootcamp/agents/csv-hr-iva/research/aiquorum/data-CALL.json"
        try:
            with open(path) as fh:
                lines = json.load(fh)["lines"]
        except OSError:
            pytest.skip("recording not available on this machine")
        for idx, text in GOLDEN.items():
            assert lines[idx]["sp"] == "caller" and lines[idx]["text"] == text


class TestVarianceRows:

    @pytest.mark.parametrize("text", ["my check's light", "I got shorted", "missing hours",
                                      "My check is light", "mi cheque está corto"])
    def test_pay_paraphrases(self, text):
        assert interp(text)["intent"] == "pay"

    @pytest.mark.parametrize("text", ["no, leave it", "let me check with my manager",
                                      "Wait, don't correct it, let me check with my manager",
                                      "not now", "hold off", "nope", "no gracias",
                                      "todavía no", "wait."])
    def test_consent_no(self, text):
        assert interp(text, "consent")["consent"] == "no"

    def test_leave_it_and_check_with_are_not_intents(self):
        assert interp("no, leave it")["intent"] == "other"
        assert interp("let me check with my manager")["intent"] == "other"

    @pytest.mark.parametrize("text, topic", [
        ("Wait, which days?", "days"), ("Wait which days", "days"),
        ("which days were those?", "days"), ("Which days was that", "days"),
        ("Hang on, when was that?", "days"), ("how much is that again", "amount"),
        ("Hang on, is that before tax?", "other"), ("¿Cuáles días?", "days"),
        ("Hang on is that before tax as far as the money goes", "other"),
        ("how much is my take-home on that", "other"), ("is that gross or net?", "other"),
        ("¿Es antes de impuestos?", "other")])
    def test_barge_in_question_is_not_consent(self, text, topic):
        r = interp(text, "consent")
        assert (r["consent"], r["question_topic"]) == ("question", topic)

    @pytest.mark.parametrize("text", ["hmm", "the thing"])
    def test_consent_unclear(self, text):
        r = interp(text, "consent")
        assert (r["consent"], r["question_topic"]) == ("unclear", "")

    @pytest.mark.parametrize("text", ["sí, por favor", "go ahead", "yes, but when will I get it?",
                                      "sure, fix it", "claro"])
    def test_consent_yes(self, text):
        assert interp(text, "consent")["consent"] == "yes"

    def test_si_por_favor_is_spanish(self):
        assert interp("sí, por favor")["wants_spanish"] == "yes"

    @pytest.mark.parametrize("text, expecting, hours", [
        ("two weeks off", "", 80), ("five days", "pto_target", 40), ("five days", "", 40),
        ("40 hours", "pto_target", 40), ("a week", "pto_target", 40),
        ("ten solid days", "", 80), ("5 days", "", 40), ("I meant ten days, not ten hours", "", 80),
        ("diez días", "pto_target", 80), ("half a day", "", 8), ("2.5 days", "", 20)])
    def test_pto_targets(self, text, expecting, hours):
        out = interp(text, expecting)
        assert out["target_hours"] == str(hours) and out["intent"] == "pto"

    def test_parse_target_hours_directly(self):
        assert r.parse_target_hours("two weeks") == 80
        assert r.parse_target_hours("Thanksgiving") == 0

    def test_bare_hours_without_hint_is_pay(self):
        out = interp("40 hours")
        assert (out["intent"], out["target_hours"]) == ("pay", "40")

    @pytest.mark.parametrize("text", ["Can I talk to someone?", "W-2 reprint",
                                      "change my bank details", "Are you a robot?"])
    def test_other(self, text):
        assert interp(text)["intent"] == "other"

    @pytest.mark.parametrize("text", ["Okay.", "Okay, great.", "Yeah.", "Alright, got it!",
                                      "Mm, sounds good.", "Vale."])
    def test_bare_acknowledgment_is_ack(self, text):
        out = interp(text)
        assert (out["intent"], out["intents"]) == ("ack", "")

    def test_long_or_odd_input_is_not_ack(self):
        assert r.is_acknowledgment("m" * 5000 + "x") is False
        assert r.is_acknowledgment("okay " * 100) is False
        assert r.is_acknowledgment("") is False
        assert r.is_acknowledgment(" ,. ") is False

    def test_acknowledgment_keeps_consent_yes(self):
        assert interp("Okay.", "consent")["consent"] == "yes"

    @pytest.mark.parametrize("text", ["Okay, what is my PTO balance?", "Okay, great. Thanks very much.",
                                      "Okay, but is that before tax?"])
    def test_acknowledgment_with_more_is_not_ack(self, text):
        assert interp(text)["intent"] != "ack"

    def test_talk_to_someone_flags_human(self):
        assert interp("Can I talk to someone?")["wants_human"] == "yes"
        assert interp("W-2 reprint")["wants_human"] == "no"


class TestLeaveTopic:

    def test_recording_wording_is_parental(self):
        out = interp("My wife and I are expecting in February. As the father, "
                     "do I get paid time off?")
        assert (out["intent"], out["leave_topic"]) == ("leave", "parental")

    @pytest.mark.parametrize("text, topic", [
        ("Is there maternity leave?", "parental"), ("adoption leave", "parental"),
        ("how does FMLA work", "other"), ("bereavement leave", "other"),
        ("HSA enrollment dates", "other"), ("what's my PTO balance", ""), ("no, leave it", "")])
    def test_topics(self, text, topic):
        assert interp(text)["leave_topic"] == topic

    @pytest.mark.parametrize("text", list(GOLDEN.values()) + ["", "sí, por favor", "40 hours"])
    def test_every_field_is_a_string(self, text):
        assert all(isinstance(v, str) for v in interp(text).values())


class TestIntentRules:

    @pytest.mark.parametrize("text", ["", "   ", None])
    def test_none(self, text):
        out = r.interpret_reply(text).to_dict()
        assert out["intent"] == "none" and out["intents"] == "" and out["target_hours"] == ""

    def test_thanks_plus_pto_is_pto(self):
        assert interp("thanks, and what's my PTO")["intent"] == "pto"

    @pytest.mark.parametrize("text", ["that's all", "thank you", "bye", "goodbye", "that's it",
                                      "nothing else", "gracias", "adiós"])
    def test_close(self, text):
        assert interp(text)["intent"] == "close"

    @pytest.mark.parametrize("text", [
        "Gracias por la información. ¿Eso incluye los días que pedí recientemente?",
        "Gracias, ¿y eso cuándo se aplica?",
        "Thanks, does that include the days I already requested?",
        "thank you, and when does that start",           # voice transcript, no "?"
        "gracias, y cuando empieza eso",
        "Thanks. Is that before tax?"])
    def test_thanks_plus_question_is_not_close(self, text):
        assert interp(text)["intent"] == "other"

    @pytest.mark.parametrize("text", [
        "Gracias por la información. ¡Eso es todo por ahora!",
        "Okay, great. Thanks very much.", "thanks, bye", "gracias, adiós",
        "thank you, that's all I needed"])
    def test_thanks_without_question_is_close(self, text):
        assert interp(text)["intent"] == "close"

    def test_thanks_plus_duration_is_pto_target(self):
        out = interp("Gracias. ¿Y para tomar dos semanas?", expecting="next")
        assert (out["intent"], out["target_hours"]) == ("pto", "80")

    def test_two_intents_in_order_spoken(self):
        out = interp("My pay's short, and what's my PTO?")
        assert (out["intent"], out["pending_intent"]) == ("pay", "pto")
        out = interp("What's my PTO balance, and also my paycheck is short")
        assert (out["intent"], out["pending_intent"]) == ("pto", "pay")

    @pytest.mark.parametrize("text, intent", [
        ("how much vacation do I have", "pto"), ("¿cuántas vacaciones tengo?", "pto"),
        ("how do I enroll in the HSA", "leave"), ("am I eligible for FMLA", "leave"),
        ("licencia de paternidad", "leave"), ("bereavement leave", "leave"),
        ("my overtime is missing", "pay"), ("el pago está mal", "pay"),
        ("summarize that for me", "recap"), ("resumen por favor", "recap"),
        ("can you go over everything again", "recap"),
        ("do you speak Vietnamese?", "language"), ("Fala português?", "language"),
        ("do you speak Klingon", "language"), ("what's my hours", "pay"),
        ("adoption benefits and PTO balance", "leave")])
    def test_keywords(self, text, intent):
        assert interp(text)["intent"] == intent

    def test_benefits_and_pto_keep_both_without_family_words(self):
        out = interp("benefits question, then my PTO balance")
        assert out["intents"] == "leave,pto"


class TestLanguages:

    @pytest.mark.parametrize("text, name", [
        ("parlez-vous français?", "French"), ("do you speak French", "French"),
        ("do you speak Vietnamese?", "Vietnamese"), ("Fala português?", "Portuguese"),
        ("can you speak german", "German"), ("¿habla mandarín?", "Chinese"),
        ("do you speak klingon", "Klingon"), ("do you speak English?", ""),
        ("do you speak spanish", ""), ("hello", "")])
    def test_language_name(self, text, name):
        assert r.detect_language_name(text) == name

    def test_speaking_spanish_is_not_a_language_limit(self):
        out = interp("do you speak spanish?")
        assert out["intent"] == "other" and out["wants_spanish"] == "yes"

    @pytest.mark.parametrize("text, wants", [
        ("español", True), ("dos", True), ("Spanish, please", True),
        ("Hola, necesito ayuda con mi cheque", True), ("my paycheck is short", False),
        ("recap that in Spanish", False), ("no", False)])
    def test_wants_spanish(self, text, wants):
        assert interp(text)["wants_spanish"] == ("yes" if wants else "no")

    @pytest.mark.parametrize("text, lang", [
        ("recap in Spanish", "es"), ("resumen en español", "es"),
        ("No, English please", "en"), ("en inglés", "en"), ("recap please", "")])
    def test_recap_language(self, text, lang):
        assert interp(text)["recap_language"] == lang

    @pytest.mark.parametrize("text, intent, lang", [
        ("Could you explain that again in Spanish?", "recap", "es"),
        ("Say that again", "recap", ""),
        ("Can you go through everything again in English?", "recap", "en"),
        ("And again in Spanish, please", "recap", "es")])
    def test_recap_again_phrasing(self, text, intent, lang):
        out = interp(text)
        assert (out["intent"], out["recap_language"]) == (intent, lang)
        assert out["wants_spanish"] == "no"

    @pytest.mark.parametrize("text", ["Can we continue in Spanish?", "again", "in Spanish"])
    def test_spanish_switch_is_not_a_recap(self, text):
        out = interp(text)
        assert out["intent"] != "recap"
        assert out["wants_spanish"] == "yes" or text == "again"

    def test_fold(self):
        assert r.fold("  ESPAÑOL’s  ") == "espanol's"


class TestRouterServer:

    @pytest.fixture
    def server(self, tmp_path):
        return CvsHrRouterMCPServer(db_path=str(tmp_path / "keys.db"),
                                    cvs_hr_db_path=str(tmp_path / "cvs_hr.db"))

    @pytest.mark.asyncio
    async def test_tool_and_audit(self, server, tmp_path):
        async with Client(server.mcp) as client:
            assert {t.name for t in await client.list_tools()} == {"interpret_reply"}
            result = await client.call_tool("interpret_reply",
                                            {"text": GOLDEN[10], "expecting": "pto_target"})
        out = json.loads(result.content[0].text)
        assert set(out) == {"intent", "pending_intent", "intents", "consent", "question_topic", "target_hours",
                            "recap_language", "wants_spanish", "language_name", "wants_human",
                            "leave_topic", "expecting"}
        assert all(isinstance(v, str) for v in out.values())
        assert (out["intent"], out["target_hours"], out["expecting"]) == ("pto", "80", "pto_target")
        rows = CvsHrDatabase(str(tmp_path / "cvs_hr.db")).list_audit_events("cvs_hr_router")
        assert [(e["tool"], e["args"]["expecting"]) for e in rows] == [("interpret_reply", "pto_target")]
        assert rows[0]["verification_id"] is None

    def test_lazy_module_instance(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        import mcp_server_kit.cvs_hr_router as m
        assert m.server.mcp is m.mcp
