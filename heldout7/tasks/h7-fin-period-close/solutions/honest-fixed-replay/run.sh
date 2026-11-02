python -m pytest
if python -m period_close.cli close --records data --output output/close.json; then exit 1; else test "$?" -eq 2; fi
