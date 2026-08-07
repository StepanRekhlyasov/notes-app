import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .notify_worker import notify_worker_loop
from .routers import account as account_router
from .routers import auth as auth_router
from .routers import notes as notes_router
from .routers import notifications as notifications_router
from .routers import tags as tags_router
from .telegram_poller import telegram_poll_loop


@asynccontextmanager
async def lifespan(_app: FastAPI):
    stop = asyncio.Event()
    tasks: list[asyncio.Task] = []
    if (settings.telegram_bot_token or "").strip():
        tasks.append(asyncio.create_task(telegram_poll_loop(stop)))
        tasks.append(asyncio.create_task(notify_worker_loop(stop)))
    try:
        yield
    finally:
        stop.set()
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="Notes API", version="0.1.0", lifespan=lifespan)

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


app.include_router(auth_router.router, prefix="/api")
app.include_router(account_router.router, prefix="/api")
app.include_router(notes_router.router, prefix="/api")
app.include_router(tags_router.router, prefix="/api")
app.include_router(notifications_router.router, prefix="/api")
