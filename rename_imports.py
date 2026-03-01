import os
import glob

# Uistite sa, že dlhšie reťazce sú pred kratšími (aby nedošlo k čiastočnému nahradeniu)
REPLACEMENTS = {
    # Mappers & Adapters
    "riskapp_client.domain.action_assessment_codec": "riskapp_client.adapters.mappers.action_assessment_mapper",
    "riskapp_client.domain.scored_codec": "riskapp_client.adapters.mappers.scored_entity_mapper",
    "riskapp_client.adapters.local.outbox": "riskapp_client.adapters.local_storage.sync_outbox_queue",
    "riskapp_client.adapters.local.sqlite_schema": "riskapp_client.adapters.local_storage.sqlite_schema_definition",
    "riskapp_client.adapters.local.sqlite_store": "riskapp_client.adapters.local_storage.sqlite_data_store",
    "riskapp_client.adapters.remote.api_backend": "riskapp_client.adapters.remote_api.rest_api_client",
    "riskapp_client.services.export_csv": "riskapp_client.adapters.local_storage.csv_data_exporter",

    # Domain
    "riskapp_client.domain.models": "riskapp_client.domain.domain_models",
    "riskapp_client.domain.scored_fields": "riskapp_client.domain.scored_entity_fields",

    # Services
    "riskapp_client.services.action_service": "riskapp_client.services.action_management_service",
    "riskapp_client.services.assessment_service": "riskapp_client.services.assessment_management_service",
    "riskapp_client.services.filters": "riskapp_client.services.entity_filters",
    "riskapp_client.services.members_service": "riskapp_client.services.member_management_service",
    "riskapp_client.services.offline_first_backend": "riskapp_client.services.offline_first_facade",
    "riskapp_client.services.permissions": "riskapp_client.utils.role_permission_evaluator",
    "riskapp_client.services.scored_entity_service": "riskapp_client.services.scored_entity_management_service",
    "riskapp_client.services.security": "riskapp_client.utils.url_validation_helpers",
    "riskapp_client.services.sync_service": "riskapp_client.services.synchronization_service",

    # Utils
    "riskapp_client.utils.normalize": "riskapp_client.utils.text_normalization_helpers",
    "riskapp_client.utils.logging_config": "riskapp_client.utils.logging_configuration",

    # UI Components & Mixins
    "riskapp_client.ui.widgets": "riskapp_client.ui.components.custom_gui_widgets",
    "riskapp_client.ui.main_window": "riskapp_client.ui.main_application_window",
    "riskapp_client.ui.mixins.core_mixin": "riskapp_client.ui.mixins.global_state_mixin",
    "riskapp_client.ui.mixins.scored_entities_ui": "riskapp_client.ui.mixins.scored_entities_ui_helpers",

    # UI Tabs
    "riskapp_client.ui.tabs.actions": "riskapp_client.ui.tabs.actions_tab",
    "riskapp_client.ui.tabs.assessments": "riskapp_client.ui.tabs.assessments_tab",
    "riskapp_client.ui.tabs.matrix": "riskapp_client.ui.tabs.matrix_tab",
    "riskapp_client.ui.tabs.members": "riskapp_client.ui.tabs.members_tab",
    "riskapp_client.ui.tabs.opportunities": "riskapp_client.ui.tabs.opportunities_tab",
    "riskapp_client.ui.tabs.risks": "riskapp_client.ui.tabs.risks_tab",
    "riskapp_client.ui.tabs.scored_entities": "riskapp_client.ui.tabs.scored_entities_base_tab",
    "riskapp_client.ui.tabs.top_history": "riskapp_client.ui.tabs.top_history_tab",

    # App
    "riskapp_client.app.bootstrap": "riskapp_client.app.application_bootstrap",
    "riskapp_client.app.config": "riskapp_client.app.environment_config",
    "riskapp_client.app.main": "riskapp_client.app.main_entrypoint",
}

def update_imports(root_dir="riskapp_client"):
    py_files = glob.glob(f"{root_dir}/**/*.py", recursive=True)
    
    changed_files_count = 0
    
    for file_path in py_files:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        new_content = content
        for old_import, new_import in REPLACEMENTS.items():
            new_content = new_content.replace(old_import, new_import)
            
        if new_content != content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"✅ Aktualizované importy v: {file_path}")
            changed_files_count += 1
            
    print(f"\nHotovo! Upravených {changed_files_count} súborov.")

if __name__ == "__main__":
    update_imports()