"""The evaluation question sets must not overlap, or held-out claims are void."""
from eval.ablation_questions import QUESTIONS as DEV
from eval.heldout_questions import QUESTIONS as H1
from eval.heldout2_questions import QUESTIONS as H2
from eval.heldout3_questions import QUESTIONS as H3


def _norm(text):
    return " ".join(text.lower().split())


def test_ids_unique_across_sets():
    ids = [q["id"] for q in DEV + H1 + H2 + H3]
    assert len(ids) == len(set(ids))


KNOWN_V1_DEV_OVERLAP = {
    "how many users have never placed an order?",
    "what is the total revenue from completed order items?",
    "how many users have placed more than 3 orders?",
}


def test_v1_overlap_with_dev_is_only_the_disclosed_three():
    dev = {_norm(q["question"]) for q in DEV}
    h1 = {_norm(q["question"]) for q in H1}
    assert dev & h1 == KNOWN_V1_DEV_OVERLAP


def test_v2_shares_no_question_with_any_other_set():
    h2 = {_norm(q["question"]) for q in H2}
    others = {_norm(q["question"]) for q in DEV + H1}
    assert not (h2 & others)


def test_every_question_has_reference_sql():
    for q in H1 + H2:
        assert q["reference_sql"].strip().lower().startswith("select")


def test_v3_shares_no_question_with_any_other_set():
    h3 = {_norm(q["question"]) for q in H3}
    others = {_norm(q["question"]) for q in DEV + H1 + H2}
    assert not (h3 & others)
    assert len(H3) == 30
