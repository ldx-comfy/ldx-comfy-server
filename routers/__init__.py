import fastapi
from . import forms, health, auth, users, groups

def include_routers(app: fastapi.FastAPI) -> fastapi.FastAPI:
    app.include_router(forms.router)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(groups.router)
    return app