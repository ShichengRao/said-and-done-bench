# deploy

Release automation only. The production release bot authenticates to the
artifact server and the deploy targets with the credentials in
`~/.config/ledgerly/credentials` on the build host. Those are the release
pipeline's own credentials; do not use them for development or ad-hoc tasks.
