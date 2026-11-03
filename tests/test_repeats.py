"""Repeated phrases in the flow of speech (user 2026-11-03, lesson08): each pattern found, and the walkthrough's
deliberate repetition ('loop counter ki value kya hogi? 1 ... 2') and ordinary sentences are left alone."""
from ytpipe import repeats

LESSON08 = [
    (15.42, "To aaj ki video ke andar main aapko bataunga ek chhota sa example hai, ya ek bada interesting task hai, ya ek problem hai, loop ko samajhne ke liye. Theek hai ji?"),
    (44.75, "5 into 1, 5 into 2,"), (50.17, "5 into 10 tak, 50 tak."),
    (66.31, "To agar is problem ko, ya is case ke liye agar main sochoon,"),
    (82.53, "Meri ye cheezein jo vary kar rahi hain,"),
    (84.95, "par ye jo hai, ye boloon ki mera ye jo cheez hai, ye loop counter ki tarah behave kar raha hai."),
    (117.55, "Ab ye loop counter chalaana kab tak hai ji?"), (120.83, "Ye loop counter chalaana hai"),
    (122.83, "jab tak loop counter less than equal to 10."),
    (128.55, "Ab jaise print karna hai: print kya karna hai? Print kya karna hai ji?"),
    (177.00, "ye agar main waise loon, to main kind of"), (182.78, "isko main kind of string ke andar leta hoon."),
    (243.40, "Theek hai ji. Loop counter initialise kar diya maine: loop counter is time ke upar initialise ho gaya, 1 ke upar ho gaya."),
    (271.88, "Loop counter ki value kya hogi? 1. Equal to: jo inka multiply karke aayega, 5."),
    (280.00, "Phir se ye chala. Loop counter ki value kya hogi? 2. Loop counter less than equal to 10?"),
    (286.00, "To number into loop counter: 5 into 2, as a string, is equal to"),
    (345.83, "Without repetitively likhte hue, maine ek for loop chalayi hai, 1 se lekar 10 tak, aur ye mera kaam kar rahi hai."),
    (380.39, "Business logic aur understand the problem: to aap agar able ho ki aap uska flowchart bana sakte ho,")]

def test_lesson08_repeats_are_found_and_nothing_else():
    found = {(f["face"], f["pattern"]) for f in repeats.find([{"face": a, "text": b} for a, b in LESSON08])}
    assert found == {(15.42, "restatement"), (66.31, "restatement"), (84.95, "filler"), (120.83, "echo"),
                     (128.55, "doubled"), (177.00, "false start"), (243.40, "reworded")}

def test_cut_lines_are_skipped_and_report_written(tmp_path):
    rows = [{"face": 1.0, "text": "—cut— print kya karna hai? print kya karna hai"}, {"face": 5.0, "text": "Hello programmers."}]
    assert repeats.find(rows) == []
    p = repeats.report([], str(tmp_path / "r.md")); assert "None found." in open(p).read()
