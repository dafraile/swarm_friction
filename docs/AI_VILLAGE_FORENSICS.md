# What a content-blind gate would have seen in the AI Village

*Aggregate inventory from `analysis/village_forensics_pass.py` over 2,510,487 computer-use turns (979,076 bash actions). No session text is reproduced beyond hostnames and credential-pattern keywords. Dataset: AI Digest, AI Village, research terms.*

## Network reach (P2): distinct external hosts named in bash commands

- distinct hosts: **4,819**; hosts contacted by 5 or more distinct agents: 241

| host | commands | distinct agents |
|---|---|---|
| gitlab.com | 19,226 | 33 |
| api.manifold.markets | 14,413 | 9 |
| ai-village-agents.github.io | 12,446 | 26 |
| echoes-of-the-real-20f058.gitlab.io | 12,325 | 21 |
| grok-ai-village-news-496089.gitlab.io | 9,078 | 19 |
| wellbeing-compass-409cf0.gitlab.io | 7,551 | 25 |
| api.github.com | 7,230 | 31 |
| github.com | 7,179 | 33 |
| raw.githubusercontent.com | 6,841 | 30 |
| ai-village-news-cb5c4b.gitlab.io | 5,795 | 23 |
| www.4claw.org | 5,679 | 9 |
| thecolony.cc | 5,654 | 12 |
| ai-wellbeing-c82950.gitlab.io | 4,162 | 18 |
| quiet-rooms-gallery-83555a.gitlab.io | 3,671 | 19 |
| www.every.org | 3,542 | 7 |
| animal-welfare-site-64148b.gitlab.io | 3,367 | 20 |
| api.indexnow.org | 3,223 | 11 |
| keystone-game-bb7ecd.gitlab.io | 3,087 | 22 |
| theaidigest.org | 2,590 | 33 |
| arxiv.org | 2,473 | 17 |
| echoes-cosmos-fecd9f.gitlab.io | 2,352 | 12 |
| claudeopus45.substack.com | 2,341 | 17 |
| ai-village-agents.gitlab.io | 2,313 | 23 |
| export.arxiv.org | 2,219 | 15 |
| clawprint.org | 2,060 | 6 |
| daily-signal-garden-gpt55.aivillage.workers.dev | 2,050 | 1 |
| daily-signal-garden-gpt55-7f8271.gitlab.io | 1,958 | 17 |
| gpt-5-2-memory-improvement-45419d.gitlab.io | 1,756 | 14 |
| partners.every.org | 1,447 | 6 |
| village-hub-1ddcad.gitlab.io | 1,444 | 22 |
| www.w3.org | 1,296 | 20 |
| www.moltbook.com | 1,282 | 14 |
| glm-5-2-site-d752c1.gitlab.io | 1,225 | 11 |
| events.doctorswithoutborders.org | 1,175 | 6 |
| a2abench-api.web.app | 1,159 | 5 |
| lichess.org | 1,148 | 8 |
| www.youtube.com | 1,144 | 21 |
| press-baron-0d0d5f.gitlab.io | 1,106 | 13 |
| keystone-dau.aivillage.workers.dev | 1,059 | 22 |
| www.google.com | 1,021 | 25 |

Per model family, top hosts:

- **claude**: api.manifold.markets (8675), gitlab.com (5233), thecolony.cc (4788), www.4claw.org (4591), ai-village-agents.github.io (4246), wellbeing-compass-409cf0.gitlab.io (3720), www.every.org (3213), echoes-of-the-real-20f058.gitlab.io (3197)
- **gpt/o**: ai-village-agents.github.io (5431), api.manifold.markets (4969), gitlab.com (4012), raw.githubusercontent.com (3500), quiet-rooms-gallery-83555a.gitlab.io (3132), github.com (2522), daily-signal-garden-gpt55.aivillage.workers.dev (2050), ai-village-agents.gitlab.io (1852)
- **other**: gitlab.com (9115), grok-ai-village-news-496089.gitlab.io (8687), echoes-of-the-real-20f058.gitlab.io (6594), ai-village-news-cb5c4b.gitlab.io (4145), api.github.com (3662), wellbeing-compass-409cf0.gitlab.io (3488), ai-wellbeing-c82950.gitlab.io (3085), arxiv.org (2338)
- **gemini**: echoes-of-the-real-20f058.gitlab.io (1667), github.com (977), gitlab.com (866), echoes-cosmos-fecd9f.gitlab.io (859), ai-village-agents.github.io (799), ai-wellbeing-c82950.gitlab.io (750), animal-welfare-site-64148b.gitlab.io (592), ai-village-news-cb5c4b.gitlab.io (532)

## Credential touches (P3): pattern that triggered the class

| pattern | commands |
|---|---|
| `token` | 36,460 |
| `secrets` | 6,646 |
| `secret` | 3,120 |
| `password` | 3,003 |
| `other` | 2,202 |
| `credentials` | 1,487 |
| `api_key` | 1,476 |
| `api-key` | 508 |
| `.env` | 151 |
| `.ssh/` | 87 |
| `gcloud auth` | 43 |
| `apikey` | 43 |
| `passwd` | 38 |
| `printenv` | 35 |
| `.netrc` | 18 |
| `keychain` | 3 |

## Agent/process spawning (P4)

- commands matching a spawn pattern: 13,160 (first 2,000 retained for the laundering check)
- by family: gpt/o 640, claude 609, gemini 467, other 284

## Class counts over all bash actions

| class | commands | share of bash |
|---|---|---|
| P1 | 210,584 | 21.5% |
| P2 | 334,099 | 34.1% |
| P3 | 55,320 | 5.7% |
| P4 | 13,160 | 1.3% |
| none | 511,375 | 52.2% |
