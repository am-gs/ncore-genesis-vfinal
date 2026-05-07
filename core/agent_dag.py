"""NCore Genesis — Agent DAG Engine
Directed acyclic graph execution for specialist agents with dependencies.
"""
from __future__ import annotations
import asyncio
from typing import Dict, List, Set, Callable, Any
import structlog

log = structlog.get_logger()


class AgentDAG:
    """Directed acyclic graph of agent execution.
    
    Supports:
    - Dependencies: agent B waits for agent A
    - Parallelism: agents with no mutual dependencies run concurrently
    - Topological execution order
    - Validation after each step
    - Retry logic with feedback
    """
    
    def __init__(self, agents: list[dict]):
        self.agents = {a["role"]: a for a in agents}
        self.dependencies = self._build_deps(agents)
        self.completed: Set[str] = set()
        self.results: Dict[str, Any] = {}
        self.status: Dict[str, str] = {role: "pending" for role in self.agents}
        
    def _build_deps(self, agents: list[dict]) -> Dict[str, Set[str]]:
        """Build dependency graph from agent specs."""
        deps = {a["role"]: set() for a in agents}
        for a in agents:
            role = a["role"]
            # depends_on: explicit dependencies
            if "depends_on" in a:
                for dep in a["depends_on"]:
                    if dep in deps:
                        deps[role].add(dep)
            # parallel_with: implicit sibling dependencies
            # (these don't block each other but may share a common dependency)
        return deps
    
    def ready_agents(self) -> List[str]:
        """Return agents whose dependencies are all satisfied."""
        ready = []
        for role, deps in self.dependencies.items():
            if role in self.completed:
                continue
            if all(dep in self.completed for dep in deps):
                ready.append(role)
        return ready
    
    async def execute(self, executor_fn: Callable, validator_fn: Callable = None, 
                      max_retries: int = 2) -> Dict[str, Any]:
        """Topological execution with parallelism where possible.
        
        Args:
            executor_fn: async function(role, agent_spec) -> result_dict
            validator_fn: async function(role, result_dict) -> validation_dict
            max_retries: max retry attempts per agent on validation failure
            
        Returns:
            Dict of all agent results by role
        """
        log.info("dag.execute.start", agents=list(self.agents.keys()))
        
        while len(self.completed) < len(self.agents):
            ready = self.ready_agents()
            if not ready:
                # Deadlock or cycle - should not happen in valid DAGs
                pending = set(self.agents.keys()) - self.completed
                log.error("dag.deadlock", pending=list(pending))
                raise RuntimeError(f"Deadlock detected. Pending: {pending}")
            
            log.info("dag.execute.batch", ready=ready)
            
            # Execute ready agents in parallel
            tasks = [self._execute_with_retry(role, executor_fn, validator_fn, max_retries) 
                     for role in ready]
            batch_results = await asyncio.gather(*tasks)
            
            # Update results and mark as completed
            for role, result in zip(ready, batch_results):
                self.results[role] = result
                self.completed.add(role)
                self.status[role] = "completed"
                
        log.info("dag.execute.complete", agents=len(self.results))
        return self.results
    
    async def _execute_with_retry(self, role: str, executor_fn: Callable, 
                                  validator_fn: Callable, max_retries: int) -> Dict[str, Any]:
        """Execute agent with validation and retry logic."""
        agent_spec = self.agents[role]
        self.status[role] = "running"
        
        for attempt in range(max_retries + 1):
            try:
                # Execute agent
                result = await executor_fn(role, agent_spec)
                self.status[role] = "executed"
                
                # Validate if validator provided
                if validator_fn:
                    validation = await validator_fn(role, result)
                    if not validation.get("valid", True):
                        issues = validation.get("issues", [])
                        suggestion = validation.get("suggestion", "")
                        log.warning("dag.validation.failed", role=role, attempt=attempt,
                                    issues=issues, suggestion=suggestion)
                        
                        if attempt < max_retries:
                            # Retry with feedback
                            agent_spec["feedback"] = {
                                "issues": issues,
                                "suggestion": suggestion,
                                "attempt": attempt + 1
                            }
                            self.status[role] = "retrying"
                            continue  # Retry
                        else:
                            # Max retries exceeded
                            result["validation"] = validation
                            result["status"] = "validation_failed"
                            self.status[role] = "failed"
                            return result
                    else:
                        # Validation passed
                        result["validation"] = validation
                        result["status"] = "validated"
                        self.status[role] = "validated"
                        return result
                else:
                    # No validation needed
                    result["status"] = "completed"
                    return result
                    
            except Exception as e:
                log.error("dag.agent.error", role=role, error=str(e), attempt=attempt)
                if attempt < max_retries:
                    self.status[role] = "retrying"
                    continue
                else:
                    self.status[role] = "error"
                    return {
                        "role": role,
                        "output": f"[Error] {e}",
                        "status": "error",
                        "error": str(e),
                        "attempt": attempt
                    }
        
        # Should not reach here
        return {"role": role, "output": "[Unknown Error]", "status": "unknown"}