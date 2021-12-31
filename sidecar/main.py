import asyncio
from datetime import datetime
import time

import httpx
from aiohttp import ClientResponseError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from sidecar.http_client import Http, HttpMethod
from sidecar.settings import get_settings

settings = get_settings()
app = FastAPI()

h = Http()

in_proc_requests = 0


class GlobalState:
    app_shutdown_ready = False
    dapr_shutdown_ready = False
    self_shutdown_ready = False
    app_has_started = False


async def check_app_startup():
    if GlobalState.app_has_started:
        return True
    app_ready_probe_url = f"http://localhost:{settings.main_app_port}{settings.main_app_ready_probe_path}"
    logger.info(f"checking app readiness: {app_ready_probe_url}")
    try:
        response_status, response_json = await h.invoke(HttpMethod.get, app_ready_probe_url)
    except:
        logger.info("app is not ready yet")
        return False
    if response_status == 200:
        logger.info("app is ready")
        GlobalState.app_has_started = True
        return True
    return False


async def get_dapr_path(dapr_path: str):
    while GlobalState.app_has_started is False:
        await check_app_startup()
        await asyncio.sleep(1)
    while True:
        try:
            response_status, response_json = await h.invoke(HttpMethod.get, f"http://localhost:{settings.main_app_port}{dapr_path}")
        except Exception as e:
            if e.code == 404:
                return JSONResponse([], status_code=404)
            await asyncio.sleep(1)
            continue

        if response_status == 200:
            logger.info(response_json)
            return JSONResponse(response_json, status_code=response_status)
        else:
            await asyncio.sleep(1)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    global in_proc_requests
    path = request.url.path
    if not path.startswith("/daps"):
        incr_in_progress = True
    else:
        incr_in_progress = False
    if incr_in_progress:
        in_proc_requests += 1
    response = await call_next(request)
    if incr_in_progress:
        in_proc_requests -= 1
    return response


@app.get("/daps/in-progress-requests")
async def get_in_proc_requests():
    global in_proc_requests
    return {"in_progress_requests": in_proc_requests}


@app.on_event("startup")
async def startup_event():
    await h.__aenter__()
    while GlobalState.app_has_started is False:
        await check_app_startup()
        await asyncio.sleep(1)


@app.get("/daps/app-shutdown")
async def get_app_shutdown():
    global in_proc_requests
    logger.info("entering shutdown mode")
    grace_time = settings.pod_termination_grace_period_seconds - 2
    start = datetime.now()
    use_busy_probe = False
    if settings.main_app_busy_probe_path:
        use_busy_probe = True

    if use_busy_probe:
        app_busy_probe_url = f"http://localhost:{settings.main_app_port}{settings.main_app_busy_probe_path}"
        async with httpx.AsyncClient() as client:
            logger.info(f"checking app shutdown readiness on url {app_busy_probe_url}")
            while True:
                end = datetime.now()
                taken = (end - start).total_seconds()
                logger.info(f"taken: {taken}")
                if taken > grace_time:
                    logger.info("timed out waiting for main app to be ready to shutdown")
                    GlobalState.app_shutdown_ready = True
                    return {"status": "ok"}
                try:
                    response = await client.get(app_busy_probe_url, timeout=1)

                except httpx.RequestError as e:
                    logger.info(f"unable contact app pod, assuming busy: {str(e)}")
                    await asyncio.sleep(1)
                    continue

                response_data = response.json()
                if response_data.get("busy", None) is False:
                    logger.info("main app reporting not busy. ready to shut down")
                    GlobalState.app_shutdown_ready = True
                    return {"status": "ok"}
                await asyncio.sleep(1)
    else:  # use daps internal "inprogress requests" counter
        while True:
            end = datetime.now()
            taken = (end - start).total_seconds()
            logger.info(f"taken: {taken}")
            if taken > grace_time:
                logger.info("timed out waiting for main app to be ready to shutdown")
                GlobalState.app_shutdown_ready = True
                return {"status": "ok"}
            if in_proc_requests == 0:
                logger.info("zero requests in progress. ready to shut down")
                GlobalState.app_shutdown_ready = True
                return {"status": "ok"}
            await asyncio.sleep(1)


@app.get("/daps/dapr-shutdown")
async def get_dapr_shutdown():
    while True:
        logger.info(f"GlobalState.app_shutdown_ready: {GlobalState.app_shutdown_ready}")
        if GlobalState.app_shutdown_ready:
            GlobalState.dapr_shutdown_ready = True
            return {"status": "ok"}
        else:
            await asyncio.sleep(1)



@app.get("/daps/self-shutdown")
async def get_self_shutdown():
    while True:
        logger.info(f"GlobalState.dapr_shutdown_ready: {GlobalState.dapr_shutdown_ready}")
        if GlobalState.dapr_shutdown_ready:
            GlobalState.self_shutdown_ready = True
            return {"status": "ok"}
        else:
            await asyncio.sleep(1)


@app.get("/dapr/subscribe")
async def get_dapr_subscribe():
    logger.info("/dapr/subscribe")
    return await get_dapr_path("/dapr/subscribe")


@app.get("/dapr/config")
async def get_dapr_subscribe():
    logger.info("/dapr/config")
    return await get_dapr_path("/dapr/config")


@app.api_route("/{full_path:path}", methods=["GET", "POST", "DELETE"])
async def catch_all(request: Request):
    path = request.path_params["full_path"]
    logger.info(path)
    if GlobalState.app_has_started is False:
        await check_app_startup()
        if GlobalState.app_has_started is False:
            return JSONResponse({}, status_code=500)

    method = HttpMethod(request.method)
    if method == HttpMethod.post:
        try:
            body = await request.json()
        except:
            body = None
    else:
        body = None

    url = f"http://localhost:{settings.main_app_port}/{path}"
    try:
        logger.info(f"awaiting downstream response for {method.value} call to {url} with body {body}")
        response_status, response_json = await h.invoke(method, url, body)
    except ClientResponseError as e:
        return JSONResponse(status_code=e.status)
    logger.info(response_json)
    return JSONResponse(response_json, status_code=response_status)
