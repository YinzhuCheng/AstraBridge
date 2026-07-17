mod sidecar_supervision;

use std::collections::HashMap;
use std::path::PathBuf;
use std::process::Command;
use std::sync::Mutex;

use sidecar_supervision::{
    apply_common_sidecar_environment, SidecarLaunchConfig, SidecarSupervisor,
};
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem, Submenu};
use tauri::webview::{NewWindowResponse, WebviewWindowBuilder};
use tauri::{AppHandle, Manager, PhysicalPosition, PhysicalSize, State, WebviewUrl};
use url::Url;

const BROWSER_LABEL_PREFIX: &str = "ab-browser-";
#[derive(Default)]
struct BrowserRegistry(Mutex<HashMap<String, BrowserSession>>);

#[derive(Debug, Clone, serde::Deserialize)]
struct BrowserCreateRequest {
    id: Option<String>,
    role: Option<String>,
    url: String,
}

#[derive(Debug, Clone, serde::Deserialize)]
struct BrowserNavigateRequest {
    id: String,
    url: String,
}

#[derive(Debug, Clone, serde::Serialize)]
struct BrowserSession {
    id: String,
    role: String,
    title: String,
    url: String,
    status: String,
    error: Option<String>,
    preview_mode: String,
    supervision_status: Option<String>,
    supervision_session_id: Option<String>,
    supervision_error: Option<String>,
}

fn repo_root_from_manifest() -> Option<PathBuf> {
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest.parent()?.parent()?.parent().map(PathBuf::from)
}

fn sidecar_locations(app: &tauri::App) -> Option<(PathBuf, PathBuf)> {
    if let Ok(resource_dir) = app.path().resource_dir() {
        let bundled_dir = resource_dir.join("astrabridge-sidecar");
        let bundled_exe = bundled_dir.join("astrabridge-sidecar.exe");
        if bundled_exe.exists() {
            return Some((bundled_exe, resource_dir));
        }
        let bundled_script = bundled_dir.join("sidecar_server.py");
        if bundled_script.exists() {
            return Some((bundled_script, resource_dir));
        }
    }
    let repo_root = repo_root_from_manifest()?;
    Some((
        repo_root
            .join("apps")
            .join("astrabridge-sidecar")
            .join("sidecar_server.py"),
        repo_root,
    ))
}

fn sidecar_environment_overrides() -> HashMap<String, String> {
    let mut env = HashMap::new();
    #[cfg(windows)]
    if std::env::var_os("ASTRABRIDGE_RUNTIME_ROOT").is_none() && PathBuf::from(r"D:\").is_dir() {
        env.insert(
            "ASTRABRIDGE_RUNTIME_ROOT".to_string(),
            r"D:\AstraBridgeRuntime".to_string(),
        );
    }
    env
}

fn sidecar_state_root(app: &tauri::App, seed_root: &PathBuf) -> PathBuf {
    let workspace_state_root = seed_root.join(".astrabridge").join("desktop-sidecar");
    if seed_root.join(".git").exists() || seed_root.join(".astrabridge").exists() {
        return workspace_state_root;
    }
    if let Ok(app_data_dir) = app.path().app_data_dir() {
        return app_data_dir.join("desktop-sidecar");
    }
    workspace_state_root
}

fn sidecar_supervisor(app: &tauri::App) -> Result<SidecarSupervisor, String> {
    let (sidecar_path, seed_root) = sidecar_locations(app)
        .ok_or_else(|| "Could not resolve the AstraBridge sidecar launch path.".to_string())?;
    if !sidecar_path.exists() {
        return Err(format!(
            "AstraBridge sidecar was not found: {}",
            sidecar_path.display()
        ));
    }
    let mut python_candidates = Vec::new();
    if let Ok(path) = std::env::var("ASTRABRIDGE_PYTHON") {
        python_candidates.push(path);
    }
    python_candidates.push("python".to_string());
    python_candidates.push("py".to_string());
    let config = SidecarLaunchConfig {
        sidecar_path,
        seed_root: seed_root.clone(),
        state_root: sidecar_state_root(app, &seed_root),
        build_version: env!("CARGO_PKG_VERSION").to_string(),
        python_candidates,
        extra_env: sidecar_environment_overrides(),
        tuning: Default::default(),
    };
    SidecarSupervisor::new(config)
}

fn build_menu<R: tauri::Runtime>(handle: &tauri::AppHandle<R>) -> tauri::Result<Menu<R>> {
    let file_menu = Submenu::with_items(
        handle,
        "File",
        true,
        &[
            &MenuItem::with_id(
                handle,
                "file.new_project",
                "New Project",
                true,
                Some("Ctrl+Shift+N"),
            )?,
            &MenuItem::with_id(
                handle,
                "file.open_project",
                "Open Project",
                true,
                None::<&str>,
            )?,
            &PredefinedMenuItem::separator(handle)?,
            &PredefinedMenuItem::close_window(handle, None)?,
            &PredefinedMenuItem::quit(handle, None)?,
        ],
    )?;

    let project_menu = Submenu::with_items(
        handle,
        "Project",
        true,
        &[
            &MenuItem::with_id(
                handle,
                "project.recent",
                "Recent Projects",
                true,
                None::<&str>,
            )?,
            &MenuItem::with_id(handle, "project.close", "Close Project", true, None::<&str>)?,
        ],
    )?;

    let thread_menu = Submenu::with_items(
        handle,
        "Thread",
        true,
        &[
            &MenuItem::with_id(handle, "thread.new", "New Thread", true, Some("Ctrl+N"))?,
            &MenuItem::with_id(handle, "thread.fork", "Fork Thread", true, None::<&str>)?,
            &MenuItem::with_id(
                handle,
                "thread.archive",
                "Archive Thread",
                true,
                None::<&str>,
            )?,
        ],
    )?;

    let view_menu = Submenu::with_items(
        handle,
        "View",
        true,
        &[
            &MenuItem::with_id(
                handle,
                "view.command_palette",
                "Command Palette",
                true,
                Some("Ctrl+K"),
            )?,
            &MenuItem::with_id(handle, "view.settings", "Settings", true, Some("Ctrl+,"))?,
            &MenuItem::with_id(
                handle,
                "view.inspector",
                "Toggle Inspector",
                true,
                None::<&str>,
            )?,
        ],
    )?;

    let runtime_menu = Submenu::with_items(
        handle,
        "Runtime",
        true,
        &[
            &MenuItem::with_id(
                handle,
                "runtime.restart",
                "Restart Runtime",
                true,
                None::<&str>,
            )?,
            &MenuItem::with_id(
                handle,
                "runtime.reload_models",
                "Reload Models",
                true,
                None::<&str>,
            )?,
            &MenuItem::with_id(
                handle,
                "runtime.official_codex",
                "Official Codex",
                true,
                None::<&str>,
            )?,
        ],
    )?;

    let help_menu = Submenu::with_items(
        handle,
        "Help",
        true,
        &[&MenuItem::with_id(
            handle,
            "help.about",
            "About AstraBridge",
            true,
            None::<&str>,
        )?],
    )?;

    Menu::with_items(
        handle,
        &[
            &file_menu,
            &project_menu,
            &thread_menu,
            &view_menu,
            &runtime_menu,
            &help_menu,
        ],
    )
}

fn sanitized_token(value: &str) -> String {
    let mut token = String::new();
    let mut previous_dash = false;
    for character in value.trim().chars() {
        let normalized = character.to_ascii_lowercase();
        let next = if normalized.is_ascii_alphanumeric() {
            previous_dash = false;
            Some(normalized)
        } else if !previous_dash {
            previous_dash = true;
            Some('-')
        } else {
            None
        };
        if let Some(next) = next {
            token.push(next);
        }
    }
    token.trim_matches('-').chars().take(48).collect()
}

fn browser_label(id: Option<&str>, role: &str) -> String {
    let raw = id.and_then(|value| {
        let trimmed = value.trim();
        if trimmed.is_empty() {
            None
        } else {
            Some(trimmed)
        }
    });
    let fallback = if role.trim().is_empty() {
        "browser"
    } else {
        role
    };
    let token = sanitized_token(raw.unwrap_or(fallback));
    let token = if token.is_empty() {
        "browser".to_string()
    } else {
        token
    };
    if token.starts_with(BROWSER_LABEL_PREFIX) {
        token
    } else {
        format!("{BROWSER_LABEL_PREFIX}{token}")
    }
}

fn browser_role(value: Option<String>) -> String {
    let role = value.unwrap_or_else(|| "Browser".to_string());
    let role = role.trim();
    if role.is_empty() {
        "Browser".to_string()
    } else {
        role.chars().take(40).collect()
    }
}

fn browser_title(role: &str) -> String {
    format!("AstraBridge Browser - {role}")
}

fn validate_browser_url(raw: &str) -> Result<Url, String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Err("URL is required.".to_string());
    }
    let parsed = Url::parse(trimmed).map_err(|error| format!("Invalid URL: {error}"))?;
    match parsed.scheme() {
        "http" | "https" => Ok(parsed),
        scheme => Err(format!(
            "Unsupported URL scheme: {scheme}. Only http and https are allowed."
        )),
    }
}

fn browser_session(id: String, role: String, url: &Url) -> BrowserSession {
    BrowserSession {
        id: id.clone(),
        title: browser_title(&role),
        role,
        url: url.to_string(),
        status: "open".to_string(),
        error: None,
        preview_mode: "native".to_string(),
        supervision_status: Some("starting".to_string()),
        supervision_session_id: Some(id),
        supervision_error: None,
    }
}

fn list_open_browser_sessions(
    app: &AppHandle,
    registry: &BrowserRegistry,
) -> Result<Vec<BrowserSession>, String> {
    let sessions = registry
        .0
        .lock()
        .map_err(|_| "Browser registry lock failed.".to_string())?;
    let mut open_sessions: Vec<BrowserSession> = sessions
        .values()
        .filter(|session| app.get_webview_window(&session.id).is_some())
        .cloned()
        .collect();
    open_sessions.sort_by(|left, right| left.role.to_lowercase().cmp(&right.role.to_lowercase()));
    Ok(open_sessions)
}

fn save_browser_session(
    registry: &BrowserRegistry,
    session: BrowserSession,
) -> Result<BrowserSession, String> {
    let mut sessions = registry
        .0
        .lock()
        .map_err(|_| "Browser registry lock failed.".to_string())?;
    sessions.insert(session.id.clone(), session.clone());
    Ok(session)
}

fn remove_browser_session(registry: &BrowserRegistry, id: &str) -> Result<(), String> {
    let mut sessions = registry
        .0
        .lock()
        .map_err(|_| "Browser registry lock failed.".to_string())?;
    sessions.remove(id);
    Ok(())
}

fn get_browser_window(app: &AppHandle, id: &str) -> Result<tauri::WebviewWindow, String> {
    app.get_webview_window(id)
        .ok_or_else(|| format!("Browser window not found: {id}"))
}

#[tauri::command]
async fn browser_create(
    app: AppHandle,
    registry: State<'_, BrowserRegistry>,
    request: BrowserCreateRequest,
) -> Result<BrowserSession, String> {
    let url = validate_browser_url(&request.url)?;
    let role = browser_role(request.role);
    let id = browser_label(request.id.as_deref(), &role);
    let title = browser_title(&role);

    if let Some(existing) = app.get_webview_window(&id) {
        existing
            .eval(format!(
                "window.location.assign({});",
                serde_json::to_string(url.as_str()).map_err(|error| error.to_string())?
            ))
            .map_err(|error| format!("Could not navigate existing browser window: {error}"))?;
        existing
            .set_title(&title)
            .map_err(|error| format!("Could not set browser title: {error}"))?;
        existing
            .set_focus()
            .map_err(|error| format!("Could not focus browser window: {error}"))?;
        return save_browser_session(&registry, browser_session(id, role, &url));
    }

    let fixed_title = title.clone();
    let window = WebviewWindowBuilder::new(&app, &id, WebviewUrl::External(url.clone()))
        .title(&title)
        .inner_size(960.0, 760.0)
        .min_inner_size(420.0, 360.0)
        .resizable(true)
        .center()
        .on_navigation(|target| matches!(target.scheme(), "http" | "https"))
        .on_new_window(|_target, _features| NewWindowResponse::Deny)
        .on_document_title_changed(move |window, _title| {
            let _ = window.set_title(&fixed_title);
        })
        .build()
        .map_err(|error| format!("Could not create browser window: {error}"))?;
    window
        .set_focus()
        .map_err(|error| format!("Could not focus browser window: {error}"))?;
    save_browser_session(&registry, browser_session(id, role, &url))
}

#[tauri::command]
async fn browser_navigate(
    app: AppHandle,
    registry: State<'_, BrowserRegistry>,
    request: BrowserNavigateRequest,
) -> Result<BrowserSession, String> {
    let url = validate_browser_url(&request.url)?;
    let window = get_browser_window(&app, &request.id)?;
    window
        .eval(format!(
            "window.location.assign({});",
            serde_json::to_string(url.as_str()).map_err(|error| error.to_string())?
        ))
        .map_err(|error| format!("Could not navigate browser window: {error}"))?;
    window
        .set_focus()
        .map_err(|error| format!("Could not focus browser window: {error}"))?;

    let role = {
        let sessions = registry
            .0
            .lock()
            .map_err(|_| "Browser registry lock failed.".to_string())?;
        sessions
            .get(&request.id)
            .map(|session| session.role.clone())
            .unwrap_or_else(|| {
                request
                    .id
                    .trim_start_matches(BROWSER_LABEL_PREFIX)
                    .to_string()
            })
    };
    save_browser_session(&registry, browser_session(request.id, role, &url))
}

#[tauri::command]
async fn browser_list(
    app: AppHandle,
    registry: State<'_, BrowserRegistry>,
) -> Result<Vec<BrowserSession>, String> {
    list_open_browser_sessions(&app, &registry)
}

#[tauri::command]
async fn browser_focus(
    app: AppHandle,
    registry: State<'_, BrowserRegistry>,
    id: String,
) -> Result<BrowserSession, String> {
    let window = get_browser_window(&app, &id)?;
    window
        .set_focus()
        .map_err(|error| format!("Could not focus browser window: {error}"))?;
    let mut session = {
        let sessions = registry
            .0
            .lock()
            .map_err(|_| "Browser registry lock failed.".to_string())?;
        sessions
            .get(&id)
            .cloned()
            .unwrap_or_else(|| BrowserSession {
                id: id.clone(),
                role: id.trim_start_matches(BROWSER_LABEL_PREFIX).to_string(),
                title: window.title().unwrap_or_else(|_| browser_title(&id)),
                url: "".to_string(),
                status: "focused".to_string(),
                error: None,
                preview_mode: "native".to_string(),
                supervision_status: Some("starting".to_string()),
                supervision_session_id: Some(id.clone()),
                supervision_error: None,
            })
    };
    session.title = window.title().unwrap_or_else(|_| browser_title(&id));
    session.status = "focused".to_string();
    save_browser_session(&registry, session)
}

#[tauri::command]
async fn browser_close(
    app: AppHandle,
    registry: State<'_, BrowserRegistry>,
    id: String,
) -> Result<Vec<BrowserSession>, String> {
    if let Some(window) = app.get_webview_window(&id) {
        window
            .close()
            .map_err(|error| format!("Could not close browser window: {error}"))?;
    }
    remove_browser_session(&registry, &id)?;
    list_open_browser_sessions(&app, &registry)
}

#[tauri::command]
async fn browser_tile_two_up(
    app: AppHandle,
    registry: State<'_, BrowserRegistry>,
    ids: Vec<String>,
) -> Result<Vec<BrowserSession>, String> {
    if ids.len() != 2 {
        return Err("Two browser window ids are required.".to_string());
    }
    let first = get_browser_window(&app, &ids[0])?;
    let second = get_browser_window(&app, &ids[1])?;
    let monitor = first
        .current_monitor()
        .ok()
        .flatten()
        .or_else(|| app.primary_monitor().ok().flatten());
    let (origin_x, origin_y, width, height) = if let Some(monitor) = monitor {
        let position = monitor.position();
        let size = monitor.size();
        (
            position.x + 32,
            position.y + 48,
            size.width.saturating_sub(96).max(900),
            size.height.saturating_sub(128).max(620),
        )
    } else {
        (40, 60, 1680, 760)
    };
    let gutter: u32 = 16;
    let half_width = width.saturating_sub(gutter) / 2;
    let tile_height = height;
    first
        .set_position(PhysicalPosition::new(origin_x, origin_y))
        .map_err(|error| format!("Could not position first browser window: {error}"))?;
    first
        .set_size(PhysicalSize::new(half_width, tile_height))
        .map_err(|error| format!("Could not size first browser window: {error}"))?;
    second
        .set_position(PhysicalPosition::new(
            origin_x + half_width as i32 + gutter as i32,
            origin_y,
        ))
        .map_err(|error| format!("Could not position second browser window: {error}"))?;
    second
        .set_size(PhysicalSize::new(half_width, tile_height))
        .map_err(|error| format!("Could not size second browser window: {error}"))?;
    first
        .set_focus()
        .map_err(|error| format!("Could not focus browser windows: {error}"))?;
    second
        .set_focus()
        .map_err(|error| format!("Could not focus browser windows: {error}"))?;
    list_open_browser_sessions(&app, &registry)
}

#[tauri::command]
fn sidecar_url(supervisor: State<'_, SidecarSupervisor>) -> Result<String, String> {
    supervisor.sidecar_url()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn desktop_sidecar_does_not_inherit_codex_home_overrides() {
        let mut command = Command::new("sidecar-placeholder");
        apply_common_sidecar_environment(&mut command, &sidecar_environment_overrides());
        let environments: HashMap<_, _> = command.get_envs().collect();

        assert_eq!(
            environments.get(std::ffi::OsStr::new("CODEX_HOME")),
            Some(&None)
        );
        assert_eq!(
            environments.get(std::ffi::OsStr::new("ASTRABRIDGE_CODEX_HOME")),
            Some(&None)
        );
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .menu(build_menu)
        .setup(|app| {
            let supervisor = sidecar_supervisor(app)?;
            let _ = supervisor.sidecar_url();
            app.manage(supervisor);
            app.manage(BrowserRegistry::default());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            sidecar_url,
            browser_create,
            browser_navigate,
            browser_list,
            browser_focus,
            browser_close,
            browser_tile_two_up
        ])
        .run(tauri::generate_context!())
        .expect("error while running AstraBridge");
}
