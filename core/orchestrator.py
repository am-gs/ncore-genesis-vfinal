from typing import TypedDict, List

from fastapi import FastAPI
from langgraph.graph import StateGraph, END

from moe_router import NCoreModelRegistry, AthenaMoERouter


class AgentState(TypedDict):
    messages: List[str]
    task: str
    model_name: str
    model_endpoint: str
    role: str


registry = NCoreModelRegistry()
router = AthenaMoERouter(registry)


def route_node(state: AgentState) -> AgentState:
    cfg = router.route(state["task"])
    state["model_name"] = cfg.name
    state["model_endpoint"] = cfg.endpoint
    state["role"] = cfg.role
    state["messages"].append(f"Routed to {cfg.name} ({cfg.role}) at {cfg.endpoint}")
    return state


graph = StateGraph(AgentState)

graph.add_node("route", route_node)
graph.set_entry_point("route")
graph.add_edge("route", END)

agent = graph.compile()

app = FastAPI()


@app.post("/run")
async def run_task(payload: dict) -> AgentState:
    task = payload.get("task", "")
    result: AgentState = await agent.ainvoke(
        {"messages": [], "task": task, "model_name": "", "model_endpoint": "", "role": ""}
    )
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("orchestrator:app", host="0.0.0.0", port=8080, reload=False)
