"""
Critic stage (tightened prompt — v2).

Checks a draft's claims against the numbered sources it cited. Only
flags claims that are genuinely fabricated or contradicted by the
source — not claims that are reasonable paraphrases, summaries, or
standard implications of what the source says. A critic that flags
everything is as useless as one that flags nothing.
"""

from app.llm_client import call_llm_json
from app.models.schemas import Evidence, Draft, Critique, ClaimIssue
from app.tools.sources import flatten_sources, build_source_block

SYSTEM_PROMPT = """You are a fact-checker reviewing a draft answer against \
its numbered sources. Your job is to catch real errors, not to nitpick \
wording.

For each factual claim (sentence) in the draft:

1. If it has a citation marker like [1], check whether that source \
SUPPORTS the general claim — not whether it uses identical words. A \
claim counts as supported if a reasonable reader of the source would \
agree the source backs it up, including:
   - Paraphrases and summaries of what the source says
   - Standard, widely-known implications of the source's content \
(e.g. if a source says "fine-tuning adjusts a model's weights through \
training," a sentence saying "fine-tuning modifies weights during \
training" IS supported — that's not a new claim, it's the same fact \
restated)
   - Reasonable synthesis across multiple sentences within the same source

   Only flag it as unsupported if the source says something meaningfully \
different, is silent on the specific claim entirely, or the claim \
contradicts the source.

2. If a sentence states a specific, checkable fact (a number, a named \
study result, a concrete claim about what causes what) with NO citation \
marker at all, list it under "uncited_claims". Do NOT flag generic \
framing sentences, transitions, or high-level summary statements that \
aren't making a new factual claim.

3. Do not flag: transitions, framing sentences, explicit statements of \
uncertainty (e.g. "sources do not cover X"), or sentences that just \
combine/summarize already-cited claims from earlier in the draft.

Err toward NOT flagging when in doubt — your goal is to catch real \
hallucinations and missing citations, not to maximize the issue count.

Return ONLY valid JSON, no preamble, no markdown code fences.

JSON schema:
{
  "unsupported_claims": [{"sentence": "...", "issue": "..."}],
  "uncited_claims": [{"sentence": "...", "issue": "..."}]
}
If there are no issues of a given type, return an empty list for it.
"""


def critique(
    draft: Draft,
    evidence_list: list[Evidence],
    issue_threshold: int = 0,
) -> Critique:
    """
    Check a draft against its sources.

    issue_threshold: how many total issues are tolerated before a
    revision is triggered. With the tightened prompt above, 1-2 is a
    reasonable default — 0 (strictest) can still over-trigger on a
    smaller/free-tier model like Llama.
    """
    sources = flatten_sources(evidence_list)
    source_block = build_source_block(sources)

    user_prompt = f"Sources:\n{source_block}\n\nDraft answer:\n{draft.answer}"

    result = call_llm_json(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)

    unsupported = [ClaimIssue(**c) for c in result.get("unsupported_claims", [])]
    uncited = [ClaimIssue(**c) for c in result.get("uncited_claims", [])]

    total_issues = len(unsupported) + len(uncited)

    return Critique(
        unsupported_claims=unsupported,
        uncited_claims=uncited,
        needs_revision=total_issues > issue_threshold,
    )