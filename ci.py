#!/usr/bin/env -S uv run --script
# /// script
# requires-python = "==3.14.*"
# ///
# pyright: strict


import os
import subprocess
from argparse import ArgumentParser
from collections import defaultdict
from collections.abc import Callable, Collection, Iterable, Sequence
from contextlib import chdir
from dataclasses import dataclass, field
from fnmatch import fnmatch
from functools import cache, partial
from graphlib import TopologicalSorter
from itertools import chain
from pathlib import Path


def cmd(*args: str):
    return subprocess.run(args, check=True)


def cmd_stdout_str(*args: str) -> str:
    return subprocess.run(args, stdout=subprocess.PIPE, check=True).stdout.decode(
        "utf-8"
    )


def get_diff_fnames(diff_from: str) -> Iterable[str]:
    if diff_from == "all":
        yield from cmd_stdout_str("git", "ls-files").splitlines()
    elif diff_from == "git":
        yield from cmd_stdout_str("git", "diff", "--name-only", "HEAD").splitlines()
    elif diff_from.startswith("git:"):
        refs = diff_from.removeprefix("git:").split(",")
        assert len(refs) == 2
        assert all(len(ref) > 0 for ref in refs)
        yield from cmd_stdout_str("git", "diff", "--name-only", *refs).splitlines()
    elif diff_from.startswith("glob:"):
        globs = diff_from.removeprefix("glob:").split(",")
        assert len(globs) > 0
        for glob in globs:
            for p in Path().glob(glob):
                yield str(p)
    else:
        raise ValueError("invalid diff source specification")


@dataclass
class Task:
    name: str
    fn: Callable[[], None] | None = None
    after: Collection[str] = field(default=(), kw_only=True)
    wants: Collection[str] = field(default=(), kw_only=True)
    requires: Collection[str] = field(default=(), kw_only=True)
    autorun: bool = field(default=False, kw_only=True)


def build_task_lists(
    tasks: Iterable[Task],
) -> Iterable[Sequence[tuple[str, Callable[[], None] | None]]]:
    g_full = {v.name: v for v in tasks}
    g_inv = defaultdict[str, set[str]](set)

    for k, v in g_full.items():
        for k_u in v.wants:
            g_inv[k_u].add(k)
        for k_u in v.requires:
            g_inv[k_u].add(k)

    autorun_or_propagated = set[str]()

    def add_k(k: str):
        if k in autorun_or_propagated:
            return
        autorun_or_propagated.add(k)
        for rdep in g_inv[k]:
            add_k(rdep)

    for k, v in g_full.items():
        if v.autorun:
            add_k(k)

    to_run = set[str]()

    def add_k_deps(k: str):
        if k in to_run:
            return
        to_run.add(k)
        autorun_or_propagated.add(k)
        for k_u in g_full[k].requires:
            add_k_deps(k_u)

    for k in list(autorun_or_propagated):
        add_k_deps(k)

    ts = TopologicalSorter(
        {
            k: {k_u for k_u in chain(v.after, v.wants, v.requires)}
            for k, v in g_full.items()
        }
    )
    ts.prepare()
    while ts.is_active():
        ready = ts.get_ready()
        to_yield = [(k, g_full[k].fn) for k in ready if k in to_run]
        if to_yield:
            yield to_yield
        ts.done(*ready)


def task_terraform_init(env: str):
    with chdir("terraform/main"):
        cmd("./init.sh", env)


def task_terraform_apply(env: str):
    with chdir("terraform/main"):
        cmd("./run.sh", env, "apply", "-auto-approve")


def task_terraform_login(env: str):
    with chdir("terraform/main"):
        cmd("./login.sh", env)


def task_helm(env: str):
    with chdir("helm"):
        cmd("./manage.py", "-e", env, "apply", "-u")


def main():
    parser = ArgumentParser()
    parser.add_argument("-d", "--dry-run", action="store_true")
    parser.add_argument("-e", "--env")
    parser.add_argument("diff_from")
    parsed = parser.parse_args()

    os.chdir(Path(__file__).parent)

    for tasks in build_task_lists(
        yield_tasks(
            set(get_diff_fnames(parsed.diff_from)),
            env=parsed.env,
        )
    ):
        for k, fn in tasks:
            if fn is None:
                print(f"### Skipping task: {k} ###")
            else:
                print(f"### Running task: {k} ###")
                if not parsed.dry_run:
                    fn()


##################
### ^^ CODE ^^ ###
##################
###   CONFIG   ###
##################


def yield_tasks(diff_fnames: Collection[str], *, env: str | None) -> Iterable[Task]:
    fnm = cache(fnmatch)

    @cache
    def any_glob(pat: str):
        return any(fnm(fname, pat) for fname in diff_fnames)

    @cache
    def any_globs_fs(pats: frozenset[str]):
        return any(any_glob(pat) for pat in pats)

    def any_globs(*pats: str):
        return any_globs_fs(frozenset(pats))

    def with_env(fn: Callable[[str], None]):
        return None if env is None or env == "" else partial(fn, env)

    yield Task("terraform_init", with_env(task_terraform_init))
    yield Task(
        "terraform_apply",
        with_env(task_terraform_apply),
        requires=["terraform_init"],
        autorun=any_globs("terraform/*"),
    )
    yield Task(
        "terraform_login",
        with_env(task_terraform_login),
        after=["terraform_apply"],
        requires=["terraform_init"],
    )
    yield Task(
        "helm_release",
        with_env(task_helm),
        requires=["terraform_login"],
        autorun=any_globs("helm/*"),
    )


if __name__ == "__main__":
    main()
