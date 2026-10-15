"""Optional live queue-order/health check against the local pinned generation service."""
import concurrent.futures
import json
import time
import urllib.request

BASE = "http://llm:8080"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(path):
    with OPENER.open(BASE + path, timeout=5) as response: return json.load(response)


def until(predicate):
    deadline = time.monotonic() + 8
    while not predicate():
        if time.monotonic() > deadline: raise RuntimeError("live scheduler condition timed out")
        time.sleep(.02)


def generate(name, priority):
    from model_worker.generator_profile import load
    payload = {"model": load()['alias'], "messages": [{"role": "user", "content": "Write a paragraph of about 100 words explaining how a soccer match works."}],
               "temperature": 0, "seed": 42, "max_tokens": 192, "reasoning": "off", "cache_prompt": False}
    request = urllib.request.Request(BASE + "/v1/chat/completions", data=json.dumps(payload).encode(),
                                    headers={"Content-Type": "application/json", "X-VectorNext-Priority": priority})
    start = time.monotonic()
    with OPENER.open(request, timeout=215) as response: value = json.load(response)
    return {"name": name, "priority": priority, "finished_at": time.monotonic(), "elapsed_seconds": time.monotonic() - start,
            "finish_reason": value["choices"][0]["finish_reason"], "usage": value.get("usage")}


def main():
    before = get("/scheduler")
    assert not before["active"] and before["interactive_waiting"] == before["background_waiting"] == 0
    with concurrent.futures.ThreadPoolExecutor(3) as pool:
        active = pool.submit(generate, "active_background", "background")
        until(lambda: get("/scheduler")["active"])
        background = pool.submit(generate, "waiting_background", "background")
        until(lambda: get("/scheduler")["background_waiting"] == 1)
        interactive = pool.submit(generate, "interactive", "interactive")
        until(lambda: get("/scheduler")["interactive_waiting"] == 1)
        start = time.monotonic(); health = get("/health"); health_seconds = time.monotonic() - start
        rows = [future.result() for future in (active, background, interactive)]
    order = [r["name"] for r in sorted(rows, key=lambda r: r["finished_at"])]
    assert order == ["active_background", "interactive", "waiting_background"], order
    assert not get("/scheduler")["failed"]
    print(json.dumps({"order": order, "requests": rows, "health_during_generation": health,
                      "health_seconds": health_seconds, "before": before, "after": get("/scheduler")}), flush=True)


if __name__ == "__main__": main()
