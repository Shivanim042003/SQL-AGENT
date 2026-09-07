
**Further update, same session:** after revising SYSTEM_PROMPT with explicit
efficiency guidance (prefer conditional DISTINCT aggregation, avoid GROUP BY
over the full events table), re-ran the conversion-rate question in isolation.
Result: generated the ORIGINAL denominator bug again (WHERE event_type IN
(cart, purchase) filtering the base table), executing in 14.1s (confirming
the efficiency guidance did reduce runtime) but returning the wrong answer
(42.06%) on a first attempt, with no retry involved. This is not a regression
introduced by tonight's prompt change -- it is direct evidence that
sql_generator.py's correctness on this specific question has always been
non-deterministic: across this session it produced the verified-correct
query at least 3 times and this exact wrong query at least 4 times, with no
prompt version tested tonight eliminating the variance.

**Conclusion:** the actual safety guarantee for this system is not "the
generator usually gets it right" -- it is the retry loop + Critic layer
specifically. Tonight's Critic-reliability finding (3 confirmed false
negatives on correct SQL) is therefore the more urgent gap to close before
this pipeline can be trusted, not generator prompt-tuning, which has genuine
diminishing returns at this point.


**Further confirmation:** across 4 independent full-graph runs of "What is
the conversion rate?", the generator reached MAX_RETRIES (2) and failed
every time, producing a different wrong SQL shape on each of the ~12 total
attempts (denominator-filtering, UNION with mismatched branches, inner JOIN
collapsing numerator=denominator, cross join causing timeout). Simpler
questions ("how many events are there?") succeed reliably and consistently
across repeated runs. This sharpens the earlier "non-deterministic" framing:
it is not that the system is unreliable in general -- it is specifically
unreliable on this one class of subtle-denominator aggregate question, on
this local model. All 4 failures were handled safely: no wrong answer was
ever returned, and format_answer produced an honest failure message each
time. Recommended next step: capture this exact question in the Phase D
golden set as a known-hard case with an honest expected outcome, rather than
continuing to manually re-run it.
