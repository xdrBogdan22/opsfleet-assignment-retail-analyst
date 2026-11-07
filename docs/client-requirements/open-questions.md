# Client questions

The client answered the first three questions on 2026-11-08. The others keep their
working defaults until answered.

## Answered

| Question | Answer | Effect on the design |
|---|---|---|
| How many users and queries do you expect, and at what peak? | About 100 active managers a day, about 10 questions and 1 saved report each. Tens to a few hundred executives, few active at the same time. Data grows by about 1M rows a day. | Small Cloud Run and Cloud SQL instances. Partitioned fact tables. See P22. |
| What cost per query or per user is acceptable, and what response time? | About $1 per question, easy to configure, design only. Simple questions in 10 to 30 seconds, long reports in 1 to 2 minutes. No time-to-first-token target. | Configurable cost and time limits. See P10. |
| Must the model be open source or self-hosted? | No. Prefer newer Gemini models. Testing uses a free Gemini key, so stay within free-tier limits, at roughly 2 to 5 model calls per question. Fall back between Gemini models only, with other providers in config but switched off. | At most 5 model calls per question. Gemini-only fallback chain. See P4, P10, P12 and P17. |

## Open

| Question | Why it matters | Working default |
|---|---|---|
| Are there data residency requirements? | Sets the cloud region | Single EU or US region |
| What does "products related to him" mean? | Sets the access rule | Brand |
| How do you define revenue and churn? | Changes results | Stated in `docs/02-architecture.md` |
| What minimum group size applies to demographics? | Sets the privacy rule | 10 customers |
| Should reports be recoverable after deletion? | Changes the delete design | Permanent deletion |
