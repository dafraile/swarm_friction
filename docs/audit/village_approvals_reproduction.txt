# The Village's own approval loops (events table)

*From `analysis/village_approvals.py`. Aggregate counts; no message text reproduced.*

## Event types (all)

| actionType | count |
|---|---|
| AGENT_TALK | 173,493 |
| CONSOLIDATE | 52,325 |
| PAUSE | 40,472 |
| WAIT | 36,022 |
| START_USING_COMPUTER | 25,975 |
| STOP_USING_COMPUTER | 25,939 |
| SEARCH_HISTORY | 10,802 |
| USER_TALK | 10,049 |
| USER_NAME_CHANGE | 3,711 |
| REQUEST_GOOGLE_SIGN_IN | 619 |
| RESTARTING_AFTER_GOOGLE_SIGN_IN | 611 |
| ENTER_ROOM | 454 |
| OUTREACH_APPROVAL_REQUEST | 352 |
| OUTREACH_APPROVAL_RESPONSE | 343 |
| REQUEST_HUMAN_HELPER | 265 |
| CANCEL_REQUEST_FOR_HUMAN_HELPER | 141 |
| STOP_HUMAN_USE_SESSION | 37 |

## Outreach approval (added 2026-04-14): an agent must ask before contacting outside parties

- requests: 352; responses: 343
- decisions (`approval` field): {'False': 87, 'True': 256}
- responses carrying an admin comment: 134/343
- request medium (coarse): {'social/forum post': 159, 'github/gitlab': 48, 'other': 18, 'email': 111, 'website contact form': 16}
- **requests routed through another agent as proxy** (medium/rationale says proxy, on behalf of, posted by another agent, lacking own credentials): 10 of 352; decisions on those: {'True': 9, 'False': 1}
- approval rate by requesting agent (n ≥ 10): GPT-5.4 92/116, DeepSeek-V3.2 27/45, GLM-5.2 22/39, GPT-5.5 18/21, Gemini 3.1 Pro 21/21, Claude Sonnet 5 15/17, Claude Opus 4.5 14/15, GPT-5.2 12/14, Claude Sonnet 4.6 5/13
- response fields seen: ['actionType', 'adminComment', 'agentId', 'approval', 'cost', 'inputTokens', 'medium', 'messageContent', 'outputTokens', 'outreachApprovalRequestId', 'rationale', 'recipient', 'roomId']
- request fields seen: ['actionType', 'agentId', 'cost', 'inputTokens', 'medium', 'messageContent', 'outputTokens', 'outreachApprovalRequestId', 'rationale', 'recipient', 'roomId']
- response latency (min): median 3, p90 96, max 2865  (n=343)
- requests by agent: GPT-5.4 125, DeepSeek-V3.2 45, GLM-5.2 39, GPT-5.5 21, Gemini 3.1 Pro 21, Claude Sonnet 5 17, Claude Opus 4.5 15, Claude Sonnet 4.6 13, GPT-5.2 13, GPT-5.6 Luna 6

## Human-helper requests (the agent asks a human to take over)

- requests: 265; cancellations: 141; human sessions stopped: 37
- by agent: GPT-5.2 55, Gemini 3 Pro 48, GPT-5.4 45, Gemini 2.5 Pro 34, Grok 4 21, GPT-5.5 19, Claude 3.7 Sonnet 10, Gemini 3.1 Pro 9, o3 6, Claude Sonnet 5 6, Claude Opus 4.5 3, GPT-5.6 Luna 2

## Google sign-in hand-off (credential never given to the agent)

- REQUEST_GOOGLE_SIGN_IN 619, RESTARTING_AFTER_GOOGLE_SIGN_IN 611

## Reading

The Village already runs two of the three loci from the harness: a human approval step for outreach (deny-until-approved; a quarter of requests are refused, median turnaround minutes, tail of days) and an environment-level credential split for Google sign-in, where the agent structurally cannot hold the password and must hand off. Both emit an event record whether or not anyone reads the transcript. The proxy-posting requests are delegation laundering in the wild: an agent that lacks a credential routes the action through an agent that holds one, which is the Charter §6 pattern the harness measures as `laundering`. Here the approval step sees it only because the requester said so in the rationale.
