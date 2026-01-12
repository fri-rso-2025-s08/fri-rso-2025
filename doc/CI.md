# CI/CD

I was working with an Azure student account, which means I wasn't allowed to actually create an Azure app & service principal.
Because of this, I couldn't actually get the CI to run in a non-interactive environment, but I wrote a script that should theoretically work in Github actions if it was passed the proper credentials.

The script is split into two parts: the code part and the configuration part. Scroll down and you'll see the comment.
The configuration part is simply a function that builds a dependency DAG and calls the code part, which then executes it.

The CI is push-based, and the pipeline is triggered by git pushes. The tasks are filtered based on the diff and a few propagation rules:

- `A after B` means task A will always run after task B, although this doesn't affect propagation.
- `A triggered_by B` implies `A after B`, and also means that if `B` is scheduled to be run, `A` will be too.
- `A requires B` implies `A triggered_by B`, and also means that if `A` is scheduled to be run, `B` will be too.

By default, no tasks are scheduled to be run, but based on the diff, certain tasks are "activated".
The propagation rules then take over and build the complete task graph.
Note that all nodes are always present in the graph for ordering purposes.
The filtering only applies for execution.
