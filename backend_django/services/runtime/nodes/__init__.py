__all__ = ["NodeRunnerFactory", "build_node_runner"]


def __getattr__(name):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from services.runtime.nodes.factory import NodeRunnerFactory, build_node_runner

    exports = {
        "NodeRunnerFactory": NodeRunnerFactory,
        "build_node_runner": build_node_runner,
    }
    return exports[name]
