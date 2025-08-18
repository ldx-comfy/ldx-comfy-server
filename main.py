from fastapi import FastAPI
from routers import include_routers

app = include_routers(FastAPI())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000,reload=True,workers=1)
