# Verifying a release in production

A deploy is done when the running system shows the change working, not when the script exits.

1. **Running revision**: read what each service actually runs (container image id or label, version
   endpoint, process start time) and compare it with the commit you built. A peer can retag
   `:latest`; never infer the revision from a binary's strings or the script's output.
2. **Health**: each service's health check and its log since the restart: no new errors, crash loops or
   migration failures.
3. **Cutoff**: write down the restart time. Only events after it count; earlier rows prove nothing.
4. **First real events**: read the first production events the change touches (requests, jobs, calls,
   rows written) as soon as a few exist. Name what each event means and the observation that would
   show the change failing. Zero events is "not yet exercised", never a pass.
5. **User-visible check**: load the page or call the endpoint the change was for. A browser still on
   the old bundle needs a reload; say so.
6. **Watching longer**: a background monitor (the project's monitor lifecycle when it has one) with
   a brief naming the exact queries and log greps and the cutoff; read its log on demand, never poll
   from the session.
7. **Report**: revision per service with its evidence, health, the events checked with counts, and
   what is not yet exercised.
