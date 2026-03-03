from __future__ import annotations


def test_outbox_squashes_multiple_changes_for_same_entity_id(tmp_path) -> None:
    from riskapp_client.adapters.local_storage.sqlite_data_store import LocalStore
    from riskapp_client.adapters.local_storage.sync_outbox_queue import OutboxStore

    db_file = tmp_path / "client_outbox.db"
    store = LocalStore(str(db_file))
    try:
        # Minimal project + risk row so the outbox can fetch (project_id, version).
        store.conn.execute(
            "INSERT INTO projects (id, name, description) VALUES (?,?,?);",
            ("p1", "P", ""),
        )
        store.upsert_local_risk(
            risk_id="r1",
            project_id="p1",
            title="R",
            probability=2,
            impact=2,
            version=0,
            dirty=1,
        )

        outbox = OutboxStore(store)
        outbox.queue_risk_upsert(
            "p1", {"id": "r1", "title": "R1", "probability": 3, "impact": 4}
        )
        assert outbox.pending_count("p1") == 1

        # Mark risk as already synced (version 2), then queue again.
        store.conn.execute("UPDATE risks SET version=2 WHERE id='r1';")
        store.conn.commit()

        outbox.queue_risk_upsert(
            "p1", {"id": "r1", "title": "R2", "probability": 4, "impact": 5}
        )
        # Still one pending change due to squash behavior.
        assert outbox.pending_count("p1") == 1

        changes = outbox.get_pending_changes("p1")
        assert len(changes) == 1
        assert changes[0]["entity"] == "risk"
        assert changes[0]["op"] == "upsert"
        assert changes[0]["base_version"] == 2
        assert changes[0]["record"]["title"] == "R2"
    finally:
        store.close()


def test_requeue_conflict_creates_new_change_id_and_updates_base_version(
    tmp_path,
) -> None:
    from riskapp_client.adapters.local_storage.sqlite_data_store import LocalStore
    from riskapp_client.adapters.local_storage.sync_outbox_queue import OutboxStore

    db_file = tmp_path / "client_outbox_conflict.db"
    store = LocalStore(str(db_file))
    try:
        store.conn.execute(
            "INSERT INTO projects (id, name, description) VALUES (?,?,?);",
            ("p1", "P", ""),
        )
        store.upsert_local_risk(
            risk_id="r1",
            project_id="p1",
            title="R",
            probability=2,
            impact=2,
            version=1,
            dirty=1,
        )

        outbox = OutboxStore(store)
        outbox.queue_risk_upsert(
            "p1", {"id": "r1", "title": "R1", "probability": 2, "impact": 2}
        )
        pending = outbox.get_pending_changes("p1")
        old_id = pending[0]["change_id"]

        new_id = outbox.requeue_conflict_with_new_id(old_id, server_version=7)
        assert new_id is not None
        assert new_id != old_id

        changes = outbox.get_pending_changes("p1")
        assert len(changes) == 1
        assert changes[0]["change_id"] == new_id
        assert changes[0]["base_version"] == 7
    finally:
        store.close()
