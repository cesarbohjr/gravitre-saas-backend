use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Emitter, Manager, WebviewWindow,
};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

static SUMMON_START_MS: AtomicU64 = AtomicU64::new(0);

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

fn companion_shortcut() -> Shortcut {
    Shortcut::new(Some(Modifiers::ALT), Code::Space)
}

fn toggle_companion(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        if window.is_visible().unwrap_or(false) {
            let _ = window.hide();
        } else {
            show_companion(app, &window, true);
        }
    }
}

fn show_companion(app: &AppHandle, window: &WebviewWindow, measure: bool) {
    if measure {
        SUMMON_START_MS.store(now_ms(), Ordering::SeqCst);
    }
    let _ = window.set_always_on_top(true);
    let _ = window.show();
    let _ = window.set_focus();
    if measure {
        let _ = app.emit("companion-summoned", now_ms());
    }
}

#[tauri::command]
fn open_web_deep_link(app: AppHandle, path: String) -> Result<(), String> {
    let base = std::env::var("GRAVITRE_APP_BASE").unwrap_or_else(|_| "https://gravitre.app".into());
    let url = if path.starts_with("http://") || path.starts_with("https://") {
        path
    } else {
        format!(
            "{}/{}",
            base.trim_end_matches('/'),
            path.trim_start_matches('/')
        )
    };
    tauri_plugin_shell::ShellExt::shell(&app)
        .open(url, None)
        .map_err(|e| e.to_string())
}

#[tauri::command]
fn show_companion_window(app: AppHandle) -> Result<(), String> {
    let window = app
        .get_webview_window("main")
        .ok_or_else(|| "main window missing".to_string())?;
    show_companion(&app, &window, false);
    Ok(())
}

/// Frontend calls this when the composer is focused / input-ready after a summon.
#[tauri::command]
fn report_input_ready() -> Result<u64, String> {
    let start = SUMMON_START_MS.swap(0, Ordering::SeqCst);
    if start == 0 {
        return Ok(0);
    }
    let elapsed = now_ms().saturating_sub(start);
    eprintln!("[gravitre-desktop] summon_to_input_ready_ms={elapsed}");
    Ok(elapsed)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_store::Builder::default().build())
        .plugin(tauri_plugin_deep_link::init())
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                show_companion(app, &window, true);
            }
        }))
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _shortcut, event| {
                    if event.state() == ShortcutState::Pressed {
                        toggle_companion(app);
                    }
                })
                .build(),
        )
        .invoke_handler(tauri::generate_handler![
            open_web_deep_link,
            show_companion_window,
            report_input_ready
        ])
        .setup(|app| {
            let show_i = MenuItem::with_id(app, "show", "Open Gravitre", true, None::<&str>)?;
            let chat_i = MenuItem::with_id(app, "chat", "New chat", true, None::<&str>)?;
            let approvals_i =
                MenuItem::with_id(app, "approvals", "Approvals (web)", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_i, &chat_i, &approvals_i, &quit_i])?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .tooltip("Gravitre")
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" | "chat" => {
                        if let Some(window) = app.get_webview_window("main") {
                            show_companion(app, &window, true);
                        }
                    }
                    "approvals" => {
                        let _ = open_web_deep_link(app.clone(), "/approvals".into());
                    }
                    "quit" => {
                        app.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        toggle_companion(tray.app_handle());
                    }
                })
                .build(app)?;

            app.global_shortcut().register(companion_shortcut())?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Gravitre desktop");
}
