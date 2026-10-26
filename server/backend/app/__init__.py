from fastapi import FastAPI

from .routers import (
    note,
    provider,
    model,
    config,
    chat,
    bilibili_auth,
    bilibili_favorites,
    brief_asr,
)



def create_app(lifespan) -> FastAPI:
    app = FastAPI(title="BiliNote",lifespan=lifespan)
    app.include_router(note.router, prefix="/api")
    app.include_router(provider.router, prefix="/api")
    app.include_router(model.router,prefix="/api")
    app.include_router(config.router,  prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(bilibili_auth.router, prefix="/api")
    app.include_router(bilibili_favorites.router, prefix="/api")
    app.include_router(brief_asr.router, prefix="/api")

    return app
