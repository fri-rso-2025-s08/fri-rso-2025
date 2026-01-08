#!/usr/bin/env -S uv run --script
# /// script
# requires-python = "==3.14.*"
# ///
# pyright: strict

import argparse
import os
import subprocess
from collections import defaultdict
from collections.abc import Callable, Collection, Iterable, Sequence
from contextlib import chdir
from dataclasses import dataclass, field
from fnmatch import fnmatch
from functools import cache
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
    if diff_from == "git":
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
    fn: Callable[[], None]
    wants: Collection[str] = field(default=(), kw_only=True)
    requires: Collection[str] = field(default=(), kw_only=True)
    autorun: bool = field(default=False, kw_only=True)


def build_task_lists(
    tasks: Iterable[Task],
) -> Iterable[Sequence[tuple[str, Callable[[], None]]]]:
    g_full = {v.name: v for v in tasks}
    g_inv = defaultdict[str, set[str]](set)

    for k, v in g_full.items():
        for k_u in v.wants:
            g_inv[k_u].add(k)
        for k_u in v.requires:
            g_inv[k_u].add(k)

    autorun_or_propagated = set[str]()

    def add_k_deps(k: str):
        if k in autorun_or_propagated:
            return
        autorun_or_propagated.add(k)
        for k_u in g_full[k].requires:
            add_k_deps(k_u)

    def add_k(k: str):
        if k in autorun_or_propagated:
            return
        add_k_deps(k)
        for rdep in g_inv[k]:
            add_k(rdep)

    for k, v in g_full.items():
        if v.autorun:
            add_k(k)

    ts = TopologicalSorter(
        {
            k: {
                k_u
                for k_u in chain(g_full[k].wants, g_full[k].requires)
                if k_u in autorun_or_propagated
            }
            for k in autorun_or_propagated
        }
    )
    ts.prepare()
    while ts.is_active():
        ready = ts.get_ready()
        yield [(k, g_full[k].fn) for k in ready]
        ts.done(*ready)


def task_noop():
    print("--skip-azure passed, not running this step")


def task_terraform():
    with chdir("terraform"):
        cmd("./init.sh")
        cmd("tofu", "apply", "-auto-approve")


def task_helm():
    pass


def yield_tasks(diff_fnames: Collection[str], *, skip_azure: bool) -> Iterable[Task]:
    fnm = cache(fnmatch)

    def any_globs(*pats: str):
        return any(fnm(fname, pat) for pat in pats for fname in diff_fnames)

    yield Task(
        "terraform",
        task_noop if skip_azure else task_terraform,
        autorun=any_globs("terraform/*"),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--dry-run", action="store_true")
    parser.add_argument("--skip-azure", action="store_true")
    parser.add_argument("diff_from")
    parsed = parser.parse_args()

    os.chdir(Path(__file__).parent)

    for tasks in build_task_lists(
        yield_tasks(
            set(get_diff_fnames(parsed.diff_from)),
            skip_azure=parsed.skip_azure,
        )
    ):
        for k, fn in tasks:
            print(f"### Running task: {k} ###")
            if not parsed.dry_run:
                fn()


if __name__ == "__main__":
    main()
