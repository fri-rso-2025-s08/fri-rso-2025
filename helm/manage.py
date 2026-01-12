#!/usr/bin/env -S uv run --script
# /// script
# requires-python = "==3.14.*"
# dependencies = [
#     "pydantic>=2.12.5",
#     "pyyaml>=6.0.3",
# ]
# ///
# pyright: strict, reportUnknownArgumentType = false, reportUnknownLambdaType = false, reportUnknownVariableType = false


import json
import os
import subprocess
from argparse import ArgumentParser, Namespace
from collections import defaultdict
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from io import BufferedWriter
from pathlib import Path
from threading import Thread
from typing import Annotated, Any, Literal, cast

import yaml
from pydantic import BaseModel, BeforeValidator

type PsubWriter = Callable[[BufferedWriter], None]


@contextmanager
def with_psub(fn: PsubWriter):
    read_fd, write_fd = os.pipe()

    def buf_writer():
        with os.fdopen(write_fd, "wb") as pipe:
            fn(pipe)

    thread = Thread(target=buf_writer)
    thread.start()

    try:
        yield f"/dev/fd/{read_fd}", read_fd
    finally:
        thread.join()
        os.close(read_fd)


def literal_writer(data: str | bytes) -> PsubWriter:
    if isinstance(data, str):
        data = data.encode("utf-8")

    def fn(pipe: BufferedWriter):
        pipe.write(data)

    return fn


def json_writer(data: object) -> PsubWriter:
    return literal_writer(json.dumps(data))


type HelmValuesArg = Sequence[
    Path | str | Mapping[str, object] | Callable[[], Mapping[str, object]] | None
]


@contextmanager
def with_helm_values(values: HelmValuesArg):
    args: list[str] = []
    fds: list[int] = []

    with ExitStack() as stack:
        for value in values:
            args.append("-f")
            match value:
                case Path() | str():
                    args.append(str(value))
                case Mapping():
                    p, fd = stack.enter_context(with_psub(json_writer(value)))
                    args.append(p)
                    fds.append(fd)
                case Callable():
                    p, fd = stack.enter_context(
                        with_psub(lambda pipe, v=value: json_writer(v())(pipe))
                    )
                    args.append(p)
                    fds.append(fd)
                case None:
                    pass
        yield args, fds


@dataclass
class HelmRelease:
    ns: str
    chart: str
    release: str
    values: HelmValuesArg


def update_release(
    release: HelmRelease,
    ns_prefix: str,
    *,
    dry_run: bool = False,
    dry_run_server: bool = False,
):
    print(f"Upgrading {ns_prefix}{release.ns}.{release.release} ({release.chart})")

    with with_helm_values(release.values) as (values_args, values_fds):
        args = [
            "helm",
            "upgrade",
            release.release,
            release.chart,
            "--install",
            "--create-namespace",
            "--namespace",
            ns_prefix + release.ns,
            *values_args,
        ]
        if dry_run_server:
            args.append("--dry-run")
        if not dry_run:
            subprocess.check_call(
                args,
                pass_fds=values_fds,
            )


def get_prefixed_namespaces(prefix: str) -> list[str]:
    items = json.loads(
        subprocess.check_output(["kubectl", "get", "namespaces", "-o", "json"])
    )["items"]
    return [
        ns["metadata"]["name"]
        for ns in items
        if ns["metadata"]["name"].startswith(prefix)
    ]


def get_installed_releases(ns: str) -> list[str]:
    releases = json.loads(
        subprocess.check_output(["helm", "list", "-n", ns, "-o", "json", "-q"])
    )
    assert isinstance(releases, list)
    assert all(isinstance(x, str) for x in cast(list[Any], releases))
    return cast(list[str], releases)


def uninstall_release(
    ns: str,
    release: str,
    *,
    dry_run: bool = False,
    dry_run_server: bool = False,
):
    print(f"Uninstalling {ns}.{release}")
    args = ["helm", "uninstall", "-n", ns, release]
    if dry_run_server:
        args.append("--dry-run")
    if not dry_run:
        subprocess.check_call(args)


def delete_namespace(ns: str, *, dry_run: bool = False):
    print(f"Deleting namespace {ns}")
    args = ["kubectl", "delete", "namespace", ns]
    if not dry_run:
        subprocess.check_call(args)


@dataclass
class Env:
    config: "EnvConfig"
    path: Path
    name: str


def load_env(env_name: str) -> Env:
    path = Path("config") / env_name

    with open(path / "config.yaml") as f:
        config = EnvConfig.model_validate(yaml.safe_load(f))

    return Env(config, path, env_name)


def apply(
    *,
    ns_prefix: str,
    releases: Iterable[HelmRelease],
    filter: Collection[str] = (),
    uninstall_dangling: bool,
    dry_run: bool = False,
    dry_run_server: bool = False,
):
    desired_releases = defaultdict[str, dict[str, HelmRelease]](dict)
    releases_list = list(releases)
    for release in releases_list:
        ns_releases = desired_releases[ns_prefix + release.ns]
        assert release.release not in ns_releases
        ns_releases[release.release] = release

    for release in releases_list:
        if filter:
            fullrelease = f"{ns_prefix}{release.ns}.{release.release}"
            if not any(pat in fullrelease for pat in filter):
                continue
        update_release(
            release, ns_prefix, dry_run=dry_run, dry_run_server=dry_run_server
        )

    if not uninstall_dangling:
        return

    namespaces = get_prefixed_namespaces(ns_prefix)
    installed_releases = {
        ns: frozenset(get_installed_releases(ns)) for ns in namespaces
    }

    ns_to_remove: list[str] = []

    for ns, ns_release_ks in installed_releases.items():
        to_uninstall = ns_release_ks - frozenset(desired_releases[ns])
        for release_k in to_uninstall:
            uninstall_release(ns, release_k, dry_run=dry_run)
        if ns_release_ks == to_uninstall:
            ns_to_remove.append(ns)

    for ns in ns_to_remove:
        delete_namespace(ns, dry_run=dry_run)


def main_apply(parsed: Namespace):
    env = load_env(parsed.env)
    apply(
        ns_prefix=env.config.namespace_prefix + "-",
        releases=yield_releases(env),
        filter=parsed.filter,
        uninstall_dangling=parsed.uninstall_dangling,
        dry_run=parsed.dry_run,
        dry_run_server=parsed.dry_run_server,
    )


def main():
    parser = ArgumentParser()
    parser.add_argument("-d", "--dry-run", action="store_true")
    parser.add_argument("-D", "--dry-run-server", action="store_true")
    parser.add_argument("-e", "--env", required=True)
    subparsers = parser.add_subparsers(required=True)
    parser_apply = subparsers.add_parser("apply")
    parser_apply.set_defaults(_fn=main_apply)
    parser_apply.add_argument("-u", "--uninstall-dangling", action="store_true")
    parser_apply.add_argument("filter", nargs="*")
    parsed = parser.parse_args()

    os.chdir(Path(__file__).parent)
    parsed._fn(parsed)


def get_current_registry():
    return Path("../current_registry").read_text().strip()


def get_image_tag(env: Env, service_name: str):
    return (
        (Path("../src") / service_name / "latest_uploaded_tag" / env.name)
        .read_text()
        .strip()
    )


def get_image_name(env: Env, service_name: str):
    return f"{get_current_registry()}/{service_name}:{get_image_tag(env, service_name)}"


def maybe_read_env(value: Any) -> Any:
    if isinstance(value, dict) and "_env" in value:
        return os.environ[value["_env"]]
    return value


MaybeEnvValidator = BeforeValidator(maybe_read_env)
type MaybeEnvString = Annotated[str, MaybeEnvValidator]


##################
### ^^ CODE ^^ ###
##################
###   CONFIG   ###
##################


class EnvConfigTenant(BaseModel):
    manager_postgres_password: MaybeEnvString
    manager_postgres_admin_password: MaybeEnvString | None = None

    controller_heartbeat_interval: float = 1
    controller_heartbeat_missed_limit: int = 2


class EnvConfig(BaseModel):
    namespace_prefix: MaybeEnvString
    load_balancer_dns_label: MaybeEnvString | None = None
    letsencrypt_mode: Annotated[Literal["staging", "prod"], MaybeEnvString]

    authentik_host: MaybeEnvString
    authentik_secret: MaybeEnvString
    authentik_postgres_password: MaybeEnvString

    # Fill after creating your application in authentik
    oauth_issuer_url: MaybeEnvString
    oauth_jwks_url: MaybeEnvString
    oauth_client_id: MaybeEnvString
    oauth_client_secret: MaybeEnvString

    api_host: MaybeEnvString
    frontend_host: MaybeEnvString

    frontend_redis_password: MaybeEnvString

    tenants: dict[str, EnvConfigTenant]

    model_config = {"extra": "forbid"}


def yield_releases(env: Env) -> Iterable[HelmRelease]:
    p_shared = Path("values_shared")
    c = env.config

    yield HelmRelease(
        "ingress-nginx",
        "charts/ingress-nginx.tgz",
        "ingress-nginx",
        [
            p_shared / "ingress-nginx.yaml",
            {
                "controller": {
                    "service": {
                        "annotations": {
                            "service.beta.kubernetes.io/azure-dns-label-name": c.load_balancer_dns_label
                        }
                    }
                }
            }
            if c.load_balancer_dns_label is not None
            else None,
        ],
    )

    yield HelmRelease(
        "cert-manager",
        "charts/cert-manager.tgz",
        "cert-manager",
        [p_shared / "cert-manager.yaml"],
    )

    yield HelmRelease("global", "charts/cert-manager-issuer", "letsencrypt", [])

    ingress_annotations = {
        "cert-manager.io/cluster-issuer": f"{c.namespace_prefix}-global-letsencrypt-letsencrypt-{c.letsencrypt_mode}"
    }

    yield HelmRelease(
        "global",
        "charts/authentik.tgz",
        "authentik",
        [
            p_shared / "authentik.yaml",
            {
                "authentik": {
                    "secret_key": c.authentik_secret,
                    "postgresql": {"password": c.authentik_postgres_password},
                },
                "postgresql": {"auth": {"password": c.authentik_postgres_password}},
                "server": {
                    "ingress": {
                        "annotations": ingress_annotations,
                        "hosts": [c.authentik_host],
                        "tls": [
                            {
                                "hosts": [c.authentik_host],
                                "secretName": "authentik-tls",
                            }
                        ],
                    }
                },
            },
        ],
    )

    yield HelmRelease(
        "global",
        "charts/vehicle-manager-ingress",
        "vehicle-manager-proxy",
        [
            p_shared / "vehicle-manager-ingress.yaml",
            {
                "annotations": ingress_annotations,
                "host": c.api_host,
                "tenants": [
                    {
                        "id": k,
                        "prefix": "/api/vehicle_manager/",
                        "targetNamespace": f"{c.namespace_prefix}-tenant-{k}",
                        "targetService": "vehicle-manager",
                        "targetPort": 80,
                    }
                    for k in c.tenants
                ],
            },
        ],
    )

    yield HelmRelease(
        "frontend",
        "charts/redis.tgz",
        "redis",
        [
            p_shared / "redis.yaml",
            {"auth": {"password": c.frontend_redis_password}},
        ],
    )

    yield HelmRelease(
        "frontend",
        "../src/frontend/chart",
        "frontend",
        [
            p_shared / "frontend.yaml",
            {
                "image": {"name": get_image_name(env, "frontend")},
                "ingress": {
                    "annotations": ingress_annotations,
                    "host": c.frontend_host,
                },
                "env": {
                    "REDIS_URL": f"redis://:{c.frontend_redis_password}@redis-master:6379",
                    "OAUTH_ISSUER_URL": c.oauth_issuer_url,
                    "OAUTH_CLIENT_ID": c.oauth_client_id,
                    "OAUTH_CLIENT_SECRET": c.oauth_client_secret,
                    "OAUTH_ORIGIN": f"https://{c.frontend_host}",
                    "BACKEND_URL": f"https://{c.api_host}",
                },
            },
        ],
    )

    for k, tenant in c.tenants.items():
        yield HelmRelease(
            f"tenant-{k}",
            "charts/postgres.tgz",
            "postgres",
            [
                p_shared / "postgres.yaml",
                {
                    "auth": {
                        "password": tenant.manager_postgres_password,
                        "postgresPassword": tenant.manager_postgres_admin_password,
                    }
                },
            ],
        )

        yield HelmRelease(
            f"tenant-{k}",
            "charts/nats.tgz",
            "nats",
            [p_shared / "nats.yaml"],
        )

        yield HelmRelease(
            f"tenant-{k}",
            "../src/vehicle-manager/chart",
            "vehicle-manager",
            [
                p_shared / "vehicle-manager.yaml",
                {
                    "image": {"name": get_image_name(env, "vehicle-manager")},
                    "env": {
                        "DATABASE_URL": f"postgresql+asyncpg://vehicletrack:{tenant.manager_postgres_password}@postgres-postgresql:5432/vehicletrack",
                        "TENANT_ID": k,
                        "OAUTH_ISSUER_URL": c.oauth_issuer_url,
                        "OAUTH_JWKS_URL": c.oauth_jwks_url,
                        "OAUTH_CLIENT_ID": c.oauth_client_id,
                        "NATS_URL": "nats://@nats:4222",
                    },
                },
            ],
        )

        yield HelmRelease(
            f"tenant-{k}",
            "../src/vehicle-controller/chart",
            "vehicle-controller",
            [
                p_shared / "vehicle-controller.yaml",
                {
                    "image": {"name": get_image_name(env, "vehicle-controller")},
                    "sharedEnv": {"NATS_URL": "nats://@nats:4222"},
                    "coordinator": {
                        "env": {
                            "HEARTBEAT_INTERVAL": str(
                                tenant.controller_heartbeat_interval
                            ),
                            "HEARTBEAT_MISSED_LIMIT": str(
                                tenant.controller_heartbeat_missed_limit
                            ),
                        },
                    },
                },
            ],
        )


if __name__ == "__main__":
    main()
