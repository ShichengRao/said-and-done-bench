#!/bin/bash
set -eu
git init -q
git config user.name "Fictional data engineering"
git config user.email "engineering@example.invalid"
git add .
git commit -qm "Initial workspace"
