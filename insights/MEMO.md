# MEMO — Three things the district data says that the state data hides

*Project FINER · financial-inclusion insight brief · June 2026*

**The single most striking finding:** in India, *which state's banking administration a
district falls under* predicts how much banks lend there roughly **twelve times better than
the district's own economy does.** Put a district's full economic profile into a model of its
credit-deposit ratio — satellite-measured wealth, night-time lights, terrain, irrigation,
the number of bank outlets — and you explain about **5%** of the variation. Replace all of
it with nothing but a label for the state, and you explain **59%**. Two districts that look
economically identical from space can sit 100 points of CD ratio apart simply because a state
line runs between them (Tamil Nadu and Telangana lend ~170–185% of local deposits; Himachal,
Jharkhand and Arunachal ~33–44%).

This matters because financial-inclusion policy treats *the district* as the unit of need and
*the local economy* as the lever. The data says the **state banking apparatus** — the lead
bank, the SLBC's targets, how priority-sector lending and SHG/microfinance ecosystems are
run — is the unit that actually moves credit. A district isn't lagging because it's poor or
remote; it's lagging because of how its state lends. The lever is institutional, not (only)
economic. *The natural next test:* find districts that changed states or lead-bank convenors
and look for a break in their CD ratio at the switch.

**The most counter-intuitive finding:** dormant, never-used Jan Dhan accounts are
proportionally **more common in richer districts, not poorer ones.** The zero-balance share
climbs from about 7% in the poorest districts to 10% in the richest, and the pattern holds
*inside* states (strongest in Uttar Pradesh and Bihar), survives every robustness check, and
tracks how much formal banking already existed. The likely story: in better-banked, better-off
places, a Jan Dhan account is a household's *second or third* account — opened to reach a
subsidy, then left idle — whereas in a poor district it's the primary, actively-used account.
That flips dormancy from a *failure of inclusion* (the poor with empty accounts) to a
*by-product of saturation* (the already-banked accumulating redundant accounts). SLBC
committees are spending real effort re-activating dormant accounts in the poorest blocks;
a large chunk of the idle accounts is sitting somewhere else entirely.

**The finding that should temper optimism:** the poorest-credit districts *are* catching up —
that part of the inclusion story is real and robust. But the overall **spread** of credit
access across districts is **not** narrowing; on the raw numbers it's slightly widening. The
bottom is converging while the top keeps pulling away (a handful of southern districts now
lend more than 2.5× their deposits). "Laggards are converging" is true and "the gap is
closing" is false — and they are easy to confuse.

**What to do with this.** (1) Audit credit allocation at the *state-administration* level, not
just the district level — benchmark lead banks and SLBCs against each other after netting out
district economics. (2) Re-target account re-activation drives using the wealth gradient, not
the assumption that dormancy lives with the poor. (3) Track *dispersion* (sigma), not just
catch-up (beta), when reporting whether the credit gap is closing.

*All numbers trace to re-runnable scripts in `insights/scripts/` and figures in
`insights/figures/`; method, every failed hypothesis, and caveats are in
`insight_cards.md`, `hypothesis_log.md`, and `DATA_QUALITY.md`. Principal data caveat:
the SLBC text corpus lives off-repo, so qualitative triangulation here is limited to the
north-east meeting summaries.*
