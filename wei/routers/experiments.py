"""
Router for the "experiments"/"exp" endpoints
"""
from typing import Dict, Optional

from fastapi import APIRouter
from fastapi.responses import FileResponse

from wei.config import Config
from wei.core.data_classes import Event
from wei.core.events import EventLogger, Events
from wei.core.experiment import Experiment

router = APIRouter()


@router.post("/{experiment_id}/log")
def log_experiment(experiment_id: str, event: Event) -> Event:
    """Logs a value to the log file for a given experiment"""
    EventLogger(experiment_id).log_event(event)
    return event


@router.get("/{experiment_id}/log")
async def log_return(experiment_id: str) -> str:
    """Returns the log for a given experiment"""
    experiment = Experiment(experiment_id=experiment_id)

    with open(
        experiment.experiment_log_file,
        "r",
    ) as f:
        return f.read()


@router.get("/{experiment_id}/file")
async def get_file(filepath: str) -> FileResponse:
    """Returns the log for a given experiment"""
    return FileResponse(filepath)


@router.get("/")
def get_experiment(
    experiment_name: str,
    experiment_id: Optional[str] = None,
) -> Dict[str, str]:
    """Pulls an experiment and creates the files and logger for it

    Parameters
    ----------
    experiment_name: str
        The human created name of the experiment
    experiment_id : str
       The programmatically generated id of the experiment for the workflow
    Returns
    -------
     response: Dict
       a dictionary including the successfulness of the queueing, the jobs ahead and the id

    """

    experiment = Experiment(
        experiment_name=experiment_name, experiment_id=experiment_id
    )
    experiment.experiment_dir.mkdir(parents=True, exist_ok=True)
    experiment.run_dir.mkdir(parents=True, exist_ok=True)

    event_logger = Events(
        server_addr=Config.server_host,
        server_port=Config.server_port,
        experiment_id=experiment.experiment_id,
    )
    event_logger.start_experiment()
    return {
        "experiment_id": experiment.experiment_id,
        "experiment_name": experiment.experiment_name,
        "experiment_path": str(experiment.experiment_dir),
    }
