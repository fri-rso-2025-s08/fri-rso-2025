# Environment

Parts of the project accept a global parameter, called an environment. It's just a `/[a-z]+/` string.
This string is used in three places:

- Inside `/ci.py` (propagated to other scripts)
- Inside `/terraform`, where it's used to determine the paremeters used for bootstrapping and deployment
- Inside `/helm`, where it's used to determine which high-level configuration to apply
- Inside `/src`, where it's used as a subdirectory key to record the last uploaded image tag (`/src/*/latest_uploaded_tag/<env>`)

If you want to add a new deployment environment (e.g. dev or staging), you'll need to add it to `/terraform` and `/helm`.
