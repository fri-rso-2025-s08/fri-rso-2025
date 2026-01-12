# Architecture

The application consists of several microservices:

- Authentik for user management
- A global frontend, which redirects users to Authentik and proxies their requests to the correct tenant-specific backend
- A backend for managing and interacting with vehicles, accessible at `/api/vehicle_manager/<tenant>`
- Worker services that "connect" to vehicles, receive telemetry and pass it onto the manager, and send commands to the vehicles.
- A coordinator service that tells the worker services how to distribute their load.

TODO
