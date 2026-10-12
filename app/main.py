from fastapi import FastAPI

app = FastAPI(title="LLD Practice Platform")


@app.get("/health")
def health():
    return {"status": "ok"}