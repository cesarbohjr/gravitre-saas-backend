use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Emitter, Manager, WindowEvent,
};
use tauri_plugin_autostart::MacosLauncher;
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

/// Quick Ask from any app: Cmd+Shift+Space on macOS, Ctrl+Shift+Space elsewhere.
fn quick_ask_shortcut() -> Shortcut {
    #[cfg(target_os = "macos")]
    let modifier = Modifiers::SUPER;
    #[cfg(not(target_os = "macos"))]
    let modifier = Modifiers::CONTROL;
    Shortcut::new(Some(modifier | Modifiers::SHIFT), Code::Space)
}

/// Talk from any app: Option+Space / Alt+Space starts listening, pressing again sends.
fn talk_shortcut() -> Shortcut {
    Shortcut::new(Some(Modifiers::ALT), Code::Space)
}

fn show_main(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

/// Brings the window forward, then tells the page what to open.
fn show_and_emit(app: &AppHandle, event: &str, payload: &str) {
    show_main(app);
    let _ = app.emit(event, payload.to_string());
}

fn log(line: &str) {
    eprintln!("[gravitre-desktop] {line}");
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
    show_main(&app);
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let quick = quick_ask_shortcut();
    let talk = talk_shortcut();
    tauri::Builder::default()
        // Must be first: a second launch (or a gravitre:// link on Windows/Linux) focuses this one.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            show_main(app);
        }))
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_store::Builder::default().build())
        .plugin(tauri_plugin_deep_link::init())
        .plugin(tauri_plugin_autostart::init(MacosLauncher::LaunchAgent, None))
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(move |app, shortcut, event| {
                    if event.state() != ShortcutState::Pressed {
                        return;
                    }
                    if shortcut == &quick {
                        show_and_emit(app, "quick-ask", "");
                    } else if shortcut == &talk {
                        show_and_emit(app, "push-to-talk", "");
                    }
                })
                .build(),
        )
        .invoke_handler(tauri::generate_handler![
            open_web_deep_link,
            show_companion_window
        ])
        .on_window_event(|window, event| {
            // Closing the window keeps Gravitre in the tray so approval notifications still arrive.
            if let WindowEvent::CloseRequested { api, .. } = event {
                if window.label() == "main" {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .setup(move |app| {
            let show_i = MenuItem::with_id(app, "show", "Open Gravitre", true, None::<&str>)?;
            let quick_i = MenuItem::with_id(app, "quick", "Quick Ask", true, None::<&str>)?;
            let approvals_i = MenuItem::with_id(app, "approvals", "Approvals", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Quit Gravitre", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_i, &quick_i, &approvals_i, &quit_i])?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .show_menu_on_left_click(false)
                .tooltip("Gravitre")
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => show_main(app),
                    "quick" => show_and_emit(app, "quick-ask", ""),
                    "approvals" => show_and_emit(app, "open-view", "appr"),
                    "quit" => app.exit(0),
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        show_main(tray.app_handle());
                    }
                })
                .build(app)?;

            for (shortcut, name) in [(quick, "Quick Ask"), (talk, "Talk")] {
                if let Err(err) = app.global_shortcut().register(shortcut) {
                    log(&format!("{name} shortcut unavailable ({err}); the in-app buttons still work"));
                }
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Gravitre desktop");
}
