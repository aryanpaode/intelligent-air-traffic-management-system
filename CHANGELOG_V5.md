# Version 5 Changelog

## Why V5 was created

Independent validation of the Combined Disruption scenario found a better feasible schedule than V4:

- V4 result: AI222 at 10:15, weighted CSP cost 91.
- Independent exhaustive validator: AI222 at 10:13, weighted CSP cost 77.

The discrepancy was traced to V4's fixed **20-minute scheduling horizon**. In the globally better schedule, EK502 is assigned at 10:33, which is 21 minutes after its effective time of 10:12. V4 could not consider that value.

## V5 correction

V5 removes the arbitrary fixed horizon from the main optimizer.

The optimizer now:

1. Builds an unbounded feasible incumbent schedule.
2. Uses the incumbent objective cost to derive mathematically safe finite domains.
3. Searches with branch-and-bound, MRV and forward checking.
4. Can therefore consider later low-priority assignments when doing so protects a high-weight emergency flight.

Because all delay costs are non-negative, any single assignment whose weighted delay is already greater than or equal to the incumbent cost cannot participate in a strictly better schedule. This provides a finite objective-derived bound without a fixed time cutoff.

## Exact validation layer

For scenarios with exactly one open runway and at most eight flights, V5 also runs an **independent exhaustive permutation validator**. This is not part of the AI optimizer; it is a verification layer.

For Combined Disruption:

- permutations checked: 8! = 40,320
- exact weighted optimum: 77
- AI222 final runway time: 10:13
- AI222 CSP delay: 0 minutes
- AI222 total delay: 4 minutes

The branch-and-bound CSP optimizer and the exhaustive validator now agree.

## CSP comparison table

The existing Plain Backtracking / MRV / MRV + Forward Checking table remains a deliberately bounded **20-minute heuristic stress test**. It is kept separate from the exact V5 optimizer so the heuristic-comparison experiment remains reproducible.
