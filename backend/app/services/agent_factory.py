from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.models.anthropic import Claude
from agno.models.google import Gemini
from agno.models.ollama import Ollama
from agno.models.openrouter import OpenRouter
from agno.models.azure import AzureOpenAI, AzureAIFoundry
from agno.team import Team, TeamMode
from agno.tools import Function
from agno.tools.mcp import MCPTools
from agno.tools.workspace import Workspace
from agno.tools.local_file_system import LocalFileSystemTools
from agno.skills import Skills, LocalSkills
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from app.models.agent import Agent as AgentModel
from app.models.skill import Skill
from app.models.mcp import MCPServer


def _normalize_db_url(db_url: str) -> str:
    if not db_url:
        return "postgresql+asyncpg://nada:nada@db:5432/nada"
    if db_url.startswith("postgresql+psycopg://"):
        return db_url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
    if db_url.startswith("postgresql://"):
        return db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return db_url


def _build_async_engine(db_url: str):
    from sqlalchemy.ext.asyncio import create_async_engine
    return create_async_engine(
        _normalize_db_url(db_url),
        pool_pre_ping=True,
        pool_recycle=300,
    )


_async_engine = None
_agno_db = None


def init_agno_db():
    get_agno_postgres_db()


def get_agno_postgres_db():
    import os
    from agno.db.postgres import AsyncPostgresDb
    global _async_engine, _agno_db
    if _agno_db is None:
        db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://nada:nada@db:5432/nada")
        _async_engine = _build_async_engine(db_url)
        _agno_db = AsyncPostgresDb(
            db_url=db_url,
            db_engine=_async_engine,
            session_table="sessions",
            create_schema=True,
        )
    return _agno_db


async def close_agno_postgres_db():
    global _async_engine, _agno_db
    if _agno_db is not None:
        try:
            await _agno_db.close()
        except Exception:
            pass
        _agno_db = None
    if _async_engine is not None:
        try:
            await _async_engine.dispose()
        except Exception:
            pass
        _async_engine = None


def _load_model(provider: str, model_id: str):
    provider = (provider or "").strip().lower()
    if provider == "openai":
        return OpenAIChat(id=model_id)
    if provider == "anthropic":
        return Claude(id=model_id)
    if provider == "google":
        import os
        return Gemini(id=model_id, api_key=os.getenv("GOOGLE_API_KEY"))
    if provider == "ollama":
        import os
        return Ollama(id=model_id, api_key=os.getenv("OLLAMA_API_KEY"))
    if provider == "openrouter":
        return OpenRouter(id=model_id)
    if provider == "azure_openai":
        return AzureOpenAI(id=model_id)
    if provider == "azure_ai":
        return AzureAIFoundry(id=model_id)
    raise ValueError(f"Unsupported model provider: {provider!r}")


_TOOLKIT_ALIASES = {
    "WebSearchTools": "agno.tools.websearch",
    "PandasTools": "agno.tools.pandas",
    "ShellTools": "agno.tools.shell",
    "LocalFileSystemTools": "agno.tools.local_file_system",
    "PythonTools": "agno.tools.python",
    "SleepTools": "agno.tools.sleep",
    "NanoBananaTools": "agno.tools.nano_banana",
    "SalesforceTools": "agno.tools.salesforce",
    "WebBrowserTools": "agno.tools.webbrowser",
    "GitLabTools": "agno.tools.gitlab",
}


def _load_toolkit_class(name: str):
    if name in _TOOLKIT_ALIASES:
        module_path = _TOOLKIT_ALIASES[name]
    elif "." in name:
        module_path, _, class_name = name.rpartition(".")
        if not module_path:
            module_path = "agno.tools"
        name = class_name
    else:
        module_path = "agno.tools"

    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, name)


def _build_toolkit_tools(tools_config):
    tools = []
    if not tools_config:
        return tools

    if isinstance(tools_config, str):
        entries = [tools_config]
    else:
        entries = tools_config.get("tools", []) or []

    for entry in entries:
        if entry is None:
            continue
        if isinstance(entry, str):
            name = entry
            params = {}
        else:
            name = entry.get("name") or entry.get("class")
            params = entry.get("params") or entry.get("config") or {}
        if not name:
            continue
        try:
            cls = _load_toolkit_class(name)
            instance = cls(**params)
            tools.append(instance)
        except Exception:
            continue
    return tools


def _build_workspace(workspace_config):
    if not workspace_config:
        return None
    target_directory = workspace_config.get("target_directory") or "./output"
    try:
        return Workspace(target_directory=target_directory)
    except Exception:
        return None


def _build_skills(skills_config):
    if not skills_config:
        return None
    loaders = []
    for loader in skills_config.get("loaders", []) or []:
        loader_type = loader.get("type")
        if loader_type == "local":
            path = loader.get("path") or "."
            loaders.append(LocalSkills(path))
    if not loaders:
        return None
    return Skills(loaders=loaders)


def _build_mcp_tools(mcp_tools_config):
    if not mcp_tools_config:
        return []
    tools = []
    for server in mcp_tools_config.get("servers", []) or []:
        config = server if isinstance(server, dict) else {}
        transport = (config.get("type") or "stdio").strip().lower()
        try:
            if transport == "stdio":
                command = config.get("command") or ""
                args = config.get("args") or []
                if not command:
                    continue
                if args:
                    command = f"{command} {' '.join(str(a) for a in args)}"
                tools.append(MCPTools(command=command, transport="stdio"))
            else:
                url = config.get("url") or ""
                if not url:
                    continue
                tools.append(MCPTools(url=url, transport=transport))
        except Exception:
            continue
    return tools


def _build_skill_tools(skills):
    tools = []
    for skill in skills:
        def skill_entrypoint(*args, skill=skill, **kwargs):
            return f"Skill {skill.name} executed: {skill.description or skill.name}"

        tools.append(
            Function(
                name=f"skill_{skill.id}",
                description=skill.description or f"Use skill {skill.name}",
                parameters={"type": "object", "properties": {}, "additionalProperties": True},
                instructions=skill.content,
                entrypoint=skill_entrypoint,
            )
        )
    return tools


def _build_mcp_tool(mcp):
    if not mcp:
        return []

    config = mcp.config or {}
    # The `config` dict is authoritative (the frontend only writes `config`);
    # the url/transport columns are legacy/placeholder and must not override it.
    transport = (config.get("type") or mcp.transport or "stdio").strip().lower()

    if transport == "stdio":
        command = config.get("command") or mcp.url or ""
        args = config.get("args") or []
        if not command:
            return []
        if args:
            command = f"{command} {' '.join(str(a) for a in args)}"
        mcp_tools = MCPTools(command=command, transport="stdio")
    else:
        url = config.get("url") or mcp.url or ""
        if not url:
            return []
        mcp_tools = MCPTools(url=url, transport=transport)

    return [mcp_tools]


class AgentFactory:
    @staticmethod
    async def create_agent(config, *, session_id=None, user_id=None):
        model = _load_model(config.model_provider, config.model_id)
        tools = []

        tools.extend(_build_toolkit_tools(getattr(config, "tools_config", None)))

        workspace = _build_workspace(getattr(config, "workspace_config", None))
        if workspace:
            tools.append(workspace)

        skills = _build_skills(getattr(config, "skills_config", None))

        mcp_tools = _build_mcp_tools(getattr(config, "mcp_tools_config", None))
        for mcp_tool in mcp_tools:
            try:
                await mcp_tool.connect()
                tools.append(mcp_tool)
            except (Exception, BaseExceptionGroup, asyncio.CancelledError) as exc:
                # Do not abort agent creation if MCP connect fails or is cancelled.
                print(f"[MCP] inline mcp connect aborted: {type(exc).__name__}: {exc}")

        if getattr(config, "skills", None):
            tools.extend(_build_skill_tools(config.skills))

        if getattr(config, "mcp", None):
            for single_mcp in config.mcp:
                selected_mcp_tools = _build_mcp_tool(single_mcp)
                for mcp_tool in selected_mcp_tools:
                    try:
                        await mcp_tool.connect()
                        tools.append(mcp_tool)
                    except (Exception, BaseExceptionGroup, asyncio.CancelledError) as exc:
                        # Do not abort agent creation if MCP connect fails or is cancelled.
                        print(f"[MCP] selected mcp connect aborted: {type(exc).__name__}: {exc}")

        db = get_agno_postgres_db()

        kwargs = {
            "db": db,
            "name": config.title,
            "model": model,
            "instructions": config.system_prompt,
            "tools": tools,
            "session_id": session_id,
            "user_id": user_id,
            "add_history_to_context": True,
            "num_history_runs":3,
            "metadata": {
                "skill_ids": getattr(config, "skill_ids", []),
                "mcp_server_id": getattr(config, "mcp_server_id", None),
            },
        }
        if skills:
            kwargs["skills"] = skills

        return Agent(**kwargs)
