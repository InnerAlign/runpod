import runpod

def handler(event):
    return {
        "status": "ok",
        "message": "RunPod endpoint connected successfully",
        "input": event
    }

runpod.serverless.start({
    "handler": handler
})
