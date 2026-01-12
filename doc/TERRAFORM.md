# Terraform

The `/terraform` directory contains two components: a bootstrap config and a deployment config.
The bootstrap config is meant to provision a storage account which will be used to store the state of the deployment.
All the scripts are hardcoded to use OpenTofu (works on my machine™), so make an alias in your `$PATH` or install it.

## Bootstrapping

Make sure you're logged into `az`, and set your subscription ID in the root `.env.local` file.
Then initialize the bootstrap subdirectory (`/terraform/bootstrap`) and run `./run.sh <env> apply` (did you read [ENVIRONMENT.md](ENVIRONMENT.md)?).

## Deployment

The `/terraform/main` directory contains configs an AKS cluster and an ACR registry. See the tasks inside `/ci.py` for usage.
Generally, you run `./init.sh <env>`, then `./run.sh <env> apply`, and finally `./login.sh <env>` to log into the cluster and registry.
