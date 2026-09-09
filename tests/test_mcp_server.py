"""MCP stdio server tests: protocol classification, root bounding, real stdio.

Protocol-level tests call handle_request() with an explicit bounded
ServerContext; integration tests drive the real ``python -m skillarum mcp``
subprocess over stdin/stdout, including malformed-input negative controls.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from skillarum.generators import DeterministicGenerator
from skillarum.mcp_server import (
    MAX_LINE_BYTES,
    MAX_READ_CHARS,
    PROTOCOL_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
    McpSession,
    ServerContext,
    handle_request,
)
from skillarum.models import PreparedCorpus, PreparedPage
from skillarum.render import render_skill
from skillarum.research import build_evaluation_report, write_evaluation_report
from skillarum.utils import sha256_text

REPO_ROOT = Path(__file__).resolve().parents[1]


def corpus() -> PreparedCorpus:
    return PreparedCorpus(
        profile_id="fixture",
        profile_name="Fixture Site",
        target_id="page",
        skill_name="Fixture-Skill",
        pages=(
            PreparedPage(
                url="https://example.org/page",
                title="Fixture",
                headings=("Intro",),
                text="Source text\nSecond line",
                links=("https://example.org/other",),
                requested_url="https://example.org/page",
                final_url="https://example.org/page",
                fetched_at="now",
                status_code=200,
                content_sha256=sha256_text("Source text\nSecond line"),
            ),
        ),
    )


def make_skill(root: Path) -> Path:
    """Render a real skill package under ``root/output/skills``."""
    prepared = corpus()
    draft = DeterministicGenerator().generate(prepared)
    return render_skill(draft, prepared, root / "output" / "skills")


PROBE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0"


def corpus_with_credential() -> PreparedCorpus:
    """Corpus whose source text carries a truncated (redaction-missed) JWT."""
    return PreparedCorpus(
        profile_id="fixture",
        profile_name="Fixture Site",
        target_id="page",
        skill_name="Fixture-Skill",
        pages=(
            PreparedPage(
                url="https://example.org/page",
                title="Fixture",
                headings=("Intro",),
                text=f"Leaked instructions\nbearer {PROBE_JWT}",
                links=("https://example.org/other",),
                requested_url="https://example.org/page",
                final_url="https://example.org/page",
                fetched_at="now",
                status_code=200,
                content_sha256=sha256_text(f"Leaked instructions\nbearer {PROBE_JWT}"),
            ),
        ),
    )


@pytest.fixture()
def rendered(tmp_path: Path) -> Path:
    return make_skill(tmp_path)


@pytest.fixture()
def rendered_dir(tmp_path: Path) -> Path:
    """A rendered skill under tmp_path so the subprocess root contains it."""
    return make_skill(tmp_path)


@pytest.fixture()
def write_context(tmp_path: Path) -> ServerContext:
    return ServerContext(root=tmp_path, allow_write=True)


@pytest.fixture()
def context(tmp_path: Path) -> ServerContext:
    return ServerContext(root=tmp_path)


def request(method: str, id_: object = 1, **params: object) -> dict[str, object]:
    message: dict[str, object] = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params:
        message["params"] = params
    return message


def fresh_session(context: ServerContext) -> McpSession:
    """A session that has completed the initialize handshake."""
    session = McpSession(context=context)
    handle_request(
        request(
            "initialize",
            id_=0,
            protocolVersion=PROTOCOL_VERSION,
            clientInfo={"name": "pytest"},
        ),
        session=session,
    )
    handle_request(
        {"jsonrpc": "2.0", "method": "notifications/initialized"}, session=session
    )
    return session


def handle(message: dict[str, object], context: ServerContext):
    """Serve one message on a freshly initialized session."""
    return handle_request(message, session=fresh_session(context))


def call(context: ServerContext, name: str, **arguments: object):
    return handle(request("tools/call", name=name, arguments=arguments), context)


# --- lifecycle and negotiation -------------------------------------------------


@pytest.mark.parametrize("version", SUPPORTED_PROTOCOL_VERSIONS)
def test_initialize_echoes_supported_client_version(version: str):
    # initialize is exempt from the initialized-session gate, so a raw
    # single-shot request is the real first-contact path.
    response = handle_request(
        request(
            "initialize",
            protocolVersion=version,
            clientInfo={"name": "pytest"},
        ),
        ServerContext(root=Path.cwd()),
    )
    assert response["result"]["protocolVersion"] == version


def test_initialize_falls_back_to_latest_for_unknown_version():
    response = handle_request(
        request(
            "initialize",
            protocolVersion="1999-01-01",
            clientInfo={"name": "pytest"},
        ),
        ServerContext(root=Path.cwd()),
    )
    assert response["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert PROTOCOL_VERSION == max(SUPPORTED_PROTOCOL_VERSIONS)


def test_initialize_without_version_returns_latest():
    response = handle_request(
        request("initialize", clientInfo={"name": "pytest"}),
        ServerContext(root=Path.cwd()),
    )
    assert response["result"]["protocolVersion"] == PROTOCOL_VERSION


def test_initialize_reports_capabilities_and_server_info():
    result = handle_request(
        request(
            "initialize",
            protocolVersion=PROTOCOL_VERSION,
            clientInfo={"name": "pytest"},
        ),
        ServerContext(root=Path.cwd()),
    )["result"]
    assert set(result["capabilities"]) == {"tools", "resources", "prompts"}
    assert result["serverInfo"]["name"] == "skillarum"
    assert result["serverInfo"]["version"]


def test_initialize_requires_client_info():
    context = ServerContext(root=Path.cwd())
    missing = handle_request(request("initialize"), context)
    assert missing["error"]["code"] == -32602
    empty = handle_request(request("initialize", clientInfo={"name": "  "}), context)
    assert empty["error"]["code"] == -32602
    non_object = handle_request(request("initialize", clientInfo="pytest"), context)
    assert non_object["error"]["code"] == -32602
    non_string_version = handle_request(
        request("initialize", protocolVersion=7, clientInfo={"name": "pytest"}),
        context,
    )
    assert non_string_version["error"]["code"] == -32602


def test_ping():
    assert handle(request("ping", id_=7), ServerContext(root=Path.cwd())) == {
        "jsonrpc": "2.0",
        "id": 7,
        "result": {},
    }


# --- request classification (malformed-input defect controls) ------------------


def test_missing_jsonrpc_field_is_invalid_request():
    # DEFECT: a request without "jsonrpc" must not be treated as valid 2.0.
    response = handle({"id": 1, "method": "ping"}, ServerContext(root=Path.cwd()))
    assert response["error"]["code"] == -32600


def test_wrong_jsonrpc_version_is_invalid_request():
    # DEFECT: jsonrpc "1.0" must be rejected, not coerced to 2.0.
    response = handle(
        {"jsonrpc": "1.0", "id": 1, "method": "ping"}, ServerContext(root=Path.cwd())
    )
    assert response["error"]["code"] == -32600


def test_non_object_request_is_invalid_request_with_null_id():
    response = handle(
        [{"jsonrpc": "2.0", "id": 2, "method": "ping"}], ServerContext(root=Path.cwd())
    )
    assert response["error"]["code"] == -32600
    assert response["id"] is None


def test_missing_method_is_invalid_request():
    response = handle({"jsonrpc": "2.0", "id": 1}, ServerContext(root=Path.cwd()))
    assert response["error"]["code"] == -32600


def test_explicit_null_id_is_invalid_request():
    response = handle(
        {"jsonrpc": "2.0", "id": None, "method": "ping"}, ServerContext(root=Path.cwd())
    )
    assert response["error"]["code"] == -32600


def test_notifications_never_get_responses():
    context = ServerContext(root=Path.cwd())
    assert (
        handle({"jsonrpc": "2.0", "method": "notifications/initialized"}, context)
        is None
    )
    assert handle({"jsonrpc": "2.0", "method": "notifications/bogus"}, context) is None


def test_unknown_method_is_method_not_found():
    response = handle(request("bogus", id_=3), ServerContext(root=Path.cwd()))
    assert response["error"]["code"] == -32601


def test_params_must_be_object():
    response = handle(
        {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": [1]},
        ServerContext(root=Path.cwd()),
    )
    assert response["error"]["code"] == -32602


def test_unknown_tool_is_invalid_params():
    response = call(ServerContext(root=Path.cwd()), "no_such_tool")
    assert response["error"]["code"] == -32602
    assert "no_such_tool" in response["error"]["message"]


def test_missing_required_argument_is_invalid_params():
    # DEFECT: argument-level failures are invalid params (-32602), not -32603.
    response = call(ServerContext(root=Path.cwd()), "skillarum_validate")
    assert response["error"]["code"] == -32602


def test_unknown_tool_arguments_rejected():
    response = call(
        ServerContext(root=Path.cwd()), "skillarum_validate", skill_path="x", bogus=1
    )
    assert response["error"]["code"] == -32602


# --- initialized-session state machine ------------------------------------------


def test_requests_before_initialize_are_refused():
    # DEFECT: the server used to serve tools/list before any initialize.
    session = McpSession(context=ServerContext(root=Path.cwd()))
    response = handle_request(request("tools/list", id_=1), session=session)
    assert response["error"]["code"] == -32000
    assert "initialize" in response["error"]["message"]


def test_ping_allowed_before_initialize():
    session = McpSession(context=ServerContext(root=Path.cwd()))
    response = handle_request(request("ping", id_=2), session=session)
    assert response["result"] == {}


def test_notifications_initialized_recorded_without_response():
    session = McpSession(context=ServerContext(root=Path.cwd()))
    assert (
        handle_request(
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            session=session,
        )
        is None
    )
    assert session.initialized is True
    assert session.initialize_responded is False


def test_session_serves_requests_after_initialize():
    session = McpSession(context=ServerContext(root=Path.cwd()))
    hello = handle_request(
        request(
            "initialize",
            protocolVersion="2025-06-18",
            clientInfo={"name": "pytest"},
        ),
        session=session,
    )
    assert hello["result"]["protocolVersion"] == "2025-06-18"
    handle_request(
        {"jsonrpc": "2.0", "method": "notifications/initialized"}, session=session
    )
    listed = handle_request(request("prompts/list", id_=3), session=session)
    assert listed["result"]["prompts"]
    assert session.initialize_responded is True


def test_reinitialize_after_initialize_renegotiates():
    session = McpSession(context=ServerContext(root=Path.cwd()))
    first = handle_request(
        request("initialize", protocolVersion="2025-06-18", clientInfo={"name": "a"}),
        session=session,
    )
    second = handle_request(
        request("initialize", protocolVersion="2025-03-26", clientInfo={"name": "b"}),
        session=session,
    )
    assert first["result"]["protocolVersion"] == "2025-06-18"
    assert second["result"]["protocolVersion"] == "2025-03-26"


def test_failed_initialize_keeps_gate_closed():
    session = McpSession(context=ServerContext(root=Path.cwd()))
    rejected = handle_request(request("initialize"), session=session)
    assert rejected["error"]["code"] == -32602
    response = handle_request(request("prompts/list", id_=4), session=session)
    assert response["error"]["code"] == -32000


# --- root bounding -------------------------------------------------------------


def test_tool_path_outside_root_is_invalid_params(context: ServerContext):
    response = call(context, "skillarum_validate", skill_path="/etc/hosts")
    assert response["error"]["code"] == -32602
    assert "root" in response["error"]["message"]


def test_tool_path_traversal_is_rejected(write_context: ServerContext):
    response = call(
        write_context, "skillarum_validate", skill_path="../outside/SKILL.md"
    )
    assert response["error"]["code"] == -32602


# --- tool behavior --------------------------------------------------------------


def test_validate_returns_metadata_not_file_contents(
    write_context: ServerContext, rendered: Path
):
    result = call(write_context, "skillarum_validate", skill_path=str(rendered))
    payload = result["result"]["structuredContent"]
    assert payload["ok"] is True
    assert payload["skill"]["name"] == "fixture-skill"
    assert "content" not in payload


def test_verify_with_security_policy(write_context: ServerContext, rendered: Path):
    result = call(
        write_context, "skillarum_verify", skill_path=str(rendered), policy="security"
    )
    payload = result["result"]["structuredContent"]
    assert payload["policy"]["policies"] == ["security"]


def test_verify_rejects_unknown_policy(write_context: ServerContext, rendered: Path):
    response = call(
        write_context, "skillarum_verify", skill_path=str(rendered), policy="bogus"
    )
    assert response["error"]["code"] == -32602


def test_verify_policy_findings_never_echo_credentials(
    write_context: ServerContext, tmp_path: Path
):
    # F21: a credential-detector rule must never echo its own match. The
    # truncated JWT survives render-time redaction (it is not a full JWT) but
    # the policy layer still flags it; the excerpt must stay a placeholder.
    prepared = corpus_with_credential()
    draft = DeterministicGenerator().generate(prepared)
    rendered = render_skill(draft, prepared, tmp_path / "output" / "skills")
    result = call(
        write_context,
        "skillarum_verify",
        skill_path=str(rendered),
        policy="security",
    )
    payload = result["result"]["structuredContent"]
    findings = payload["policy"]["findings"]
    secret_findings = [f for f in findings if f["rule"] == "hardcoded_secret"]
    assert secret_findings
    assert all(f["excerpt"] == "<{secret}>" for f in secret_findings)
    assert PROBE_JWT not in json.dumps(result)


def test_tool_execution_failure_is_iserror_result(
    write_context: ServerContext, rendered: Path
):
    missing = rendered.parent / "Missing" / "SKILL.md"
    response = call(write_context, "skillarum_validate", skill_path=str(missing))
    assert "error" not in response
    assert response["result"]["isError"] is True
    assert response["result"]["content"][0]["text"]


def test_index_requires_write_access(context: ServerContext):
    response = call(context, "skillarum_index")
    assert response["result"]["isError"] is True
    assert "--allow-write" in response["result"]["content"][0]["text"]


def test_index_defaults_to_root_output_skills(write_context: ServerContext):
    # DEFECT: omitting skills_dir used to crash with KeyError; it now defaults
    # to <root>/output/skills.
    response = call(write_context, "skillarum_index")
    payload = response["result"]["structuredContent"]
    assert payload["ok"] is True
    default_index = write_context.root / "output" / "skills" / "index.json"
    assert Path(payload["index"]) == default_index
    assert default_index.is_file()
    assert payload["skills"] == 0


def test_discover_lists_rendered_skill(write_context: ServerContext, rendered: Path):
    call(write_context, "skillarum_index")
    result = call(write_context, "skillarum_discover")
    payload = result["result"]["structuredContent"]
    assert [entry["path"] for entry in payload["skills"]] == [
        rendered.relative_to(write_context.default_skills_dir).as_posix()
    ]


def test_discover_without_index_is_iserror(write_context: ServerContext):
    response = call(write_context, "skillarum_discover")
    assert response["result"]["isError"] is True


def test_discover_rejects_symlinked_index(write_context: ServerContext, rendered: Path):
    # DEFECT: a symlinked index.json must not be trusted as discovery state.
    call(write_context, "skillarum_index")
    skills_dir = write_context.root / "output" / "skills"
    real = skills_dir / "index.json"
    real.rename(skills_dir / "real-index.json")
    real.symlink_to(skills_dir / "real-index.json")
    response = call(write_context, "skillarum_discover")
    assert response["result"]["isError"] is True


def test_discover_revalidates_advertised_packages(
    write_context: ServerContext, rendered: Path
):
    # DEFECT: a package advertised by the index that no longer validates must
    # not be returned.
    call(write_context, "skillarum_index")
    index_path = write_context.root / "output" / "skills" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["skills"].append({"path": "Forged/Area/SKILL.md", "portable_name": "Forged"})
    index_path.write_text(json.dumps(index), encoding="utf-8")
    response = call(write_context, "skillarum_discover")
    assert response["result"]["isError"] is True


def test_discover_rejects_forged_card_metadata(
    write_context: ServerContext, rendered: Path
):
    # DEFECT: a stale or forged card must be caught against the package
    # manifest, not returned as advertised.
    call(write_context, "skillarum_index")
    index_path = write_context.root / "output" / "skills" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["skills"][0]["skill_sha256"] = "0" * 64
    index_path.write_text(json.dumps(index), encoding="utf-8")
    response = call(write_context, "skillarum_discover")
    assert response["result"]["isError"] is True
    assert "disagrees" in response["result"]["content"][0]["text"]


def test_read_returns_bounded_skill_text(write_context: ServerContext, rendered: Path):
    full = rendered.read_text(encoding="utf-8")
    response = call(write_context, "skillarum_read", skill_path=str(rendered))
    payload = response["result"]["structuredContent"]
    assert payload["content"] == full
    assert payload["truncated"] is False
    assert payload["size"] == len(full)


def test_read_reports_truncation(write_context: ServerContext, rendered: Path):
    # The read itself is bounded: truncation is detected via a limit+1 sentinel.
    full = rendered.read_text(encoding="utf-8")
    response = call(
        write_context, "skillarum_read", skill_path=str(rendered), max_chars=10
    )
    payload = response["result"]["structuredContent"]
    assert payload["truncated"] is True
    assert payload["size"] == 10
    assert payload["content"] == full[:10]
    assert "max_chars" in payload["hint"]


def test_read_rejects_non_skill_files(context: ServerContext):
    secret = context.root / "secret.txt"
    secret.write_text("do not leak", encoding="utf-8")
    response = call(context, "skillarum_read", skill_path="secret.txt")
    assert response["error"]["code"] == -32602


def test_read_rejects_outside_root(context: ServerContext):
    response = call(context, "skillarum_read", skill_path="/etc/hosts")
    assert response["error"]["code"] == -32602


def test_read_rejects_bad_max_chars(write_context: ServerContext, rendered: Path):
    response = call(
        write_context, "skillarum_read", skill_path=str(rendered), max_chars=10**9
    )
    assert response["error"]["code"] == -32602


# --- evaluation report tool ------------------------------------------------------


def test_report_missing_is_iserror(context: ServerContext):
    response = call(context, "skillarum_report")
    assert response["result"]["isError"] is True
    assert "evaluate" in response["result"]["content"][0]["text"]


def test_report_malformed_is_iserror(context: ServerContext):
    path = context.root / "output" / "reports" / "evaluation-summary.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    response = call(context, "skillarum_report")
    assert response["result"]["isError"] is True


def test_report_returns_validated_identity(write_context: ServerContext):
    write_evaluation_report(
        build_evaluation_report(()),
        write_context.root / "output",
    )
    response = call(write_context, "skillarum_report")
    payload = response["result"]["structuredContent"]
    assert payload["ok"] is True
    assert payload["report"]["report_id"].startswith("evaluation-")
    assert payload["report"]["rating_status"] == "pending"
    assert payload["report"]["observation_count"] == 0
    assert payload["report"]["rating_count"] == 0
    assert payload["report"]["artifact_sha256"]
    assert payload["summary"]["observation_count"] == 0


def test_report_rejects_unknown_arguments(write_context: ServerContext):
    response = call(write_context, "skillarum_report", path="anything")
    assert response["error"]["code"] == -32602


# --- resources -------------------------------------------------------------------


def test_resources_list_is_empty_without_index(context: ServerContext):
    response = handle(request("resources/list"), context)
    assert response["result"] == {"resources": []}


def test_resources_list_advertises_indexed_skills(
    write_context: ServerContext, rendered: Path
):
    call(write_context, "skillarum_index")
    response = handle(request("resources/list"), write_context)
    resources = response["result"]["resources"]
    uris = [item["uri"] for item in resources]
    assert "skillarum://skills/index.json" in uris
    assert any(uri.endswith("Fixture-Skill/SKILL.md") for uri in uris)


def test_resources_read_unknown_uri_is_invalid_params(write_context: ServerContext):
    response = handle(request("resources/read", uri="file:///etc/hosts"), write_context)
    assert response["error"]["code"] == -32602


def test_resources_read_missing_index_is_resource_not_found(
    write_context: ServerContext,
):
    # DEFECT: resources/read failures are JSON-RPC errors, never isError
    # results; a well-formed URI with missing backing content is -32002.
    response = handle(
        request("resources/read", uri="skillarum://skills/index.json"),
        write_context,
    )
    assert response["error"]["code"] == -32002
    assert response["error"]["data"] == {"uri": "skillarum://skills/index.json"}


def test_resources_read_skill_returns_markdown(
    write_context: ServerContext, rendered: Path
):
    call(write_context, "skillarum_index")
    rel = rendered.relative_to(write_context.default_skills_dir).as_posix()
    response = handle(
        request("resources/read", uri=f"skillarum://skills/{rel}"), write_context
    )
    content = response["result"]["contents"][0]
    assert content["mimeType"] == "text/markdown"
    assert content["text"] == rendered.read_text(encoding="utf-8")


def test_resources_read_index_returns_validated_index(
    write_context: ServerContext, rendered: Path
):
    # DEFECT: the index route must revalidate cards instead of returning raw bytes.
    call(write_context, "skillarum_index")
    index_path = write_context.root / "output" / "skills" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["skills"].append({"path": "Forged/Area/SKILL.md", "portable_name": "Forged"})
    index_path.write_text(json.dumps(index), encoding="utf-8")
    response = handle(
        request("resources/read", uri="skillarum://skills/index.json"),
        write_context,
    )
    assert response["error"]["code"] == -32002


def test_resources_templates_list_is_empty(context: ServerContext):
    response = handle(request("resources/templates/list"), context)
    assert response["result"] == {"resourceTemplates": []}


def test_operator_resource_absent(context: ServerContext):
    listed = handle(request("resources/list"), context)["result"]["resources"]
    assert listed == []
    read = handle(request("resources/read", uri="skillarum://operator/skill"), context)
    assert read["error"]["code"] == -32002


def test_operator_resource_present(write_context: ServerContext):
    skill = write_context.root / "skills" / "skillarum" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: skillarum\ndescription: operate skillarum\n---\nbody\n",
        encoding="utf-8",
    )
    listed = handle(request("resources/list"), write_context)["result"]["resources"]
    assert [item["uri"] for item in listed] == ["skillarum://operator/skill"]
    read = handle(
        request("resources/read", uri="skillarum://operator/skill"), write_context
    )
    content = read["result"]["contents"][0]
    assert content["mimeType"] == "text/markdown"
    assert content["text"] == skill.read_text(encoding="utf-8")


# --- prompts ---------------------------------------------------------------------


def test_prompts_list_offers_review_prompt(context: ServerContext):
    response = handle(request("prompts/list"), context)
    names = [item["name"] for item in response["result"]["prompts"]]
    assert names == ["skillarum-review-skill"]


def test_prompts_get_review_prompt(write_context: ServerContext, rendered: Path):
    response = handle(
        request(
            "prompts/get",
            name="skillarum-review-skill",
            arguments={"skill_path": str(rendered)},
        ),
        write_context,
    )
    message = response["result"]["messages"][0]
    assert message["role"] == "user"
    assert "skillarum_validate" in message["content"]["text"]


def test_prompts_get_unknown_prompt_is_invalid_params(context: ServerContext):
    response = handle(request("prompts/get", name="bogus"), context)
    assert response["error"]["code"] == -32602


def test_prompts_get_missing_argument_is_invalid_params(context: ServerContext):
    response = handle(request("prompts/get", name="skillarum-review-skill"), context)
    assert response["error"]["code"] == -32602


# --- real stdio subprocess integration (negative controls) -----------------------


class StdioClient:
    """Drives the real server process line-by-line over stdin/stdout."""

    def __init__(self, cwd: Path, env: dict[str, str] | None = None):
        full_env = dict(os.environ)
        full_env.pop("SKILLARUM_MCP_ROOT", None)
        full_env.pop("SKILLARUM_MCP_ALLOW_WRITE", None)
        # The child runs with cwd=cwd, so a relative PYTHONPATH would not resolve;
        # force the checkout's src/ ahead of any stale installed copy.
        full_env["PYTHONPATH"] = os.pathsep.join(
            [str(REPO_ROOT / "src"), full_env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)
        if env:
            full_env.update(env)
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "skillarum", "mcp"],
            cwd=str(cwd),
            env=full_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def send(self, payload: bytes) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(payload)
        self.proc.stdin.flush()

    def send_json(self, message: object) -> None:
        self.send((json.dumps(message) + "\n").encode("utf-8"))

    def recv(self) -> dict[str, object]:
        assert self.proc.stdout is not None
        line = self.proc.stdout.readline()
        assert line, "server closed stdout unexpectedly"
        return json.loads(line.decode("utf-8"))

    def close(self) -> int:
        assert self.proc.stdin is not None
        self.proc.stdin.close()
        self.proc.wait(timeout=60)
        return self.proc.returncode


def test_stdio_initialize_negotiates_and_survives_notifications(tmp_path: Path):
    client = StdioClient(tmp_path)
    client.send_json(
        request(
            "initialize",
            id_=1,
            protocolVersion="2025-06-18",
            clientInfo={"name": "pytest"},
        )
    )
    hello = client.recv()
    assert hello["id"] == 1
    assert hello["result"]["protocolVersion"] == "2025-06-18"
    client.send_json({"jsonrpc": "2.0", "method": "notifications/initialized"})
    client.send_json(request("ping", id_=2))
    pong = client.recv()  # the notification above produced no line
    assert pong["id"] == 2 and pong["result"] == {}
    assert client.close() == 0


def test_stdio_malformed_input_negative_controls(tmp_path: Path):
    client = StdioClient(tmp_path)
    client.send(b"not json at all\n")
    parse = client.recv()
    # DEFECT: parse errors must include id: null per JSON-RPC error contract.
    assert parse["error"]["code"] == -32700
    assert parse["id"] is None

    client.send(b'[{"jsonrpc": "2.0", "id": 2, "method": "ping"}]\n')
    batch = client.recv()
    assert batch["error"]["code"] == -32600
    assert batch["id"] is None

    client.send(b'{"jsonrpc": "2.0", "id": 3}\n')
    assert client.recv()["error"]["code"] == -32600

    client.send(b'{"jsonrpc": "1.0", "id": 4, "method": "ping"}\n')
    assert client.recv()["error"]["code"] == -32600

    client.send(b"\xff\xfe not utf8\n")
    assert client.recv()["error"]["code"] == -32700

    client.send_json(request("ping", id_=5))
    assert client.recv()["id"] == 5  # loop survived every malformed line
    assert client.close() == 0


def test_stdio_tools_roundtrip_and_root_bounding(tmp_path: Path, rendered_dir: Path):
    client = StdioClient(tmp_path)
    client.send_json(
        request(
            "initialize",
            id_=1,
            protocolVersion="2025-06-18",
            clientInfo={"name": "pytest"},
        )
    )
    assert client.recv()["result"]["protocolVersion"] == "2025-06-18"
    client.send_json(request("tools/list", id_=1))
    tools = client.recv()["result"]["tools"]
    assert [tool["name"] for tool in tools] == [
        "skillarum_discover",
        "skillarum_index",
        "skillarum_validate",
        "skillarum_verify",
        "skillarum_read",
        "skillarum_report",
    ]
    assert all(tool["inputSchema"]["type"] == "object" for tool in tools)

    rel = rendered_dir.relative_to(tmp_path).as_posix()
    client.send_json(
        request(
            "tools/call",
            id_=2,
            name="skillarum_validate",
            arguments={"skill_path": rel},
        )
    )
    result = client.recv()["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["skill"]["name"] == "fixture-skill"

    # DEFECT: tools/call skillarum_index with no arguments must not crash with
    # KeyError; without write access it is refused as a tool execution error.
    client.send_json(request("tools/call", id_=3, name="skillarum_index"))
    refused = client.recv()["result"]
    assert refused["isError"] is True
    assert "--allow-write" in refused["content"][0]["text"]

    client.send_json(
        request(
            "tools/call",
            id_=4,
            name="skillarum_validate",
            arguments={"skill_path": "/etc/hosts"},
        )
    )
    assert client.recv()["error"]["code"] == -32602
    assert client.close() == 0


def test_stdio_index_write_requires_allow_write_env(tmp_path: Path, rendered_dir: Path):
    client = StdioClient(tmp_path, env={"SKILLARUM_MCP_ALLOW_WRITE": "1"})
    client.send_json(
        request(
            "initialize",
            id_=0,
            protocolVersion="2025-06-18",
            clientInfo={"name": "pytest"},
        )
    )
    client.recv()
    client.send_json(request("tools/call", id_=1, name="skillarum_index"))
    payload = client.recv()["result"]["structuredContent"]
    assert payload["ok"] is True
    assert payload["skills"] == 1
    assert (tmp_path / "output" / "skills" / "index.json").is_file()
    assert client.close() == 0


def test_stdio_requests_before_initialize_are_refused(tmp_path: Path):
    # DEFECT: the wire server used to answer tools/list before any initialize.
    client = StdioClient(tmp_path)
    client.send_json(request("tools/list", id_=1))
    refused = client.recv()
    assert refused["error"]["code"] == -32000
    assert "initialize" in refused["error"]["message"]
    client.send_json(
        request(
            "initialize",
            id_=2,
            protocolVersion="2025-06-18",
            clientInfo={"name": "pytest"},
        )
    )
    assert client.recv()["result"]["protocolVersion"] == "2025-06-18"
    client.send_json(request("ping", id_=3))
    assert client.recv()["id"] == 3
    assert client.close() == 0


def test_stdio_oversized_line_is_refused_and_framing_survives(tmp_path: Path):
    # A single input line beyond MAX_LINE_BYTES is refused and drained so the
    # following message stays aligned.
    client = StdioClient(tmp_path)
    oversized = (
        b'{"jsonrpc": "2.0", "id": 1, "method": "ping"'
        + b" " * (MAX_LINE_BYTES + 2)
        + b"\n"
    )
    client.send(oversized)
    refused = client.recv()
    assert refused["error"]["code"] == -32700
    assert "exceeds" in refused["error"]["message"]
    client.send_json(request("ping", id_=2))
    assert client.recv()["id"] == 2
    assert client.close() == 0


# --- boundary negative controls --------------------------------------------------


def test_report_rejects_symlinked_report_path(context: ServerContext):
    outside = context.root.parent / "outside-report.json"
    outside.write_text("{}", encoding="utf-8")
    path = context.root / "output" / "reports" / "evaluation-summary.json"
    path.parent.mkdir(parents=True)
    path.symlink_to(outside)
    response = call(context, "skillarum_report")
    assert response["error"]["code"] == -32602


def test_resources_reject_symlinked_skills_dir(
    write_context: ServerContext, rendered: Path
):
    # A symlinked output/ must not let the skills root escape the server root.
    outside = write_context.root.parent / "outside-skills"
    outside.mkdir()
    output = write_context.root / "output"
    output.rename(write_context.root / "output-real")
    output.symlink_to(outside)
    listed = handle(request("resources/list"), write_context)
    assert listed["error"]["code"] == -32602
    read = handle(
        request("resources/read", uri="skillarum://skills/index.json"), write_context
    )
    assert read["error"]["code"] == -32602


def test_resources_read_rejects_truncated_resource(write_context: ServerContext):
    big = write_context.root / "output" / "skills" / "Big" / "SKILL.md"
    big.parent.mkdir(parents=True)
    big.write_text("x" * (MAX_READ_CHARS + 1), encoding="utf-8")
    response = handle(
        request("resources/read", uri="skillarum://skills/Big/SKILL.md"),
        write_context,
    )
    assert response["error"]["code"] == -32002
    assert "cap" in response["error"]["message"]


def test_tools_call_rejects_non_object_arguments(context: ServerContext):
    for arguments in ([], False, "x"):
        response = handle(
            request("tools/call", name="skillarum_report", arguments=arguments), context
        )
        assert response["error"]["code"] == -32602


def test_resource_failures_are_protocol_errors(write_context, rendered):
    call(write_context, "skillarum_index")
    index = write_context.default_skills_dir / "index.json"
    payload = json.loads(index.read_text())
    payload["skills"][0]["skill_name"] = "Forged label"
    index.write_text(json.dumps(payload))
    response = handle(request("resources/list"), write_context)
    assert response["error"]["code"] == -32602
    assert "disagrees" in response["error"]["message"]


def test_prompt_rejects_empty_non_object_arguments(context):
    response = handle(
        request("prompts/get", name="skillarum-review-skill", arguments=[]), context
    )
    assert response["error"]["code"] == -32602
