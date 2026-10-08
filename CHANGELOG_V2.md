# V2 Change Log

- Added interactive SVG airspace/radar visualization.
- Added live aircraft contacts coloured by inferred priority.
- Added visual runway open/closed state near the airport.
- Added blocked-weather and risk-zone visualization.
- Search paths can now be overlaid on the radar.
- Added per-algorithm **Show** controls for BFS/UCS/Greedy/A*.
- Added **Search Contrast** scenario where BFS/Greedy choose a 30.0-cost route while UCS/A* choose a 12.5-cost route.
- Added lowest-cost / fewest-nodes tags and explanatory route insight.
- Fixed route dropdown defaults to NORTH -> AIRPORT.
- Added airspace graph serialization and persisted last route comparison.
- Expanded automated tests from 4 to 6; all pass.
