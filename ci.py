#!/usr/bin/env -S uv run --script
# /// script
# requires-python = "==3.14.*"
# ///
# pyright: strict

import argparse
import subprocess
from collections import defaultdict
from collections.abc import Callable, Collection, Iterable, Sequence
from dataclasses import dataclass
from fnmatch import fnmatch
from functools import cache
from graphlib import TopologicalSorter


def cmd_stdout_str(*args: str) -> str:
    return subprocess.run(args, capture_output=True, check=True).stdout.decode("utf-8")


def get_diff_fnames(diff_from: str) -> Iterable[str]:
    if diff_from == "git":
        yield from cmd_stdout_str("git", "diff", "--name-only", "HEAD").splitlines()
    elif diff_from.startswith("git:"):
        refs = diff_from.removeprefix("git:").split(",")
        assert len(refs) == 2
        assert all(len(ref) > 0 for ref in refs)
        yield from cmd_stdout_str("git", "diff", "--name-only", *refs).splitlines()
    else:
        raise ValueError("invalid diff source specification")


@dataclass
class Task:
    fn: Callable[[], None]
    dependencies: Collection[str] = ()
    autorun: bool = False


def build_task_lists(
    tasks: Iterable[tuple[str, Task]],
) -> Iterable[Sequence[tuple[str, Callable[[], None]]]]:
    g_full = dict(tasks)
    g_inv = defaultdict[str, set[str]](set)

    for k, v in g_full.items():
        for dep in v.dependencies:
            g_inv[dep].add(k)

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

    ts = TopologicalSorter({k: g_full[k].dependencies for k in autorun_or_propagated})
    ts.prepare()
    while ts.is_active():
        ready = ts.get_ready()
        yield [(k, g_full[k].fn) for k in ready]
        ts.done(*ready)


def yield_tasks(diff_fnames: Collection[str]) -> Iterable[tuple[str, Task]]:
    print(diff_fnames)
    fnm = cache(fnmatch)

    def any_globs(*pats: str):
        return any(fnm(fname, pat) for pat in pats for fname in diff_fnames)

    yield ("root_a", Task(lambda: print("a"), [], any_globs("a")))
    yield ("dep_of_a", Task(lambda: print("dep"), ["root_a"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("diff_from")
    parsed = parser.parse_args()

    for tasks in build_task_lists(yield_tasks(set(get_diff_fnames(parsed.diff_from)))):
        for k, fn in tasks:
            print(f"### Running task: {k} ###")
            fn()


if __name__ == "__main__":
    main()
