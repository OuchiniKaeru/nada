import asyncio
import time

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.models.anthropic import Claude
from agno.models.google import Gemini
from agno.models.ollama import Ollama
from agno.models.openrouter import OpenRouter
from agno.models.azure import AzureOpenAI, AzureAIFoundry
from agno.team import Team, TeamMode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.agent import Agent as AgentModel
from app.models.skill import Skill
from app.models.mcp import MCPServer
from app.models.squad import Squad
from app.models.squad_member import SquadMember
from app.models.attachment import Attachment
from app.services.agent_factory import AgentFactory, get_agno_postgres_db
from app.services.attachment_service import list_attachments_by_ids
from agno.media import File as AgnoFile


class AgentRuntime:
    def __init__(self, agent_id: str, db: AsyncSession, session_id: str | None = None, user_id: str | None = None):
        self.agent_id = agent_id
        self.db = db
        self.session_id = session_id
        self.user_id = user_id
        self.usage: dict = {}

    async def run(self, message: str, attachments: list) -> str:
        config = await self._load_agent_definition()

        # Isolate the ENTIRE MCP-touching lifecycle (agent creation which connects
        # MCP tools, the run, and the close) inside ONE child task on the same
        # event loop. agno's MCPTools wraps every connection in an anyio cancel
        # scope created by whatever task enters it. Running connect+run+close on
        # the request task means the MCP scope teardown delivers its CancelledError
        # to the request task, which then surfaces at the first subsequent await
        # (the assistant-message DB commit), producing a 500 after a successful
        # run. Keeping the whole lifecycle in one child task contains that
        # cancel-scope teardown so only the child is cancelled, never the request.
        agent_holder = {}
        result_holder = {"content": None}

        async def _execute():
            agent = None
            run_start = time.monotonic()
            try:
                agent = await AgentFactory.create_agent(
                    config, session_id=self.session_id, user_id=self.user_id
                )
                agent_holder["agent"] = agent
                run = await agent.arun(
                    message, session_id=self.session_id, user_id=self.user_id
                )
                content = getattr(run, "content", None)
                if not content:
                    content = getattr(getattr(run, "response", None), "content", None)
                result_holder["content"] = str(content) if content else "(no response)"
                self.usage = self._make_usage(
                    config, getattr(run, "metrics", {}) or {}, run_start
                )
            except asyncio.CancelledError:
                # The child task may be cancelled by the MCP cancel-scope teardown
                # during close() below. That is contained here, in the child.
                raise
            except Exception as exc:
                result_holder["error"] = exc
            finally:
                if agent is not None:
                    try:
                        await self._close_mcp_tools(agent)
                    except BaseException:
                        pass

        task = asyncio.create_task(_execute())
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            # If the *request* task is the one actually being cancelled (client
            # disconnect / shutdown), propagate it so FastAPI/uvicorn handles it
            # normally. If only the child was cancelled by MCP teardown, shield
            # surfaces that CancelledError here — but the run already completed,
            # so recover the result instead of failing the request.
            if result_holder.get("content") is not None:
                return result_holder["content"]
            raise
        except Exception as exc:
            return f"ランタイムエラー: {exc}"

        if "error" in result_holder:
            return f"ランタイムエラー: {result_holder['error']}"
        if task.cancelled() and result_holder.get("content") is None:
            return "ランタイムエラー: 処理がキャンセルされました。"

        return result_holder.get("content") or "(no response)"

    async def astream(self, message: str, attachments: list | None = None):
        """Stream the agent's response token-by-token (async generator of str).

        The ENTIRE agno lifecycle (MCP connect + run + close) runs inside ONE
        child task on the same event loop; only text deltas are pushed across a
        queue to the request task. This preserves the MCP cancel-scope isolation:
        agno tears down each MCP client's anyio cancel scope on close(), and that
        teardown delivers its CancelledError to whatever task entered the scope.
        Containing it in the child task means a spurious cancel never escapes
        into the request task / DB commit. See notes in the skill references.
        """
        config = await self._load_agent_definition()
        files = await _build_agent_files(self.db, attachments)

        q: asyncio.Queue = asyncio.Queue()
        metrics_holder: dict = {}
        error_holder: dict = {"msg": None}

        async def _produce():
            agent = None
            run_start = time.monotonic()
            pushed_any = False
            completed_content = None
            try:
                agent = await AgentFactory.create_agent(
                    config, session_id=self.session_id, user_id=self.user_id
                )
                async for event in agent.arun(
                    message,
                    stream=True,
                    session_id=self.session_id,
                    user_id=self.user_id,
                    files=files or None,
                ):
                    # agno emits event strings like "RunContent" / "RunCompleted".
                    # Compare on a case-insensitive basis to stay robust across
                    # agent and team event enums.
                    ev = (getattr(event, "event", "") or "").lower()
                    if ev in ("runcontent", "runintermediatecontent"):
                        chunk = getattr(event, "content", None)
                        if chunk is not None:
                            pushed_any = True
                            q.put_nowait(("delta", str(chunk)))
                    elif ev == "runcompleted":
                        metrics_holder["metrics"] = getattr(event, "metrics", None)
                        fc = getattr(event, "content", None)
                        if fc is not None:
                            completed_content = str(fc)
                    elif ev == "runerror":
                        msg = str(getattr(event, "content", None) or "エラーが発生しました。")
                        error_holder["msg"] = msg
                        q.put_nowait(("error", msg))
                # Some providers don't emit incremental content events; fall back
                # to the final content carried by the completed event so the UI
                # never ends up with "(no response)".
                if not pushed_any and completed_content:
                    q.put_nowait(("delta", completed_content))
                self.usage = self._make_usage(config, metrics_holder.get("metrics") or {}, run_start)
            except BaseException as exc:  # noqa: BLE001 - must never hang the queue
                if error_holder.get("msg") is None:
                    error_holder["msg"] = f"ランタイムエラー: {exc}"
                q.put_nowait(("error", error_holder["msg"]))
            finally:
                if agent is not None:
                    try:
                        await self._close_mcp_tools(agent)
                    except BaseException:
                        pass
                q.put_nowait(("done", None))

        _task = asyncio.create_task(_produce())
        while True:
            kind, data = await q.get()
            if kind == "delta":
                yield data
            elif kind == "error":
                yield data
            else:  # done
                break

    @staticmethod
    def _make_usage(config, metrics, run_start: float) -> dict:
        return {
            "input_tokens": int(_metric(metrics, "input_tokens", "prompt_tokens") or 0),
            "output_tokens": int(_metric(metrics, "output_tokens", "completion_tokens") or 0),
            "total_tokens": int(_metric(metrics, "total_tokens") or 0),
            "cost": float(_metric(metrics, "cost", "completion_cost") or 0.0),
            "duration_ms": int((time.monotonic() - run_start) * 1000),
            "model": getattr(config, "model_id", ""),
        }

    @staticmethod
    async def _close_mcp_tools(agent):
        """Close MCP connections inside the same task that entered them.

        agno's MCPTools holds each connection inside an anyio cancel scope that
        is created by whatever task entered it. The scope's teardown (close) can
        deliver a CancelledError to the current task. This helper is only ever
        called from within the isolated child task (see ``astream`` / ``run``), so
        the scope is both entered and exited in the same task — the
        CancelledError it raises is contained in that child task and never
        reaches the request task.
        """
        for tool in getattr(agent, "tools", []) or []:
            if hasattr(tool, "close"):
                try:
                    await tool.close()
                except BaseException:
                    pass

    async def _load_agent_definition(self):
        agent = await self.db.get(AgentModel, self.agent_id)
        if not agent:
            raise ValueError("Agentが見つかりません。")

        skills = []
        if agent.skill_ids:
            result = await self.db.execute(select(Skill).where(Skill.id.in_(agent.skill_ids)))
            skills = list(result.scalars().all())

        mcp = None
        mcp_ids = agent.mcp_server_ids or []
        if agent.mcp_server_id:
            mcp_ids = [agent.mcp_server_id] + [aid for aid in mcp_ids if aid != agent.mcp_server_id]
        mcp_servers = []
        for mcp_id in mcp_ids:
            mcp_server = await self.db.get(MCPServer, mcp_id)
            if mcp_server:
                mcp_servers.append(mcp_server)

        class _Cfg:
            pass

        cfg = _Cfg()
        cfg.title = agent.title
        cfg.system_prompt = agent.system_prompt
        cfg.model_provider = agent.model_provider
        cfg.model_id = agent.model_id
        cfg.skill_ids = agent.skill_ids
        cfg.mcp_server_id = agent.mcp_server_id
        cfg.skills = skills
        cfg.mcp = mcp_servers
        cfg.tools_config = agent.tools_config or {}
        cfg.workspace_config = agent.workspace_config or {}
        cfg.skills_config = agent.skills_config or {}
        cfg.mcp_tools_config = agent.mcp_tools_config or {}

        return cfg


def _build_agent_files(db: AsyncSession, attachment_ids: list | None):
    """Build agno ``File`` objects from stored attachments so the agent can read them."""
    async def _inner() -> list:
        if not attachment_ids:
            return []
        attachments = await list_attachments_by_ids(db, attachment_ids)
        files = []
        for att in attachments:
            if not att.file_path:
                continue
            files.append(
                AgnoFile(
                    filepath=att.file_path,
                    filename=att.filename or None,
                    size=att.size if getattr(att, "size", None) is not None else None,
                )
            )
        return files
    return _inner()


def _metric(metrics, primary: str, alias: str = None):
    """Read a metric value that may be a dict or an agno ``RunMetrics`` object.

    agno's ``Run.metrics`` is a ``RunMetrics`` model (attribute access), not a
    plain dict, so ``metrics.get(...)`` raises AttributeError. Fall back through
    common aliases and return None when absent.
    """
    if metrics is None:
        return None
    if isinstance(metrics, dict):
        return metrics.get(primary) if primary in metrics else (metrics.get(alias) if alias else None)
    for key in (primary, alias):
        if key and hasattr(metrics, key):
            return getattr(metrics, key)
    return None


class SquadChatRuntime:
    def __init__(self, squad: Squad, db: AsyncSession, session_id: str | None = None):
        self.squad = squad
        self.db = db
        self.session_id = session_id
        self.usage: dict = {}

    def _make_usage(self, model: str, metrics, run_start: float) -> dict:
        return {
            "input_tokens": int(_metric(metrics, "input_tokens", "prompt_tokens") or 0),
            "output_tokens": int(_metric(metrics, "output_tokens", "completion_tokens") or 0),
            "total_tokens": int(_metric(metrics, "total_tokens") or 0),
            "cost": float(_metric(metrics, "cost", "completion_cost") or 0.0),
            "duration_ms": int((time.monotonic() - run_start) * 1000),
            "model": model or "",
        }

    async def run(self, message: str, attachments: list) -> str:
        squad = self.squad
        members = await self._load_team_members()
        mode = (squad.mode or "coordinate").strip().lower()

        leader, member_agents, names = self._select_leader(members, squad.leader_agent_id)

        if leader is None:
            self.usage = self._make_usage(squad.model_id, {}, time.monotonic())
            return (
                f"[squad placeholder] squad={squad.name!r} "
                f"members={names} message={message!r}"
            )

        run_start = time.monotonic()
        try:
            mode_enum = (
                TeamMode.coordinate
                if mode in ("coordinate", "collaborate", "")
                else TeamMode.route
            )
            # The Team coordinates with the leader's own model (loaded from the
            # leader agent config), falling back to the squad's configured model.
            # Using the squad default (openai/gpt-4o) when members are google/
            # openrouter models fails when no OpenAI key is configured.
            team_model = getattr(leader, "model", None) or _load_model(
                squad.model_provider, squad.model_id
            )
            team = Team(
                name=squad.name,
                mode=mode_enum,
                model=team_model,
                members=[leader, *member_agents],
                instructions=squad.system_prompt,
            )
            run = await team.arun(message, session_id=self.session_id)
            content = getattr(run, "content", None)
            if not content:
                content = (
                    getattr(getattr(run, "response", None), "content", None) or str(run)
                )
            self.usage = self._make_usage(
                squad.model_id, getattr(run, "metrics", None), run_start
            )
            return str(content)
        except Exception as exc:
            names = [getattr(m, "name", aid) for m, aid in members] or names
            return (
                f"[squad runtime fallback] squad={squad.name!r} members={names} "
                f"message={message!r} error={exc!r}"
            )

    async def astream(self, message: str, attachments: list | None = None):
        """Stream a squad (agno Team) response token-by-token (async generator of str)."""
        squad = self.squad
        members = await self._load_team_members()
        leader, member_agents, names = self._select_leader(members, squad.leader_agent_id)

        if leader is None:
            self.usage = self._make_usage(squad.model_id, {}, time.monotonic())
            yield (
                f"[squad placeholder] squad={squad.name!r} "
                f"members={names} message={message!r}"
            )
            return

        files = (await _build_agent_files(self.db, attachments)) if attachments else []
        q: asyncio.Queue = asyncio.Queue()
        metrics_holder: dict = {}

        async def _produce():
            run_start = time.monotonic()
            pushed_any = False
            completed_content = None
            try:
                mode = (squad.mode or "coordinate").strip().lower()
                mode_enum = (
                    TeamMode.coordinate
                    if mode in ("coordinate", "collaborate", "")
                    else TeamMode.route
                )
                team_model = getattr(leader, "model", None) or _load_model(
                    squad.model_provider, squad.model_id
                )
                team = Team(
                    name=squad.name,
                    mode=mode_enum,
                    model=team_model,
                    members=[leader, *member_agents],
                    instructions=squad.system_prompt,
                )
                async for event in team.arun(
                    message,
                    stream=True,
                    session_id=self.session_id,
                    files=files or None,
                ):
                    ev = (getattr(event, "event", "") or "").lower()
                    if ev in ("runcontent", "runintermediatecontent"):
                        chunk = getattr(event, "content", None)
                        if chunk is not None:
                            pushed_any = True
                            q.put_nowait(("delta", str(chunk)))
                    elif ev == "runcompleted":
                        metrics_holder["metrics"] = getattr(event, "metrics", None)
                        fc = getattr(event, "content", None)
                        if fc is not None:
                            completed_content = str(fc)
                    elif ev == "runerror":
                        q.put_nowait(
                            ("error", str(getattr(event, "content", None) or "エラーが発生しました。"))
                        )
                if not pushed_any and completed_content:
                    q.put_nowait(("delta", completed_content))
                self.usage = self._make_usage(
                    squad.model_id, metrics_holder.get("metrics") or {}, run_start
                )
            except BaseException as exc:  # noqa: BLE001
                q.put_nowait(("error", f"ランタイムエラー: {exc}"))
            finally:
                q.put_nowait(("done", None))

        _task = asyncio.create_task(_produce())
        while True:
            kind, data = await q.get()
            if kind in ("delta", "error"):
                yield data
            else:
                break

    def _select_leader(self, members, leader_agent_id):
        """Split squad members into a leader and the remaining members.

        The leader agent is stored both as a SquadMember (role="leader") and on
        ``squad.leader_agent_id``. Returning the same agent twice to an agno
        ``Team`` produces a duplicate-member error, so we take the leader from
        the SquadMember rows and exclude it from the extra members.
        """
        leaders = []
        extras = []
        for agent, agent_id in members:
            if leader_agent_id and agent_id == leader_agent_id:
                leaders.append(agent)
            else:
                extras.append((agent, agent_id))

        leader = leaders[0] if leaders else None
        member_agents = [agent for agent, _ in extras]

        if leader is None and member_agents:
            leader = member_agents[0]
            member_agents = member_agents[1:]

        names = [getattr(m, "name", aid) for m, aid in members]
        return leader, member_agents, names

    async def _load_member_agent(self, agent_id: str | None):
        if not agent_id:
            return None
        agent = await self.db.get(AgentModel, agent_id)
        if not agent:
            return None
        cfg = await self._load_full_agent_config(agent)
        return await AgentFactory.create_agent(cfg)

    async def _load_team_members(self):
        result = await self.db.execute(
            select(SquadMember).where(SquadMember.squad_id == self.squad.id).order_by(SquadMember.sort_order.asc())
        )
        members = []
        for row in result.scalars().all():
            agent = await self.db.get(AgentModel, row.agent_id)
            if agent:
                cfg = await self._load_full_agent_config(agent)
                members.append((await AgentFactory.create_agent(cfg), row.agent_id))
        return members

    async def _load_full_agent_config(self, agent: AgentModel):
        """Load skills + MCP servers for a member agent so the Team members
        keep their Tools/MCP/Skills wiring (mirrors AgentRuntime._load_agent_definition)."""
        skills = []
        if agent.skill_ids:
            result = await self.db.execute(
                select(Skill).where(Skill.id.in_(agent.skill_ids))
            )
            skills = list(result.scalars().all())

        mcp_ids = agent.mcp_server_ids or []
        if agent.mcp_server_id:
            mcp_ids = [agent.mcp_server_id] + [i for i in mcp_ids if i != agent.mcp_server_id]
        mcps = []
        for mcp_id in mcp_ids:
            mcp = await self.db.get(MCPServer, mcp_id)
            if mcp:
                mcps.append(mcp)

        cfg = self._agent_config(agent)
        cfg.skills = skills
        cfg.mcp = mcps
        return cfg

    def _agent_config(self, agent: AgentModel):
        class _Cfg:
            pass

        cfg = _Cfg()
        cfg.title = agent.title
        cfg.system_prompt = agent.system_prompt
        cfg.model_provider = agent.model_provider
        cfg.model_id = agent.model_id
        cfg.skill_ids = agent.skill_ids or []
        cfg.mcp_server_id = agent.mcp_server_id
        cfg.skills = []
        cfg.mcp = None
        cfg.tools_config = agent.tools_config or {}
        cfg.workspace_config = agent.workspace_config or {}
        cfg.skills_config = agent.skills_config or {}
        cfg.mcp_tools_config = agent.mcp_tools_config or {}
        return cfg


def _load_model(provider: str, model_id: str):
    provider = (provider or "").strip().lower()
    if provider == "openai":
        return OpenAIChat(id=model_id)
    if provider == "anthropic":
        return Claude(id=model_id)
    if provider == "google":
        return Gemini(id=model_id, api_key=__import__("os").getenv("GOOGLE_API_KEY"))
    if provider == "ollama":
        return Ollama(id=model_id, api_key=__import__("os").getenv("OLLAMA_API_KEY"))
    if provider == "openrouter":
        return OpenRouter(id=model_id)
    if provider == "azure_openai":
        return AzureOpenAI(id=model_id)
    if provider == "azure_ai":
        return AzureAIFoundry(id=model_id)
    raise ValueError(f"Unsupported model provider: {provider!r}")
