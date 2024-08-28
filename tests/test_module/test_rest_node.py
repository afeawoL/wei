"""
REST-based node that interfaces with WEI and provides various fake actions for testing purposes
"""

import time
from typing import Annotated

from fastapi import UploadFile
from fastapi.datastructures import State
from wei.modules.rest_module import RESTModule
from wei.types import StepFileResponse, StepResponse, StepStatus
from wei.types.module_types import (
    LocalFileModuleActionResult,
    Location,
    ModuleState,
    ValueModuleActionResult,
)
from wei.types.step_types import ActionRequest

# * Test predefined action functions


test_rest_node = RESTModule(
    name="test_rest_node",
    description="A test module for WEI",
    version="1.0.0",
    resource_pools=[],
    model="test_module",
    actions=[],
)
test_rest_node.arg_parser.add_argument(
    "--foo",
    type=float,
    help="The starting amount of foo",
    default=0.0,
)
test_rest_node.arg_parser.add_argument(
    "--bar",
    type=float,
    help="The starting amount of bar",
    default=0.0,
)


@test_rest_node.startup()
def test_node_startup(state: State):
    """Initializes the module"""
    state.foobar = state.foo + state.bar


@test_rest_node.state_handler()
def state_handler(state: State) -> ModuleState:
    """Handles the state of the module"""
    return ModuleState(status=state.status, error=state.error, foobar=state.foobar)


@test_rest_node.action()
def fail(state: State, action: ActionRequest) -> StepResponse:
    """Fails the current step"""
    return StepResponse.step_failed("Oh no! This step failed!")


@test_rest_node.action()
def transfer(
    state: State,
    action: ActionRequest,
    target: Annotated[Location[str], "the location to transfer to"],
    source: Annotated[Location[str], "the location to transfer from"] = "",
) -> StepResponse:
    """Transfers a sample from source to target"""
    time.sleep(5)
    return StepResponse.step_succeeded()


@test_rest_node.action()
def synthesize(
    state: State,
    action: ActionRequest,
    foo: Annotated[float, "The amount of foo to use"],
    bar: Annotated[float, "The amount of bar to use"],
    protocol: Annotated[UploadFile, "Python Protocol File"],
) -> StepResponse:
    """Synthesizes a sample using specified amounts `foo` and `bar` according to file `protocol`"""
    protocol = protocol.file.read().decode("utf-8")
    print(protocol)

    state.foobar = foo + bar
    time.sleep(5)
    return StepResponse.step_succeeded()


@test_rest_node.action(
    name="measure",
    results=[
        LocalFileModuleActionResult(label="test_file", description="a test file"),
        LocalFileModuleActionResult(
            label="test2_file", description="a second test file"
        ),
        ValueModuleActionResult(label="test", description="a test value result"),
    ],
)
def measure_action(state: State, action: ActionRequest) -> StepResponse:
    """Measures the foobar of the current sample"""
    with open("test.txt", "w") as f:
        f.write("test")
    with open("test2.txt", "w") as f:
        f.write("test")
    time.sleep(5)
    return StepFileResponse(
        StepStatus.SUCCEEDED,
        files={"test_file": "test.txt", "test2_file": "test2.txt"},
        data={"test": {"test": "test"}},
    )


if __name__ == "__main__":
    test_rest_node.start()
