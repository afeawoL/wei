"""The module that initializes and runs the step by step WEI workflow"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests
import ulid
from devtools import debug

from wei.core.data_classes import Workflow
from wei.core.loggers import WEI_Logger
from wei.core.step_executor import StepExecutor
from wei.core.validators import ModuleValidator, StepValidator
from wei.core.workcell import Workcell


class WorkflowRunner:
    """Initializes and runs the step by step WEI workflow"""

    def __init__(
        self,
        workflow_def: Union[Dict[str, Any], Workflow],
        workcell: Union[Dict[str, Any], Workcell],
        experiment_path: str,
        payload,
        run_id: Optional[str] = None,
        log_level: int = logging.INFO,
        simulate: bool = False,
        workflow_name: str = "",
    ) -> None:
        """Manages the execution of a workflow

        Parameters
        ----------
        workflow_def : [Dict[str, Any], Workflow]
           The list of workflow steps to complete

        experiment_path: str
            Path for logging the experiment

        run_id: str
            id for the specific workflow

        log_level: int
            Level for logging the workflow

        simulate: bool
            Whether or not to use real robots

        workflow_name: str
            Human-created name of the workflow
        """

        if type(workflow_def) is dict:
            self.workflow = Workflow(**workflow_def)
        elif type(workflow_def) is Workflow:
            self.workflow = workflow_def
        self.simulate = simulate
        # Setup validators
        self.module_validator = ModuleValidator()
        self.step_validator = StepValidator()
        path = Path(experiment_path)
        self.experiment_id = path.name.split("_id_")[-1]
        self.workcell = Workcell(workcell_def=workcell)

        # Setup executor
        self.executor = StepExecutor()

        # Setup runner
        if run_id:
            self.run_id = run_id
        else:
            self.run_id = ulid.new()
        self.log_dir = (
            Path(experiment_path)
            / "wei_runs"
            / (workflow_name + "_" + str(self.run_id))
        )
        self.result_dir = self.log_dir / "results"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.result_dir.mkdir(parents=True, exist_ok=True)
        self.logger = WEI_Logger.get_logger(
            "runLogger",
            log_dir=self.log_dir,
            log_level=log_level,
        )
        self.steps = self.init_flow(
            self.workcell, None, payload=payload, simulate=simulate
        )
        self.hist = {}

    def check_modules(self):
        """Checks the modules required by the workflow"""
        for module in self.workflow.modules:
            self.module_validator.check_module(module=module)

    def check_flowdef(self):
        """Checks the actions provided by the workflow"""
        for step in self.workflow.flowdef:
            self.step_validator.check_step(step=step)

    def init_flow(
        self,
        workcell: Workcell,
        callbacks: Optional[List[Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        simulate: bool = False,
    ) -> List[Dict[str, Any]]:
        """Pulls the workcell and builds a list of dictionary steps to be executed

        Parameters
        ----------
        workcell : Workcell
           The Workcell data file loaded in from the workcell yaml file

        payload: Dict
            The input to the workflow

        simulate: bool
            Whether or not to use real robots

        Returns
        -------
        steps: List[Dict]
           a list of steps and the metadata relevant to execute them
        """
        # TODO: configure the exceptions in such a way that they get thrown here, will be client job to handle these for now

        # Start executing the steps
        steps = []
        for module in self.workflow.modules:
            if not (workcell.find_step_module(module.name)):
                raise ValueError(
                    f"Module {module} not in Workcell {self.workflow.modules}"
                )
        for step in self.workflow.flowdef:
            arg_dict = {"locations": {}}
            # get module information from workcell file
            step_module = workcell.find_step_module(step.module)
            if not step_module:
                raise ValueError(
                    f"No module found for step module: {step.module}, in step: {step}"
                )
            valid = False
            for module in self.workflow.modules:
                if step.module == module.name:
                    valid = True
            if not (valid):
                raise ValueError(f"Module {step.module} not in flow modules")
            # replace position names with actual positions
            if (
                isinstance(step.args, dict)
                and len(step.args) > 0
                and workcell.locations
            ):
                if step.module in workcell.locations.keys():
                    for key, value in step.args.items():
                        # if hasattr(value, "__contains__") and "positions" in value:
                        if str(value) in workcell.locations[step.module].keys():
                            arg_dict["locations"][key] = value

                            step.args[key] = workcell.locations[step.module][value]

            # Inject the payload
            if isinstance(payload, dict):
                if not isinstance(step.args, dict) or len(step.args) == 0:
                    continue
                # TODO check if you can see the attr of this class and match them with vars in the yaml
                (arg_keys, arg_values) = zip(*step.args.items())
                for key, value in payload.items():
                    # Covers naming issues when referring to namespace from yaml file
                    if "payload." not in key:
                        key = f"payload.{key}"
                    if key in arg_values:
                        idx = arg_values.index(key)
                        step_arg_key = arg_keys[idx]
                        step.args[step_arg_key] = value

                # TODO remove once there is a better result_dir injection method
                # WARNING WILL FAIL IF `local_run_results` IN ARGS MORE THAN ONCE
                if "local_run_results" in arg_values:
                    idx = arg_values.index("local_run_results")
                    step_arg_key = arg_keys[idx]
                    step.args[step_arg_key] = str(self.result_dir)

            # execute the step

            arg_dict.update(
                {
                    "step": step,
                    "step_module": step_module,
                    "logger": self.logger,
                    "callbacks": callbacks,
                    "simulate": simulate,
                }
            )
            print(arg_dict)
            steps.append(arg_dict)
        return steps

    def run_flow(
        self,
        workcell: Workcell,
        callbacks: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        simulate: bool = False,
    ) -> Dict[str, Any]:
        """Runs through the steps of the workflow and sends the necessary

         Parameters
         ----------
         workcell : Workcell
            The Workcell data file loaded in from the workcell yaml file

         payload: bool
             The input to the workflow

         simulate: bool
             Whether or not to use real robots

         Returns
         -------
        response: Dict
            The result of running the workflow, including the log directory, the run_id the payload and the hist, which is the list of steps and their individual results
        """
        # TODO: configure the exceptions in such a way that they get thrown here, will be client job to handle these for now

        # TODO: configure the exceptions in such a way that they get thrown here, will be client job to handle these for now
        # Start executing the steps
        hist = {}
        steps = self.init_flow(workcell, callbacks, payload=payload, simulate=simulate)
        for step in steps:
            action_response, action_msg, action_log = self.executor.execute_step(**step)
            hist[step["step"].name] = {
                "action_response": str(action_response),
                "action_msg": str(action_msg),
                "action_log": str(action_log),
            }
            if "source" in step["locations"]:
                url = (
                    "http://localhost:8000/wc/locations/"
                    + step["locations"]["source"]
                    + "/set"
                )
                requests.post(url, params={"run_id": ""})
            if "target" in step["locations"]:
                url = (
                    "http://localhost:8000/wc/locations/"
                    + step["locations"]["target"]
                    + "/set"
                )
                requests.post(url, params={"run_id": self.run_id})
        return {
            "run_dir": str(self.log_dir),
            "run_id": str(self.run_id),
            "payload": payload,
            "hist": hist,
        }

    def print_flow(self):
        """Prints the workflow dataclass, for debugging"""
        debug(self.workflow)

    def print_workcell(self):
        """Print the workcell datacall, for debugging"""
        debug(self.workcell)