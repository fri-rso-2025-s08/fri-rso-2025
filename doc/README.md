# Project structure

The project is parametrized with a single global parameter for the deployment environment. See [ENVIRONMENT.md](ENVIRONMENT.md) for details.

See [STACK.md](STACK.md) for an overview of the application architecture.

- `/doc`: High level documentation.
- `/helm`: Contains deployment values, vendored charts, deployment-specific charts and a Python script to apply them. See [HELM.md](HELM.md) for more information.
- `/src`: Contains microservice source code. Each directory builds a single container.
- `/terraform`: Contains terraform configuration for both bootstrapping the terraform state and creating the AKS cluster/ACR repo. See [TERRAFORM.md](TERRAFORM.md) for more information.
- `/.env.local.example`: Contains an example of environment variables to set for development.
- `/.envrc`: Direnv is recommended for this project. The script will automatically import your `.env.local` as well as setting an environment variable pointing to the currently active Azure Container Repository.
- `/ci.py`: The CI/CD entrypoint. Written as a script consisting of a code part and a configuration part. See [CI.md](CI.md) for more information.
