import json
from pathlib import Path
from argparse import ArgumentParser
from contextlib import asynccontextmanager
from typing import Dict, Any

import rq
import ulid
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from rq.job import Job
from rq.registry import FailedJobRegistry, FinishedJobRegistry, StartedJobRegistry

from rpl_wei.core.data_classes import Workcell
from rpl_wei.processing.worker import run_workflow_task, task_queue

# TODO: db backup of tasks and results (can be a proper db or just a file)
# TODO logging for server and workcell
# TODO consider sub-applications for different parts of the server (e.g. /job, /queue, /data, etc.)
# TODO make the workcell live in the DATA_DIR and be coupled to the server
#      This might entail making a rq object of the wei object and making that available to the workers

workcell = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global workcell
    parser = ArgumentParser()
    parser.add_argument("--workcell", type=Path, help="Path to workcell file")

    args = parser.parse_args()
    workcell = Workcell.from_yaml(args.workcell)

    # Yield control to the application
    yield

    # Do any cleanup here
    pass


app = FastAPI(lifespan=lifespan)


def submit_job(
    experiment_id: str, workflow_content_str: str, parsed_payload: Dict[str, Any]
):
    # manually create job ulid (so we can use it for the loggign inside wei)
    job_id = ulid.new().str

    base_response_content = {
        "experiment_id": experiment_id,
    }
    try:
        job = task_queue.enqueue(
            run_workflow_task,
            experiment_id,
            workflow_content_str,
            parsed_payload,
            workcell.__dict__,
            job_id,
            job_id=job_id,
        )
        jobs_ahead = len(task_queue.jobs)
        response_content = {
            "status": "success",
            "jobs_ahead": jobs_ahead,
            "job_id": job.get_id(),
            **base_response_content,
        }
        return JSONResponse(content=response_content)
    except Exception as e:
        response_content = {
            "status": "failed",
            "error": str(e),
            **base_response_content,
        }
        return JSONResponse(content=response_content)


@app.post("/job")
async def process_job(workflow: UploadFile = File(...), payload: str = Form("{}")):
    workflow_content = await workflow.read()
    # Decode the bytes object to a string
    workflow_content_str = workflow_content.decode("utf-8")
    parsed_payload = json.loads(payload)

    # Generate ULID for the experiment, really this should be done by the client (Experiment class)
    experiment_id = ulid.new().str

    return submit_job(experiment_id, workflow_content_str, parsed_payload)


@app.post("/job/{experiment_id}")
async def process_job_with_id(
    experiment_id: str, workflow: UploadFile = File(...), payload: str = Form("{}")
):
    workflow_content = await workflow.read()
    workflow_content_str = workflow_content.decode("utf-8")

    parsed_payload = json.loads(payload)

    return submit_job(experiment_id, workflow_content_str, parsed_payload)


@app.get("/job/{job_id}")
async def get_job_status(job_id: str):
    try:
        job = Job.fetch(job_id, connection=task_queue.connection)
    except rq.exceptions.NoSuchJobError:
        return JSONResponse(content={"status": "failed", "error": "No such job"})

    job_status = job.get_status()
    result = job.result

    return JSONResponse(content={"status": job_status, "result": result})


@app.get("/queue/info")
async def queue_info():
    # TODO: what more information can we get from the queue?
    queued_jobs = task_queue.count
    started_registry = StartedJobRegistry(queue=task_queue)
    started_jobs = len(started_registry)
    finished_registry = FinishedJobRegistry(queue=task_queue)
    finished_jobs = len(finished_registry)
    failed_registry = FailedJobRegistry(queue=task_queue)
    failed_jobs = len(failed_registry)

    return JSONResponse(
        content={
            "queued_jobs": queued_jobs,
            "started_jobs": started_jobs,
            "finished_jobs": finished_jobs,
            "failed_jobs": failed_jobs,
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("rpl_wei.server:app", reload=True)
