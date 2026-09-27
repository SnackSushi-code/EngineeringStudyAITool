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
            commands::runtime_message,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
