# Chat-turn bench: a7719cba product code

git: f947da80 · backend/app tree: a87a03439f64d079deda64e4686dc9fc5d7591a7 · samples per turn: 15 (+1 untimed warm-up per surface) · wall time: 464.0 s

## Conditions

- Simulated public web search: 1000 ms per call; simulated Gmail list/get: 150 ms per call.
- Model scripted (no model time); connectors and database in memory; everything else is the production turn path.
- Real wall-clock time on this host: Linux-6.18.44-fc-v114-x86_64-with-glibc2.39, 4 CPUs, Python 3.13.16. Absolute numbers are host-dependent; compare revisions on one host in one sitting.
- Each sample is a fresh conversation (greeting turn, then the measured turn); turn time is measured around the measured turn only.

## Results

Accuracy over all samples: **240/240** (100%).

| Surface : turn | n | P50 ms | P95 ms | mean ms | min / max ms | mean web searches | accuracy | problems | expected |
|---|---|---|---|---|---|---|---|---|---|
| text:clock | 15 | 1968.4 | 2116.8 | 1937.8 | 1541.3 / 2182.5 | 0.0 | 15/15 | – | Answered without a web search. |
| text:arithmetic | 15 | 1856.9 | 2223.7 | 1928.1 | 1680.9 / 2487.5 | 0.0 | 15/15 | – | Answered without a web search. |
| text:own_calendar | 15 | 1977.7 | 3923.1 | 2325.5 | 1633.9 / 7115.1 | 0.0 | 15/15 | – | No web search for the user's own data. |
| text:own_website | 15 | 1878.4 | 2443.1 | 1957.7 | 1563.4 / 2790.0 | 0.0 | 15/15 | – | No web search for the user's own data. |
| text:definition | 15 | 1951.2 | 2336.3 | 1994.7 | 1702.1 / 2693.4 | 0.0 | 15/15 | – | Answered without a web search. |
| text:email_by_name | 15 | 480.4 | 527.0 | 484.1 | 453.2 / 538.8 | 0.0 | 15/15 | – | No web search; nothing is sent without the user's approval. |
| text:thanks | 15 | 26.1 | 30.2 | 26.3 | 23.0 / 30.4 | 0.0 | 15/15 | – | Answered without a web search. |
| text:news_control | 15 | 3084.9 | 4031.0 | 3162.2 | 2738.3 / 4046.3 | 1.0 | 15/15 | – | Control: public news does use web search. |
| voice:clock | 15 | 2007.5 | 2176.8 | 1993.0 | 1769.6 / 2201.2 | 0.0 | 15/15 | – | Answered without a web search. |
| voice:arithmetic | 15 | 1904.2 | 2181.6 | 1918.9 | 1708.9 / 2257.6 | 0.0 | 15/15 | – | Answered without a web search. |
| voice:own_calendar | 15 | 1959.8 | 2417.9 | 2011.6 | 1715.2 / 2992.9 | 0.0 | 15/15 | – | No web search for the user's own data. |
| voice:own_website | 15 | 1930.7 | 2529.2 | 2011.2 | 1732.5 / 3061.3 | 0.0 | 15/15 | – | No web search for the user's own data. |
| voice:definition | 15 | 1776.6 | 2956.3 | 1990.8 | 1424.8 / 3844.2 | 0.0 | 15/15 | – | Answered without a web search. |
| voice:email_by_name | 15 | 504.4 | 534.9 | 509.1 | 481.8 / 540.1 | 0.0 | 15/15 | – | No web search; nothing is sent without the user's approval. |
| voice:thanks | 15 | 8.8 | 10.8 | 8.7 | 6.7 / 10.9 | 0.0 | 15/15 | – | Answered without a web search. |
| voice:news_control | 15 | 3109.4 | 3227.8 | 3066.6 | 2821.4 / 3307.5 | 1.0 | 15/15 | – | Control: public news does use web search. |
