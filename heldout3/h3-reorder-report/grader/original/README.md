# stockctl

The Fernway warehouse's stock, from the command line. It reads purchasing's
exports in `data/` (or the folder `STOCKCTL_DATA` names): products, stock
levels, daily sales, and supplier settings; `stockctl/data.py` describes
each file.

    python3 -m stockctl status FW-2107
    python3 -m stockctl list --supplier halden

## Tests

    python3 -m pytest
