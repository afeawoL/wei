"""
Router for the "experiments"/"exp" endpoints
"""
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from wei.core.experiment import Experiment, create_experiment
from wei.core.loggers import WEI_Logger

router = APIRouter()


@router.post("/{experiment_id}/log")
def log_experiment(experiment_id: str, log_value: str) -> JSONResponse:
    """Logs a value to the log file for a given experiment"""
    logger = WEI_Logger.get_experiment_logger(experiment_id)
    logger.info(log_value)
    return JSONResponse(status_code=200, content={"logged": log_value})


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
    """Returns a file inside an experiment folder."""
    return FileResponse(filepath)


@router.get("/")
def get_experiment(
    experiment_name: str,
    experiment_id: Optional[str] = None,
) -> Dict[str, Path]:
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

    return create_experiment(experiment_name, experiment_id)
