mod commands;
mod runtime;

use runtime::RuntimeManager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(RuntimeManager::new())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            commands::runtime_health,
            commands::runtime_create_session,
            commands::runtime_message,
            commands::runtime_clear_session,
            commands::runtime_delete_session,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
