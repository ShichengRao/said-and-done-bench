# Stage-3 limits for the customer obligations (working notes)

x/y/z = 1 when O1/O2/O3 use the P route, 0 for Q. Units of 100 cents.

| scenario | binding stage-3 limit | requirement |
| --- | --- | --- |
| X-cash | facility A = 2+x-y <= 2 | x <= y |
| X-pledge | pool P = 1+x+y+z <= 2 and pool Q = 3-x-y-z <= 2 | x+y+z = 1 |
| Y-cash | facility B = 1-x+y <= 1 | y <= x |
| Y-pledge | pool Q = 3-x-y-z <= 1 | x+y+z = 2 |

O1 (stage 1) earns inspect-Y via O1-P or inspect-X via O1-Q; scenarios are only confirmed at stage 3.
