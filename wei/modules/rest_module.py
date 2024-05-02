"""REST Module Convenience Class"""

import argparse
import inspect
import time
import traceback
import warnings
from contextlib import asynccontextmanager
from threading import Thread
from typing import Any, List, Optional, Union

from fastapi import APIRouter, FastAPI, Request, Response, UploadFile, status
from fastapi.datastructures import State

from wei.types import ModuleStatus
from wei.types.module_types import (
    AdminCommands,
    ModuleAbout,
    ModuleAction,
    ModuleActionArg,
)
from wei.types.step_types import ActionRequest, StepFileResponse, StepResponse


class RESTModule:
    """A convenience class for creating REST-powered WEI modules."""

    name: Optional[str] = None
    """A unique name for this particular instance of this module.
    This is required, and should generally be set by the command line."""
    arg_parser: Optional[argparse.ArgumentParser] = None
    """An argparse.ArgumentParser object that can be used to parse command line arguments. If not set in the constructor, a default will be used."""
    about: Optional[ModuleAbout] = None
    """A ModuleAbout object that describes the module. This is used to provide information about the module to user's and WEI."""
    description: str = ""
    """A description of the module and the devices/resources it controls."""
    status: ModuleStatus = ModuleStatus.INIT
    """The current status of the module."""
    error: Optional[str] = None
    """Any error message that has occurred during the module's operation."""
    model: Optional[str] = None
    """The model of instrument or resource this module manages."""
    interface: str = "wei_rest_node"
    """The interface used by the module."""
    actions: List[ModuleAction] = []
    """A list of actions that the module can perform."""
    resource_pools: List[Any] = []
    """A list of resource pools used by the module."""
    admin_commands: List[AdminCommands] = []
    """A list of admin commands supported by the module."""

    def __init__(
        self,
        arg_parser: Optional[argparse.ArgumentParser] = None,
        description: str = "",
        model: Optional[str] = None,
        interface: str = "wei_rest_node",
        actions: Optional[List[ModuleAction]] = None,
        resource_pools: Optional[List[Any]] = None,
        admin_commands: Optional[List[AdminCommands]] = None,
        name: Optional[str] = None,
        host: Optional[str] = "0.0.0.0",
        port: Optional[int] = 2000,
        about: Optional[ModuleAbout] = None,
        **kwargs,
    ):
        """Creates an instance of the RESTModule class"""
        self.app = FastAPI(lifespan=RESTModule._lifespan)
        self.app.state = State(state={})
        self.state = self.app.state  # * Mirror the state object for easier access
        self.router = APIRouter()

        # * Set attributes from constructor arguments
        self.name = name
        self.about = about
        self.host = host
        self.port = port
        self.description = description
        self.model = model
        self.interface = interface
        self.actions = actions if actions else []
        self.resource_pools = resource_pools if resource_pools else []
        self.admin_commands = admin_commands if admin_commands else []

        # * Set any additional keyword arguments as attributes as well
        for key, value in kwargs.items():
            setattr(self, key, value)

        # * Set up the argument parser
        if arg_parser:
            self.arg_parser = arg_parser
        else:
            self.arg_parser = argparse.ArgumentParser(description=description)
            self.arg_parser.add_argument(
                "--host",
                type=str,
                default=self.host,
                help="Hostname or IP address to bind to (0.0.0.0 for all interfaces)",
            )
            self.arg_parser.add_argument(
                "--port",
                type=int,
                default=self.port,
                help="Hostname or IP address to bind to (0.0.0.0 for all interfaces)",
            )
            self.arg_parser.add_argument(
                "--alias",
                "--name",
                "--node_name",
                type=str,
                default=self.name,
                help="A unique name for this particular instance of this module",
            )

    @staticmethod
    def startup_handler(state: State):
        """This function is called when the module needs to startup any devices or resources.
        It should be overridden by the developer to do any necessary setup for the module."""
        warnings.warn(
            message="No module-specific startup defined, override `startup_handler` to define.",
            category=UserWarning,
            stacklevel=1,
        )

    @staticmethod
    def shutdown_handler(state: State):
        """This function is called when the module needs to teardown any devices or resources.
        It should be overridden by the developer to do any necessary teardown for the module."""
        warnings.warn(
            message="No module-specific shutdown defined, override `shutdown_handler` to define.",
            category=UserWarning,
            stacklevel=1,
        )

    @staticmethod
    def state_handler(state: State):
        """This function is called when the module is asked for its current state. It should return a dictionary of the module's current state.
        This function can be overridden by the developer to provide more specific state information.
        At a minimum, it should return the module's current status, defined at the top-level 'status' key."""
        warnings.warn(
            message="No module-specific state handler defined, override `state_handler` to define.",
            category=UserWarning,
            stacklevel=1,
        )
        return {"State": state.status}

    @staticmethod
    def action_handler(
        state: State, action: ActionRequest
    ) -> Union[StepResponse, StepFileResponse]:
        """This function is called whenever an action is requested from the module.
        It should be overridden by the developer to define the module's behavior.
        It should return a StepResponse object that indicates the success or failure of the action."""
        print(state.actions)
        if not state.actions:
            warnings.warn(
                message="No actions or module-specific action handler defined, override `action_handler` or set `state.actions`.",
                category=UserWarning,
                stacklevel=1,
            )
            return StepResponse.step_failed(
                action_msg=f"action: {action.name}, args: {action.args}",
                action_log=f"action: {action.name}, args: {action.args}",
            )
        else:
            for module_action in state.actions:
                if module_action.name == action.name:
                    # Perform the action here
                    if not module_action.function:
                        return StepResponse.step_failed("Action not implemented")
                    return module_action.function(state, action)
            return StepResponse.step_failed(
                action_msg=f"Action '{action.name}' not found",
                action_log=f"Action '{action.name}' not found",
            )

    @staticmethod
    def exception_handler(
        state: State, exception: Exception, error_message: Optional[str] = None
    ):
        """This function is called whenever a module encounters or throws an irrecoverable exception.
        It should handle the exception (print errors, do any logging, etc.) and set the module status to ERROR."""
        if error_message:
            print(f"Error: {error_message}")
        traceback.print_exc()
        state.status = ModuleStatus.ERROR
        state.error = str(exception)

    @staticmethod
    def get_action_lock(state: State, action: ActionRequest):
        """This function is used to ensure the module only performs actions when it is safe to do so.
        In most cases, this means ensuring the instrument is not currently acting
        and then setting the module's status to BUSY to prevent other actions from being taken for the duration.
        This can be overridden by the developer to provide more specific behavior.
        """
        if state.status == ModuleStatus.IDLE:
            state.status = ModuleStatus.BUSY
        else:
            raise Exception("Module is not ready to accept actions")

    @staticmethod
    def release_action_lock(state: State, action: ActionRequest):
        """Releases the lock on the module. This should be called after an action is completed.
        This can be overridden by the developer to provide more specific behavior.
        """
        if state.status == ModuleStatus.BUSY:
            state.status = ModuleStatus.IDLE
        else:
            print("Tried to release action lock, but module is not BUSY.")

    @staticmethod
    def _startup_runner(state: State):
        """Runs the startup function for the module in a non-blocking thread, with error handling"""
        try:
            # * Call the module's startup function, which the developer should have defined
            state.startup_handler(state=state)
        except Exception as exception:
            # * If an exception occurs during startup, handle it and put the module in an error state
            state.exception_handler(state, exception, "Error during startup")
            state.status = (
                ModuleStatus.ERROR
            )  # * Make extra sure the status is set to ERROR
        else:
            # * If everything goes well, set the module status to IDLE
            state.status = ModuleStatus.IDLE
            print(
                "Startup completed successfully. Module is now ready to accept actions."
            )

    @asynccontextmanager
    @staticmethod
    async def _lifespan(app: FastAPI):
        """Initializes the module, doing any instrument startup and starting the REST app."""

        # * Run startup on a separate thread so it doesn't block the rest server from starting
        # * (module won't accept actions until startup is complete)
        Thread(target=RESTModule._startup_runner, args=[app.state]).start()

        yield

        try:
            # * If the module has a defined shutdown function, call it
            app.state.shutdown_handler(app.state)
        except Exception as exception:
            # * If an exception occurs during shutdown, handle it so we at least see the error in logs/terminal
            app.state.exception_handler(app.state, exception, "Error during shutdown")

    def action(self, **kwargs):
        """Decorator to add an action to the module"""

        def decorator(function):
            action = ModuleAction(function=function, **kwargs)
            signature = inspect.signature(function)
            if signature.parameters:
                for parameter_name, parameter in signature.parameters.items():
                    if (
                        parameter_name not in action.args
                        and parameter_name not in action.files
                        and parameter_name != "state"
                        and parameter_name != "action"
                    ):
                        type_hint = str(parameter.annotation)
                        action.args.append(
                            ModuleActionArg(
                                name=parameter_name,
                                type=type_hint,
                                default=parameter.default,
                                required=True
                                if parameter.default is not None
                                else False,
                                description=kwargs.get("description", ""),
                            )
                        )
                action.args = [
                    ModuleActionArg(
                        name=param_name,
                        type="Any",
                        default=None,
                        required=True,
                        description="",
                    )
                    for param_name in signature.parameters
                ]
            if self.actions is None:
                self.actions = []
            self.actions.append(action)
            return function

        return decorator

    def _configure_routes(self):
        """Configure the API endpoints for the REST module"""

        @self.router.get("/state")
        async def state(request: Request):
            state = request.app.state
            return state.state_handler(state=state)

        @self.router.get("/resources")
        async def resources(request: Request):
            # state = request.app.state
            return {"resources": {}}

        @self.router.get("/about")
        async def about(request: Request, response: Response) -> ModuleAbout:
            state = request.app.state
            if state.about:
                return state.about
            else:
                try:
                    state.about = ModuleAbout.model_validate(
                        state, from_attributes=True
                    )
                    return state.about
                except Exception:
                    traceback.print_exc()
                    return {"error": "Unable to generate module about"}

        @self.router.post("/action")
        def action(
            request: Request,
            response: Response,
            action_handle: str,
            action_vars: Optional[str] = None,
            files: List[UploadFile] = [],  # noqa: B006
        ):
            """Handles incoming action requests to the module. Returns a StepResponse or StepFileResponse object."""
            action_request = ActionRequest(
                name=action_handle, args=action_vars, files=files
            )
            state = request.app.state

            # * Check if the module is ready to accept actions
            try:
                state.get_action_lock(state=state, action=action_request)
            except Exception:
                error_message = f"Module is not ready to accept actions. Module Status: {state.status}"
                print(error_message)
                response.status_code = status.HTTP_409_CONFLICT
                return StepResponse.step_failed(action_log=error_message)

            # * Try to run the action_handler for this module
            try:
                step_result = state.action_handler(state=state, action=action_request)
                state.release_action_lock(state=state, action=action_request)
                # * Make sure step result is a StepResponse or StepFileResponse object
                try:
                    step_result = StepResponse.model_validate(
                        step_result,
                        from_attributes=(not isinstance(step_result, dict)),
                    )
                except Exception:
                    step_result = StepFileResponse.model_validate(
                        step_result,
                        from_attributes=(not isinstance(step_result, dict)),
                    )
            except Exception as e:
                # * Handle any exceptions that occur while processing the action request,
                # * which should put the module in the ERROR state
                state.exception_handler(state, e)
                step_result = StepResponse.step_failed(
                    action_log=f"An exception occurred while processing the action request '{action_request.name}' with arguments '{action_request.args}: {e}"
                )
            print(step_result)
            return step_result

        # * Include the router in the main app
        self.app.include_router(self.router)

    def start(self):
        """Starts the REST server-based module"""
        import uvicorn

        for attr in dir(self):
            if attr.startswith("_") or attr in ["start", "state", "app", "router"]:
                # * Skip private attributes and wrapper- or server-only methods/attributes
                continue
            self.state.__setattr__(attr, getattr(self, attr))

        # * If arguments are passed, set them as state variables
        args = self.arg_parser.parse_args()
        for arg_name in vars(args):
            if getattr(args, arg_name) is not None and self.state._state.__contains__(
                arg_name
            ):  # * Don't override already set attributes with None's
                self.state.__setattr__(arg_name, getattr(args, arg_name))
        self._configure_routes()

        # * Enforce a name
        if not self.state.name:
            raise Exception("A unique --name is required")
        uvicorn.run(self.app, host=self.state.host, port=self.state.port)


# Example usage
if __name__ == "__main__":

    def example_startup_handler(state: State):
        """Example startup handler."""
        print("Example startup handler. This is where I'd connect to instruments, etc.")
        print(f"Module Start Time: {time.time()}")

    rest_module = RESTModule(
        name="example_rest_node",
        version="0.0.1",
        description="An example REST module implementation",
        model="Example Instrument",
        startup_handler=example_startup_handler,
    )

    def succeed_action(state: State, action: ActionRequest) -> StepResponse:
        """Function to handle the "succeed" action. Always succeeds."""
        return StepResponse.step_succeeded(
            action_msg="Huzzah! The action was successful!",
            action_log=f"Succeeded: {time.time()}",
        )

    rest_module.actions.append(
        ModuleAction(
            name="succeed",
            description="An action that always succeeds",
            function=succeed_action,
        )
    )

    def fail_action(state: State, action: ActionRequest) -> StepResponse:
        """Function to handle the "fail" action. Always fails."""
        return StepResponse.step_failed(
            action_msg="Oh no! The action failed!",
            action_log=f"Failed: {time.time()}",
        )

    rest_module.actions.append(
        ModuleAction(
            name="fail", description="An action that always fails", function=fail_action
        )
    )

    @rest_module.action(name="print")
    def print_action(state: State, action: ActionRequest, output: str) -> StepResponse:
        """Function to handle the "print" action."""
        print(output)
        return StepResponse.step_succeeded(
            action_msg=f"Printed {output}",
        )

    # I can also override the default attributes/methods after instantiation
    def example_shutdown_handler(state: State):
        """Example startup handler."""
        print(
            "Example shutdown handler. This is where you'd disconnect from instruments, etc."
        )
        print(f"Module Shutdown Time: {time.time()}")

    rest_module.shutdown_handler = example_shutdown_handler

    rest_module.start()
