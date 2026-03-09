"""Client module for rest api client."""

from __future__ import annotations

import base64
import json
import logging
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid

from riskapp_client.adapters.mappers.action_assessment_mapper import (
    action_from_mapping,
    assessment_from_mapping,
)
from riskapp_client.adapters.mappers.scored_entity_mapper import (
    scored_entity_from_mapping,
)
from riskapp_client.domain.domain_models import (
    Action,
    Assessment,
    Member,
    Opportunity,
    Project,
    Risk,
)
from riskapp_client.domain.scored_entity_fields import SCORED_ENTITY_META_KEYS
from riskapp_client.utils.url_validation_helpers import UrlPolicy, validate_base_url

_MAX_RESPONSE_BYTES = 5_000_000  # 5 MB defensive cap for JSON payloads

logger = logging.getLogger(__name__)


class _SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Allow redirects only within the original scheme+netloc.

    This defends against malicious/compromised servers redirecting the client to
    unexpected origins (a common SSRF-esque pivot for desktop apps).
    """

    def __init__(self, *, allowed_scheme: str, allowed_netloc: str) -> None:
        """Internal helper for init."""
        super().__init__()
        self._allowed_scheme = allowed_scheme
        self._allowed_netloc = allowed_netloc

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        """Handle redirect request."""
        parsed = urllib.parse.urlparse(newurl)
        if parsed.scheme and parsed.scheme != self._allowed_scheme:
            raise urllib.error.HTTPError(
                newurl, code, "Refusing cross-scheme redirect", headers, fp
            )
        if parsed.netloc and parsed.netloc != self._allowed_netloc:
            raise urllib.error.HTTPError(
                newurl, code, "Refusing cross-origin redirect", headers, fp
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _jwt_sub(token: str) -> str | None:
    """Internal helper for jwt sub."""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        data = json.loads(
            base64.urlsafe_b64decode(payload_b64.encode("ascii")).decode("utf-8")
        )
        return str(data.get("sub")) if data.get("sub") else None
    except Exception:
        return None


class FakeBackend:
    """Represent Fake Backend."""

    def __init__(self) -> None:
        """Internal helper for init."""
        p1 = Project(id=str(uuid.uuid4()), name="MPR Project", description="Fake data")
        p2 = Project(
            id=str(uuid.uuid4()), name="Demo Project", description="More fake data"
        )
        self.projects: list[Project] = [p1, p2]
        self.risks: dict[str, list[Risk]] = {
            p1.id: [
                Risk(
                    id=str(uuid.uuid4()),
                    project_id=p1.id,
                    title="Critical outage",
                    probability=5,
                    impact=5,
                ),
                Risk(
                    id=str(uuid.uuid4()),
                    project_id=p1.id,
                    title="Supplier delay",
                    probability=4,
                    impact=5,
                ),
                Risk(
                    id=str(uuid.uuid4()),
                    project_id=p1.id,
                    title="Scope creep",
                    probability=3,
                    impact=4,
                ),
            ],
            p2.id: [
                Risk(
                    id=str(uuid.uuid4()),
                    project_id=p2.id,
                    title="Minor bug",
                    probability=2,
                    impact=2,
                ),
            ],
        }
        self.opportunities: dict[str, list[Opportunity]] = {
            p1.id: [
                Opportunity(
                    id=str(uuid.uuid4()),
                    project_id=p1.id,
                    title="Automation savings",
                    probability=3,
                    impact=4,
                ),
                Opportunity(
                    id=str(uuid.uuid4()),
                    project_id=p1.id,
                    title="Early delivery bonus",
                    probability=2,
                    impact=5,
                ),
            ],
            p2.id: [
                Opportunity(
                    id=str(uuid.uuid4()),
                    project_id=p2.id,
                    title="Reuse components",
                    probability=4,
                    impact=3,
                ),
            ],
        }

        # Minimal in-memory assessments store for demo usage.
        self._assessments: dict[tuple[str, str], list[Assessment]] = {}

    def _sorted_scored(
        self, items: list[Risk] | list[Opportunity]
    ) -> list[Risk] | list[Opportunity]:
        """Internal helper for sorted scored."""
        return sorted(items, key=lambda item: (item.score, item.title), reverse=True)

    def _create_scored(
        self,
        project_id: str,
        store: dict[str, list[Risk]] | dict[str, list[Opportunity]],
        model_cls: type[Risk] | type[Opportunity],
        *,
        title: str,
        probability: int,
        impact: int,
    ) -> Risk | Opportunity:
        """Internal helper for create scored."""
        item = model_cls(
            id=str(uuid.uuid4()),
            project_id=project_id,
            title=title,
            probability=probability,
            impact=impact,
        )
        store.setdefault(project_id, []).append(item)
        return item

    def _update_scored(
        self,
        entity_id: str,
        store: dict[str, list[Risk]] | dict[str, list[Opportunity]],
        model_cls: type[Risk] | type[Opportunity],
        *,
        title: str,
        probability: int,
        impact: int,
        missing_message: str,
    ) -> Risk | Opportunity:
        """Internal helper for update scored."""
        for items in store.values():
            for index, item in enumerate(items):
                if item.id == entity_id:
                    items[index] = model_cls(
                        id=item.id,
                        project_id=item.project_id,
                        title=title,
                        probability=probability,
                        impact=impact,
                    )
                    return items[index]
        raise KeyError(missing_message)

    def list_projects(self) -> list[Project]:
        """Return projects."""
        return list(self.projects)

    def list_risks(self, project_id: str) -> list[Risk]:
        """Return risks."""
        return list(self._sorted_scored(self.risks.get(project_id, [])))

    def create_risk(
        self, project_id: str, title: str, probability: int, impact: int
    ) -> Risk:
        """Create risk."""
        return self._create_scored(
            project_id,
            self.risks,
            Risk,
            title=title,
            probability=probability,
            impact=impact,
        )

    def update_risk(
        self, risk_id: str, title: str, probability: int, impact: int
    ) -> Risk:
        """Update risk."""
        return self._update_scored(
            risk_id,
            self.risks,
            Risk,
            title=title,
            probability=probability,
            impact=impact,
            missing_message="risk not found",
        )

    def list_opportunities(self, project_id: str) -> list[Opportunity]:
        """Return opportunities."""
        return list(self._sorted_scored(self.opportunities.get(project_id, [])))

    def create_opportunity(
        self, project_id: str, title: str, probability: int, impact: int
    ) -> Opportunity:
        """Create opportunity."""
        return self._create_scored(
            project_id,
            self.opportunities,
            Opportunity,
            title=title,
            probability=probability,
            impact=impact,
        )

    def update_opportunity(
        self, opportunity_id: str, title: str, probability: int, impact: int
    ) -> Opportunity:
        """Update opportunity."""
        return self._update_scored(
            opportunity_id,
            self.opportunities,
            Opportunity,
            title=title,
            probability=probability,
            impact=impact,
            missing_message="opportunity not found",
        )

    def list_assessments(
        self, project_id: str, item_type: str, item_id: str
    ) -> list[Assessment]:
        """Return assessments."""
        _ = item_type  # unused (items share UUID space in the demo)
        return list(self._assessments.get((project_id, item_id), []))

    def upsert_my_assessment(
        self,
        project_id: str,
        item_type: str,
        item_id: str,
        probability: int,
        impact: int,
        notes: str | None = None,
    ) -> Assessment:
        """Insert or update my assessment."""
        assessor = "demo-user"
        aid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"assessment:{item_id}:{assessor}"))
        a = Assessment(
            id=aid,
            item_id=item_id,
            assessor_user_id=assessor,
            probability=int(probability),
            impact=int(impact),
            notes=(notes or ""),
            version=1,
            is_deleted=False,
            updated_at="",
        )
        self._assessments[(project_id, item_id)] = [a]
        return a


class ApiError(RuntimeError):
    """Represent Api Error."""

    def __init__(self, status: int, detail: str) -> None:
        """Internal helper for init."""
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


class ApiBackend:
    """
    Thin HTTP client for the FastAPI backend.
    Auth:
        - POST /login (x-www-form-urlencoded: username, password) -> access_token
    Core:
        - GET  /projects
        - POST /projects
        - GET  /projects/{project_id}/risks
        - POST /projects/{project_id}/risks
        - PATCH /projects/{project_id}/risks/{risk_id}
    """

    def __init__(
        self,
        base_url: str,
        email: str,
        password: str,
        *,
        auto_create_project: bool = True,
        timeout_s: int = 6,
        url_policy: UrlPolicy | None = None,
    ) -> None:
        """Internal helper for init."""
        if url_policy is None:
            url_policy = UrlPolicy(
                allow_http_anywhere=os.getenv("RISKAPP_ALLOW_HTTP", "").strip() == "1"
            )
        self.base_url = validate_base_url(base_url, url_policy)
        parsed_base = urllib.parse.urlparse(self.base_url)
        handlers: list[urllib.request.BaseHandler] = [
            _SameOriginRedirectHandler(
                allowed_scheme=parsed_base.scheme,
                allowed_netloc=parsed_base.netloc,
            )
        ]
        # Explicit TLS context (defensive; uses system trust store).
        if parsed_base.scheme == "https":
            ssl_context = ssl.create_default_context()
            handlers.insert(0, urllib.request.HTTPSHandler(context=ssl_context))
        self._opener = urllib.request.build_opener(*handlers)
        self.email = email
        self.timeout_s = timeout_s
        self.auto_create_project = auto_create_project
        self.user_id: str | None = None
        self.token: str | None = None
        self.refresh_token: str | None = None
        self._login(password)

    def _req(
        self,
        method: str,
        path: str,
        *,
        json_body: object | None = None,
        form_body: dict[str, str] | None = None,
        auth: bool = True,
        _retry_on_401: bool = True,
    ) -> object | None:
        """Make a JSON/form HTTP request and return decoded JSON.

        Security notes:
        - `path` must be a relative API path starting with '/'.
        - redirects are restricted to the original origin via `_SameOriginRedirectHandler`.
        - responses are size-capped to `_MAX_RESPONSE_BYTES`.
        """
        if not path.startswith("/"):
            raise ValueError("API path must start with '/'")
        method_up = (method or "").strip().upper()
        if method_up not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise ValueError(f"Unsupported HTTP method: {method_up}")
        url = f"{self.base_url}{path}"
        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": "RiskAppClient/1.0",
        }
        data: bytes | None = None
        if auth:
            if not self.token:
                raise ApiError(401, "Not logged in")
            headers["Authorization"] = f"Bearer {self.token}"
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif form_body is not None:
            data = urllib.parse.urlencode(form_body).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers, method=method_up)
        try:
            with self._opener.open(req, timeout=self.timeout_s) as resp:
                content_type = (
                    (resp.headers.get("Content-Type") or "")
                    .split(";", 1)[0]
                    .strip()
                    .lower()
                )
                raw_bytes = resp.read(_MAX_RESPONSE_BYTES + 1)
                if len(raw_bytes) > _MAX_RESPONSE_BYTES:
                    raise ApiError(0, "Response too large")
                raw = raw_bytes.decode("utf-8")
                if not raw:
                    return None
                if content_type not in {"application/json", ""}:
                    raise ApiError(0, f"Unexpected Content-Type: {content_type}")
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw else {}
                detail = payload.get("detail", raw)
            except Exception:
                detail = raw
            if exc.code == 401 and auth and _retry_on_401 and self.refresh_token:
                try:
                    self._refresh_access_token()
                    return self._req(
                        method,
                        path,
                        json_body=json_body,
                        form_body=form_body,
                        auth=auth,
                        _retry_on_401=False,
                    )
                except Exception:
                    pass
            raise ApiError(exc.code, str(detail)) from exc

        except urllib.error.URLError as exc:
            raise ApiError(0, f"Cannot reach server: {exc}") from exc

    def _login(self, password: str) -> None:
        """Internal helper for login."""
        j = self._req(
            "POST",
            "/login",
            form_body={"username": self.email, "password": password},
            auth=False,
        )
        token = (j or {}).get("access_token")
        if not token:
            raise ApiError(401, f"Login failed: {j}")
        self.token = token
        self.refresh_token = (j or {}).get("refresh_token")
        self.user_id = _jwt_sub(token)

    def _refresh_access_token(self) -> None:
        """Internal helper for refresh access token."""
        if not self.refresh_token:
            raise ApiError(401, "Missing refresh token")
        j = self._req(
            "POST",
            "/refresh",
            json_body={"refresh_token": self.refresh_token},
            auth=False,
            _retry_on_401=False,
        )
        token = (j or {}).get("access_token")
        if not token:
            raise ApiError(401, f"Refresh failed: {j}")
        self.token = token
        if (j or {}).get("refresh_token"):
            self.refresh_token = (j or {}).get("refresh_token")
        self.user_id = _jwt_sub(token)

    def _to_project(self, j) -> Project:
        """Internal helper for to project."""
        return Project(
            id=str(j["id"]),
            name=j.get("name", ""),
            description=j.get("description") or "",
        )

    def _to_risk(self, j) -> Risk:
        """Internal helper for to risk."""
        return scored_entity_from_mapping(j, model_cls=Risk)

    def _to_opportunity(self, j) -> Opportunity:
        """Internal helper for to opportunity."""
        return scored_entity_from_mapping(j, model_cls=Opportunity)

    def _to_action(self, j) -> Action:
        """Internal helper for to action."""
        return action_from_mapping(j)

    def _build_scored_payload(
        self, title: str, probability: int, impact: int, meta: dict
    ) -> dict:
        """Helper to build consistent JSON payload for Risks and Opportunities."""
        body = {"title": title, "probability": int(probability), "impact": int(impact)}
        for k in SCORED_ENTITY_META_KEYS:
            v = meta.get(k)
            if v is not None and str(v).strip() != "":
                body[k] = v
        return body

    def _build_list_qs(self, **kwargs) -> str:
        """Build URL query string while omitting None values."""
        params = {
            k: str(int(v)) if isinstance(v, bool) else str(v)
            for k, v in kwargs.items()
            if v is not None
        }
        return urllib.parse.urlencode(params)

    def list_projects(self) -> list[Project]:
        """Return projects."""
        j = self._req("GET", "/projects")
        projects = [self._to_project(x) for x in (j or [])]
        if not projects and self.auto_create_project:
            created = self._req(
                "POST",
                "/projects",
                json_body={"name": "MPR Project", "description": "auto-created"},
            )
            if created:
                projects = [self._to_project(created)]
        return projects

    def create_project(self, *, name: str, description: str = "") -> Project:
        """Create a project on the server.

        This is used by the offline-first sync when promoting a local-only project
        to a real server project.
        """
        body = {"name": str(name or "Project"), "description": str(description or "")}
        j = self._req("POST", "/projects", json_body=body)
        return self._to_project(j)

    def _to_assessment(self, j) -> Assessment:
        """Internal helper for to assessment."""
        return assessment_from_mapping(j)

    # --- Opportunities ---

    def list_opportunities(
        self,
        project_id: str,
        *,
        search: str | None = None,
        min_score: int | None = None,
        max_score: int | None = None,
        status: str | None = None,
        category: str | None = None,
        owner_user_id: str | None = None,
        owner_unassigned: bool | None = None,
        from_date: str | None = None,  # "YYYY-MM-DD"
        to_date: str | None = None,  # "YYYY-MM-DD"
    ) -> list[Opportunity]:
        """Return opportunities."""
        qs = self._build_list_qs(
            search=search,
            min_score=min_score,
            max_score=max_score,
            status=status,
            category=category,
            owner_user_id=owner_user_id,
            owner_unassigned=owner_unassigned,
            from_date=from_date,
            to_date=to_date,
        )

        path = f"/projects/{project_id}/opportunities" + (f"?{qs}" if qs else "")
        j = self._req("GET", path)
        return [self._to_opportunity(x) for x in (j or [])]

    def opportunities_report(
        self,
        project_id: str,
        *,
        search: str | None = None,
        min_score: int | None = None,
        max_score: int | None = None,
        status: str | None = None,
        category: str | None = None,
        owner_user_id: str | None = None,
        owner_unassigned: bool | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict:
        """Handle opportunities report."""
        qs = self._build_list_qs(
            search=search,
            min_score=min_score,
            max_score=max_score,
            status=status,
            category=category,
            owner_user_id=owner_user_id,
            owner_unassigned=owner_unassigned,
            from_date=from_date,
            to_date=to_date,
        )
        path = f"/projects/{project_id}/opportunities/report" + (f"?{qs}" if qs else "")
        return dict(self._req("GET", path) or {})

    def create_opportunity(
        self, project_id: str, *, title: str, probability: int, impact: int, **meta
    ) -> Opportunity:
        """Create opportunity."""
        body = self._build_scored_payload(title, probability, impact, meta)
        j = self._req("POST", f"/projects/{project_id}/opportunities", json_body=body)
        return self._to_opportunity(j)

    def update_opportunity(
        self,
        project_id: str,
        opportunity_id: str,
        *,
        title: str,
        probability: int,
        impact: int,
        base_version: int | None = None,
        **meta,
    ) -> Opportunity:
        """Update opportunity."""
        body = self._build_scored_payload(title, probability, impact, meta)

        if base_version is not None:
            body["base_version"] = int(base_version)

        j = self._req(
            "PATCH",
            f"/projects/{project_id}/opportunities/{opportunity_id}",
            json_body=body,
        )
        return self._to_opportunity(j)

    def delete_opportunity(self, project_id: str, opportunity_id: str) -> None:
        """Delete opportunity."""
        self._req(
            "DELETE",
            f"/projects/{project_id}/opportunities/{opportunity_id}",
        )

    def list_assessments(
        self, project_id: str, item_type: str, item_id: str
    ) -> list[Assessment]:
        """Return assessments."""
        prefix = "risks" if item_type == "risk" else "opportunities"
        j = self._req("GET", f"/projects/{project_id}/{prefix}/{item_id}/assessments")
        return [self._to_assessment(x) for x in (j or [])]

    def upsert_my_assessment(
        self,
        project_id: str,
        item_type: str,
        item_id: str,
        probability: int,
        impact: int,
        notes: str | None = None,
    ) -> Assessment:
        """Insert or update my assessment."""
        prefix = "risks" if item_type == "risk" else "opportunities"
        j = self._req(
            "PUT",
            f"/projects/{project_id}/{prefix}/{item_id}/assessment",
            json_body={
                "probability": int(probability),
                "impact": int(impact),
                "notes": (notes or ""),
            },
        )
        return self._to_assessment(j)

    def current_user_id(self) -> str | None:
        """Handle current user id."""
        return self.user_id

    def list_risks(
        self,
        project_id: str,
        *,
        search: str | None = None,
        min_score: int | None = None,
        max_score: int | None = None,
        status: str | None = None,
        category: str | None = None,
        owner_user_id: str | None = None,
        owner_unassigned: bool | None = None,
        from_date: (
            str | None
        ) = None,  # "YYYY-MM-DD" (or pass a date and .isoformat() before calling)
        to_date: str | None = None,  # "YYYY-MM-DD"
    ) -> list[Risk]:
        """Return risks."""
        qs = self._build_list_qs(
            search=search,
            min_score=min_score,
            max_score=max_score,
            status=status,
            category=category,
            owner_user_id=owner_user_id,
            owner_unassigned=owner_unassigned,
            from_date=from_date,
            to_date=to_date,
        )
        path = f"/projects/{project_id}/risks" + (f"?{qs}" if qs else "")
        j = self._req("GET", path)
        return [self._to_risk(x) for x in (j or [])]

    def risks_report(
        self,
        project_id: str,
        *,
        search: str | None = None,
        min_score: int | None = None,
        max_score: int | None = None,
        status: str | None = None,
        category: str | None = None,
        owner_user_id: str | None = None,
        owner_unassigned: bool | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict:
        """Handle risks report."""
        qs = self._build_list_qs(
            search=search,
            min_score=min_score,
            max_score=max_score,
            status=status,
            category=category,
            owner_user_id=owner_user_id,
            owner_unassigned=owner_unassigned,
            from_date=from_date,
            to_date=to_date,
        )
        path = f"/projects/{project_id}/risks/report" + (f"?{qs}" if qs else "")
        return dict(self._req("GET", path) or {})

    def create_risk(
        self, project_id: str, *, title: str, probability: int, impact: int, **meta
    ) -> Risk:
        """Create risk."""
        body = self._build_scored_payload(title, probability, impact, meta)
        j = self._req("POST", f"/projects/{project_id}/risks", json_body=body)
        return self._to_risk(j)

    def update_risk(
        self,
        project_id: str,
        risk_id: str,
        *,
        title: str,
        probability: int,
        impact: int,
        base_version: int | None = None,
        **meta,
    ) -> Risk:
        """Update risk."""
        body = self._build_scored_payload(title, probability, impact, meta)
        if base_version is not None:
            body["base_version"] = int(base_version)

        j = self._req(
            "PATCH", f"/projects/{project_id}/risks/{risk_id}", json_body=body
        )
        return self._to_risk(j)

    def delete_risk(self, project_id: str, risk_id: str) -> None:
        """Delete risk."""
        self._req("DELETE", f"/projects/{project_id}/risks/{risk_id}")

    def sync_pull(
        self,
        project_id: str,
        since_iso: str,
        *,
        limit_per_entity: int | None = None,
        cursors: dict[str, str] | None = None,
    ):
        """Synchronize pull."""
        body: dict[str, object] = {"project_id": project_id, "since": since_iso}
        if limit_per_entity is not None:
            body["limit_per_entity"] = int(limit_per_entity)
            if cursors:
                body["cursors"] = cursors
        return self._req("POST", f"/projects/{project_id}/sync/pull", json_body=body)

    def sync_push(self, project_id: str, changes):
        """Synchronize push."""
        return self._req(
            "POST",
            f"/projects/{project_id}/sync/push",
            json_body={"project_id": project_id, "changes": changes},
        )

    def create_snapshot(self, project_id: str, *, kind: str | None = None):
        """Create snapshot."""
        if kind:
            qs = urllib.parse.urlencode({"kind": kind})
            return self._req("POST", f"/projects/{project_id}/snapshots?{qs}")
        return self._req("POST", f"/projects/{project_id}/snapshots")

    def latest_snapshot(self, project_id: str, *, kind: str = "risks"):
        """Handle latest snapshot."""
        qs = urllib.parse.urlencode({"kind": kind})
        return self._req("GET", f"/projects/{project_id}/snapshots/latest?{qs}")

    def list_actions(self, project_id: str) -> list[Action]:
        """Return actions."""
        j = self._req("GET", f"/projects/{project_id}/actions")
        return [self._to_action(x) for x in (j or [])]

    def create_action(
        self,
        project_id: str,
        *,
        target_type: str,
        target_id: str,
        kind: str,
        title: str,
        description: str,
        status: str,
        owner_user_id: str | None,
    ) -> Action:
        """Create action."""
        body = {
            "kind": kind,
            "title": title,
            "description": description or None,
            "owner_user_id": owner_user_id,
        }
        if status:
            body["status"] = status
        if target_type == "risk":
            body["risk_id"] = target_id
        else:
            body["opportunity_id"] = target_id

        j = self._req("POST", f"/projects/{project_id}/actions", json_body=body)
        return self._to_action(j)

    def update_action(
        self,
        project_id: str,
        action_id: str,
        *,
        target_type: str,
        target_id: str,
        kind: str,
        title: str,
        description: str,
        status: str,
        owner_user_id: str | None,
    ) -> Action:
        """Update action."""
        body = {
            "kind": kind,
            "title": title,
            "description": description or None,
            "status": status,
            "owner_user_id": owner_user_id,
        }
        if target_type == "risk":
            body["risk_id"] = target_id
            body["opportunity_id"] = None
        else:
            body["risk_id"] = None
            body["opportunity_id"] = target_id

        j = self._req(
            "PATCH", f"/projects/{project_id}/actions/{action_id}", json_body=body
        )
        return self._to_action(j)

    def top_history(
        self,
        project_id: str,
        *,
        kind: str = "risks",
        limit: int = 10,
        from_ts: str | None = None,
        to_ts: str | None = None,
    ):
        """Handle top history."""
        params = {"kind": kind, "limit": str(int(limit))}
        if from_ts:
            params["from_ts"] = from_ts
        if to_ts:
            params["to_ts"] = to_ts
        qs = urllib.parse.urlencode(params)
        return self._req("GET", f"/projects/{project_id}/top-history?{qs}")

    def list_members(self, project_id: str) -> list[Member]:
        """Return members."""
        j = self._req("GET", f"/projects/{project_id}/members")
        out: list[Member] = []
        for m in j or []:
            out.append(
                Member(
                    user_id=str(m.get("user_id") or ""),
                    email=str(m.get("email") or ""),
                    role=str(m.get("role") or ""),
                    created_at=str(m.get("created_at") or "") or None,
                )
            )
        return out

    def add_member(self, project_id: str, *, user_email: str, role: str) -> None:
        """Add member."""
        self._req(
            "POST",
            f"/projects/{project_id}/members",
            json_body={"user_email": user_email, "role": role},
        )

    def remove_member(self, project_id: str, *, member_user_id: str) -> None:
        """Remove member."""
        self._req("DELETE", f"/projects/{project_id}/members/{member_user_id}")
