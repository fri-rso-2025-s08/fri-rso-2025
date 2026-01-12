# Helm

The `/helm` directory contains the bulk of the deployment configuration:

- `manage.py`: Another standalone Python script split into code and configuration. This one runs tasks sequentially, those tasks being `helm update --install` and possibly `helm uninstall` with `kubectl delete namespace`.
- `charts`: Contains both vendored charts with a `./pull.sh` script for updates, and charts that are scoped to the entire deployment rather than a single microservice.
- `config`: Contains [environment](ENVIRONMENT.md) specific configuration.
- `values_shared`: Implementation detail. Contains some yaml snippets that aren't environment-specific.
